from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AIJob, Flashcard
from app.services import srs

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


def test_sm2_schedule_progression():
    state = srs.CardState(ease_factor=2.5, interval_days=0, repetitions=0, lapses=0)
    first = srs.schedule(state, "good", NOW)
    assert first.state.interval_days == 1 and first.due_at == NOW + timedelta(days=1)
    second = srs.schedule(first.state, "good", NOW)
    assert second.state.interval_days == 6
    third = srs.schedule(second.state, "good", NOW)
    assert third.state.interval_days == 15  # ceil(6 * 2.5)
    easy = srs.schedule(second.state, "easy", NOW)
    assert easy.state.interval_days > third.state.interval_days and easy.state.ease_factor == 2.6
    hard = srs.schedule(second.state, "hard", NOW)
    assert 1 <= hard.state.interval_days < third.state.interval_days and hard.state.ease_factor == 2.35
    again = srs.schedule(third.state, "again", NOW)
    assert again.state.repetitions == 0 and again.state.lapses == 1
    assert again.due_at == NOW + timedelta(minutes=10)


def test_sm2_ease_and_interval_bounds():
    state = srs.CardState(ease_factor=1.35, interval_days=300, repetitions=8, lapses=0)
    assert srs.schedule(state, "again", NOW).state.ease_factor == 1.3
    long = srs.schedule(srs.CardState(3.0, 300, 8, 0), "easy", NOW)
    assert long.state.interval_days == 365 and long.state.ease_factor == 3.0


def _notes(client, headers, *bodies):
    return [
        client.post("/api/v1/notes", json={"title": f"Note {i}", "body": b}, headers=headers).json()
        for i, b in enumerate(bodies)
    ]


def test_crunch_is_idempotent_and_cached(client, make_user, auth, settings):
    from pipeline.ai_orchestrator import AIOrchestrator

    headers = auth(make_user())
    notes = _notes(
        client,
        headers,
        "Repo rate: rate at which RBI lends to banks. MPC has six members chaired by the Governor.",
        "GST came into force on 1 July 2017. GST Council is under Article 279A.",
    )
    body = {"note_ids": [n["id"] for n in notes], "settings": {"flashcards": 5}}
    preview = client.post("/api/v1/crunch/preview", json=body, headers=headers).json()
    assert preview["engine_resolved"] == "offline" and preview["within_budget"]
    assert preview["disclosure"]["ai_available"] is False

    first = client.post("/api/v1/crunch", json=body, headers=headers)
    assert first.status_code == 202
    job = first.json()
    assert (
        job["status"] == "queued"
        and job["engine"] == "offline"
        and first.headers["location"].endswith(job["id"])
    )
    same = client.post("/api/v1/crunch", json=body, headers=headers)
    assert same.status_code == 202 and same.json()["id"] == job["id"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AIJob.id))) == 1

    outcomes = AIOrchestrator(SessionLocal, settings, providers={}).run_once()
    assert [o.status for o in outcomes] == ["succeeded"]
    done = client.get(f"/api/v1/crunch/jobs/{job['id']}", headers=headers).json()
    assert done["status"] == "completed" and done["output_id"]

    output = client.get(f"/api/v1/crunch/outputs/{done['output_id']}", headers=headers).json()
    assert output["engine"] == "offline" and output["concise_bullets"]
    refs = {r["ref"] for r in output["source_refs"]}
    assert all(set(b["source_refs"]) <= refs for b in output["concise_bullets"])
    assert all(b["verified"] is False for b in output["concise_bullets"])
    assert output["flashcards"]

    cached = client.post("/api/v1/crunch", json=body, headers=headers)
    assert cached.status_code == 200 and cached.json()["cached"] is True
    assert cached.json()["output_id"] == done["output_id"]

    client.patch(f"/api/v1/notes/{notes[0]['id']}", json={"body": "Changed content here."}, headers=headers)
    changed = client.post("/api/v1/crunch", json=body, headers=headers).json()
    assert changed["id"] != job["id"] and changed["status"] == "queued"


def test_crunch_ownership_and_privacy(client, make_user, auth):
    alice, bob = make_user("Alice"), make_user("Bob")
    note = _notes(client, auth(alice), "Alice private revision note about Article 21.")[0]
    stolen = client.post("/api/v1/crunch", json={"note_ids": [note["id"]]}, headers=auth(bob))
    assert stolen.status_code == 404
    job = client.post("/api/v1/crunch", json={"note_ids": [note["id"]]}, headers=auth(alice)).json()
    assert client.get(f"/api/v1/crunch/jobs/{job['id']}", headers=auth(bob)).status_code == 404
    # AI engine requires explicit consent before private notes can leave the server.
    ai = client.post("/api/v1/crunch", json={"note_ids": [note["id"]], "engine": "ai"}, headers=auth(alice))
    assert ai.status_code == 403


def test_crunch_output_isolation(client, make_user, auth, settings):
    from pipeline.ai_orchestrator import AIOrchestrator

    alice, bob = make_user("Alice"), make_user("Bob")
    note = _notes(client, auth(alice), "Project Tiger launched in 1973. NTCA administers it.")[0]
    job = client.post("/api/v1/crunch", json={"note_ids": [note["id"]]}, headers=auth(alice)).json()
    AIOrchestrator(SessionLocal, settings, providers={}).run_once()
    output_id = client.get(f"/api/v1/crunch/jobs/{job['id']}", headers=auth(alice)).json()["output_id"]
    assert client.get(f"/api/v1/crunch/outputs/{output_id}", headers=auth(bob)).status_code == 404
    assert client.get("/api/v1/crunch/outputs", headers=auth(bob)).json() == []
    assert client.get("/api/v1/flashcards", headers=auth(bob)).json() == []


def test_crunch_limits(client, make_user, auth, settings):
    headers = auth(make_user())
    big = _notes(client, headers, "x " * 2400, "y " * 2400, "z " * 2400)
    res = client.post("/api/v1/crunch", json={"note_ids": [n["id"] for n in big]}, headers=headers)
    assert res.status_code == 413
    empty = client.post("/api/v1/crunch", json={}, headers=headers)
    assert empty.status_code == 422


def test_flashcard_review_and_due(client, make_user, auth, settings):
    from pipeline.ai_orchestrator import AIOrchestrator

    alice, bob = make_user("Alice"), make_user("Bob")
    headers = auth(alice)
    note = _notes(
        client, headers, "Repo rate: rate at which RBI lends to banks\nCRR: share of deposits kept with RBI"
    )[0]
    client.post("/api/v1/crunch", json={"note_ids": [note["id"]]}, headers=headers)
    AIOrchestrator(SessionLocal, settings, providers={}).run_once()
    due = client.get("/api/v1/revision/due", headers=headers).json()
    assert due["due_flashcards"] >= 2 and due["recaps"]
    card = due["flashcards"][0]
    assert (
        client.post(
            f"/api/v1/flashcards/{card['id']}/reviews", json={"outcome": "good"}, headers=auth(bob)
        ).status_code
        == 404
    )
    reviewed = client.post(
        f"/api/v1/flashcards/{card['id']}/reviews", json={"outcome": "good"}, headers=headers
    ).json()
    assert reviewed["interval_days"] == 1
    with SessionLocal() as db:
        stored = db.get(Flashcard, card["id"])
        assert stored.repetitions == 1 and stored.due_at > datetime.now(UTC)
    after = client.get("/api/v1/revision/due", headers=headers).json()
    assert after["due_flashcards"] == due["due_flashcards"] - 1 and after["upcoming"]

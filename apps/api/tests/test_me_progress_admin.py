from __future__ import annotations

import os
from datetime import date, timedelta

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Event, IngestionRun, Note, User
from app.services.progress import level_for, streaks


def test_preferences_round_trip_and_validation(client, make_user, auth):
    headers = auth(make_user())
    prefs = client.get("/api/v1/me/preferences", headers=headers).json()
    assert prefs["onboarded_at"] is None
    payload = {
        **{k: v for k, v in prefs.items() if k != "onboarded_at"},
        "target_exam": "BANKING",
        "topics": ["economy", "science"],
        "banglish_intensity": 3,
        "crunch_ai_consent": "primary_only",
        "mark_onboarded": True,
    }
    updated = client.put("/api/v1/me/preferences", json=payload, headers=headers).json()
    assert updated["target_exam"] == "BANKING" and updated["onboarded_at"]
    me = client.get("/api/v1/me", headers=headers).json()
    assert me["crunch_ai"]["consent"] == "primary_only" and me["crunch_ai"]["ai_available"] is False
    bad_tz = client.put(
        "/api/v1/me/preferences", json={**payload, "timezone": "Mars/Olympus"}, headers=headers
    )
    assert bad_tz.status_code == 422
    bad_exam = client.put("/api/v1/me/preferences", json={**payload, "target_exam": "IIT"}, headers=headers)
    assert bad_exam.status_code == 422


def test_export_and_delete_account(client, make_user, auth):
    user = make_user()
    headers = auth(user)
    client.post("/api/v1/notes", json={"title": "Keep me", "body": "Export this"}, headers=headers)
    export = client.get("/api/v1/me/export", headers=headers).json()
    assert export["notes"][0]["title"] == "Keep me"
    assert "user_id" not in export["notes"][0]
    assert client.delete("/api/v1/me", headers=headers).status_code == 204
    with SessionLocal() as db:
        assert db.get(User, user.id) is None
        assert db.scalar(select(func.count(Note.id))) == 0
    assert client.get("/api/v1/me", headers=headers).status_code == 401


def test_progress_after_activity(client, seeded, make_user, auth):
    headers = auth(make_user())
    session = client.post("/api/v1/quizzes/sessions", json={"type": "daily"}, headers=headers).json()
    from app.models import Question

    with SessionLocal() as db:
        q = db.get(Question, session["questions"][0]["id"])
        correct = q.correct_index
    client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": session["questions"][0]["id"], "selected_index": correct},
        headers=headers,
    )
    client.post(f"/api/v1/quizzes/sessions/{session['id']}/finish", headers=headers)
    progress = client.get("/api/v1/progress", headers=headers).json()
    assert progress["xp_total"] == 30
    assert progress["streak_current"] == 1 and progress["studied_today"] is True
    assert progress["today_answered"] == 1 and progress["accuracy_overall"] == 1.0
    assert len(progress["activity"]) == 14 and progress["activity"][-1]["count"] >= 1


def test_streak_and_level_math():
    today = date(2026, 3, 10)
    days = {today, today - timedelta(days=1), today - timedelta(days=2), today - timedelta(days=5)}
    assert streaks(days, today) == (3, 3)
    assert streaks({today - timedelta(days=1)}, today) == (1, 1)
    assert streaks({today - timedelta(days=3)}, today) == (0, 1)
    assert level_for(0) == (1, 0, 100)
    assert level_for(100) == (2, 100, 300)
    assert level_for(299) == (2, 100, 300)


def test_admin_review_queue_approve_and_reject(client, make_user, auth, make_event):
    admin = auth(make_user("Admin", admin=True))
    draft = make_event(title="Draft needing review", status="needs_review")
    other = make_event(title="Another draft", status="needs_review")
    queue = client.get("/api/v1/admin/review-queue", headers=admin).json()
    assert {q["event_id"] for q in queue} == {str(draft.id), str(other.id)}
    assert queue[0]["draft"]["headline"].startswith("AI headline")

    approved = client.post(f"/api/v1/admin/events/{draft.id}/approve", json={}, headers=admin).json()
    assert approved["status"] == "published"
    detail = client.get(f"/api/v1/news/{draft.slug}").json()
    assert detail["ai_status"] == "ready" and detail["verification"]["method"] == "editor_review"

    rejected = client.post(
        f"/api/v1/admin/events/{other.id}/reject", json={"note": "duplicate"}, headers=admin
    ).json()
    assert rejected["status"] == "rejected"
    with SessionLocal() as db:
        assert db.get(Event, other.id).review_note == "duplicate"


def test_admin_ingestion_respects_live_flag(client, make_user, auth, seeded, monkeypatch):
    admin = auth(make_user("Admin", admin=True))
    blocked = client.post("/api/v1/admin/ingestion/run", json={}, headers=admin)
    assert blocked.status_code == 403
    from app.config import get_settings

    monkeypatch.setenv("ENABLE_LIVE_INGESTION", "true")
    get_settings.cache_clear()
    try:
        queued = client.post("/api/v1/admin/ingestion/run", json={"source_slug": "rbi-press"}, headers=admin)
        assert queued.status_code == 202
        again = client.post("/api/v1/admin/ingestion/run", json={"source_slug": "rbi-press"}, headers=admin)
        assert again.json()["id"] == queued.json()["id"]
        with SessionLocal() as db:
            assert db.scalar(select(func.count(IngestionRun.id))) == 1
    finally:
        monkeypatch.delenv("ENABLE_LIVE_INGESTION")
        get_settings.cache_clear()

    overview = client.get("/api/v1/admin/overview", headers=admin).json()
    assert {s["slug"] for s in overview["sources"]} >= {"pib", "gdelt", "rbi-press", "un-news"}
    assert all(not p["operational"] for p in overview["providers"])
    assert "GEMINI_API_KEY missing" in overview["providers"][0]["problems"]
    assert os.environ["API_JWT_SECRET"] not in str(overview)

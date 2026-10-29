from __future__ import annotations

from app.db import SessionLocal
from app.models import Article


def test_note_crud_persists_and_sanitizes(client, make_user, auth):
    headers = auth(make_user())
    created = client.post(
        "/api/v1/notes",
        json={
            "title": "<b>Article 32</b>",
            "body": "Heart and soul <script>alert('x')</script>of the Constitution",
            "color": "lavender",
            "tags": ["Polity", "polity", "<i>writs</i>"],
        },
        headers=headers,
    )
    assert created.status_code == 201
    note = created.json()
    assert note["title"] == "Article 32"
    assert "<script>" not in note["body"] and "alert" not in note["body"]
    assert note["tags"] == ["polity", "writs"]
    assert note["revision_version"] == 1

    moved = client.patch(
        f"/api/v1/notes/{note['id']}", json={"board_x": 120, "board_y": 40}, headers=headers
    ).json()
    assert moved["revision_version"] == 1, "moving a sticky must not change its content version"
    edited = client.patch(
        f"/api/v1/notes/{note['id']}", json={"body": "Updated body"}, headers=headers
    ).json()
    assert edited["revision_version"] == 2

    listing = client.get("/api/v1/notes", headers=headers).json()
    assert [n["id"] for n in listing] == [note["id"]]
    assert listing[0]["board_x"] == 120

    conflict = client.patch(
        f"/api/v1/notes/{note['id']}", json={"body": "stale write", "expected_version": 1}, headers=headers
    )
    assert conflict.status_code == 409
    assert conflict.json()["current"]["body"] == "Updated body"

    assert client.delete(f"/api/v1/notes/{note['id']}", headers=headers).status_code == 204
    assert client.get("/api/v1/notes", headers=headers).json() == []


def test_note_validation(client, make_user, auth):
    headers = auth(make_user())
    assert client.post("/api/v1/notes", json={"color": "neon"}, headers=headers).status_code == 422
    assert client.post("/api/v1/notes", json={"body": "x" * 5001}, headers=headers).status_code == 422


def test_user_a_cannot_touch_user_b_notes(client, make_user, auth):
    alice, bob = make_user("Alice"), make_user("Bob")
    note = client.post("/api/v1/notes", json={"title": "Alice secret"}, headers=auth(alice)).json()
    bob_h = auth(bob)
    assert client.get("/api/v1/notes", headers=bob_h).json() == []
    assert (
        client.patch(f"/api/v1/notes/{note['id']}", json={"title": "pwned"}, headers=bob_h).status_code == 404
    )
    assert client.delete(f"/api/v1/notes/{note['id']}", headers=bob_h).status_code == 404
    assert client.get("/api/v1/notes", headers=auth(alice)).json()[0]["title"] == "Alice secret"


def test_snapshot_saved_once_and_survives_article_edits(client, seeded, make_user, auth):
    headers = auth(make_user())
    slug = "demo-upi-npci-explainer"
    first = client.post("/api/v1/snapshots", json={"article_slug": slug}, headers=headers)
    assert first.status_code == 201
    snap = first.json()
    assert snap["verified"] is True and snap["source_url"].startswith("https://")
    assert len(snap["saved_key_facts"]) == 3
    again = client.post("/api/v1/snapshots", json={"article_slug": slug}, headers=headers)
    assert again.status_code == 200 and again.json()["id"] == snap["id"]

    with SessionLocal() as db:
        article = db.get(Article, snap["article_id"])
        article.headline = "Edited headline"
        db.commit()
    listed = client.get("/api/v1/snapshots", headers=headers).json()
    assert listed[0]["saved_title"] == snap["saved_title"]
    assert listed[0]["article_updated_since_save"] is True

    detail = client.get(f"/api/v1/news/{slug}", headers=headers).json()
    assert detail["snapshot_id"] == snap["id"] and detail["saved"] is True


def test_source_only_snapshot_and_isolation(client, make_event, make_user, auth):
    event = make_event(title="Pending story", status="discovered")
    alice, bob = make_user("Alice"), make_user("Bob")
    snap = client.post("/api/v1/snapshots", json={"article_slug": event.slug}, headers=auth(alice)).json()
    assert snap["verified"] is False and snap["saved_title"] == "Pending story"
    assert client.get("/api/v1/snapshots", headers=auth(bob)).json() == []
    assert client.delete(f"/api/v1/snapshots/{snap['id']}", headers=auth(bob)).status_code == 404
    assert client.delete(f"/api/v1/snapshots/{snap['id']}", headers=auth(alice)).status_code == 204


def test_note_cannot_attach_foreign_snapshot(client, seeded, make_user, auth):
    alice, bob = make_user("Alice"), make_user("Bob")
    snap = client.post(
        "/api/v1/snapshots", json={"article_slug": "demo-gst-council-279a"}, headers=auth(alice)
    ).json()
    res = client.post("/api/v1/notes", json={"title": "x", "snapshot_id": snap["id"]}, headers=auth(bob))
    assert res.status_code == 404

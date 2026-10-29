from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AIJob, Article, ArticleChatCache
from app.services.chat import question_hash


def test_archive_lists_only_stored_dates(client, make_event):
    day = date(2026, 3, 4)
    event = make_event(status="published", day=day)
    archive = client.get("/api/v1/news/archive", params={"demo": "false"}).json()
    match = next(row for row in archive["dates"] if row["date"] == "2026-03-04")
    assert match["story_count"] >= 1 and match["ai_count"] >= 1
    page = client.get("/api/v1/news", params={"date": "2026-03-04", "demo": "false"}).json()
    assert any(item["slug"] == event.slug for item in page["items"])
    empty = client.get("/api/v1/news", params={"date": "2020-01-01", "demo": "false"}).json()
    assert empty["total"] == 0


def test_opening_news_does_not_queue_ai(client, make_event):
    event = make_event(status="published")
    client.get("/api/v1/news", params={"demo": "false"})
    client.get(f"/api/v1/news/{event.slug}")
    client.get("/api/v1/editions/today")
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AIJob.id))) == 0


def test_chat_serves_cached_answers_and_queues_new_ones(client, make_user, auth, make_event):
    user = make_user()
    event = make_event(status="published")
    headers = auth(user)
    with SessionLocal() as db:
        article = db.scalar(select(Article).where(Article.event_id == event.id))
        assert article is not None
        db.add(
            ArticleChatCache(
                article_id=article.id,
                question_hash=question_hash(article.id, "Why does this matter?"),
                answer="Bhai, Cabinet-er mission-ta exam-e outlay ar year diye mone rakhbi.",
            )
        )
        db.commit()

    cached = client.post(
        f"/api/v1/news/{event.slug}/chat",
        json={"message": "  Why does this matter? "},
        headers=headers,
    )
    assert cached.status_code == 200
    body = cached.json()
    assert body["pending"] is False
    assert any(m["cached"] and "outlay" in m["body"] for m in body["messages"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AIJob.id)).where(AIJob.kind == "article_chat")) == 0

    queued = client.post(
        f"/api/v1/news/{event.slug}/chat",
        json={"message": "Ministry-r naam ta ki?"},
        headers=headers,
    )
    assert queued.status_code == 202
    assert queued.json()["pending"] is True
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AIJob.id)).where(AIJob.kind == "article_chat")) == 1

    busy = client.post(
        f"/api/v1/news/{event.slug}/chat",
        json={"message": "Abar bolbi?"},
        headers=headers,
    )
    assert busy.status_code == 409

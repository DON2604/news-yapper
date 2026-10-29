"""Read saved articles for quiz and chat. This module never calls a model or a news feed."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Article, Event, EventSource, SourceItem


@dataclass
class StoredStory:
    article_id: str
    event_id: str
    date: str
    category: str
    sensitive: bool
    text: str
    source_urls: list[str]
    source_item_ids: list[str]


def story_text(article: Article, source_lines: list[str]) -> str:
    facts = []
    for fact in article.key_facts or []:
        if isinstance(fact, dict) and fact.get("claim"):
            facts.append(f"- {fact['claim']}")
    parts = [
        article.headline,
        article.banglish_summary,
        article.neutral_summary,
        article.why_matters or "",
        article.context or "",
        "\n".join(facts),
        "\n".join(source_lines),
    ]
    return "\n".join(part for part in parts if part)


def _source_lines(db: Session, event_id: uuid.UUID) -> tuple[list[str], list[str], list[str]]:
    rows = db.execute(
        select(SourceItem, EventSource.source_role)
        .join(EventSource, EventSource.source_item_id == SourceItem.id)
        .where(EventSource.event_id == event_id, SourceItem.fetch_status != "revoked")
    ).all()
    lines: list[str] = []
    urls: list[str] = []
    ids: list[str] = []
    for item, role in rows:
        ids.append(str(item.id))
        urls.append(item.original_url)
        lines.append(f"[{role}] {item.publisher or 'source'}: {item.original_url}")
    return lines, urls, ids


def load_story(db: Session, article_id: uuid.UUID) -> StoredStory | None:
    row = db.execute(
        select(Article, Event).join(Event, Event.id == Article.event_id).where(Article.id == article_id)
    ).first()
    if row is None:
        return None
    article, event = row
    if event.status != "published":
        return None
    lines, urls, ids = _source_lines(db, event.id)
    return StoredStory(
        article_id=str(article.id),
        event_id=str(event.id),
        date=event.date.isoformat(),
        category=article.category,
        sensitive=bool(event.sensitive or article.sensitive_story),
        text=story_text(article, lines),
        source_urls=urls,
        source_item_ids=ids,
    )


def related_stories(db: Session, focus: StoredStory, limit: int = 2) -> list[StoredStory]:
    event = db.get(Event, uuid.UUID(focus.event_id))
    if event is None:
        return []
    rows = db.execute(
        select(Article, Event)
        .join(Event, Event.id == Article.event_id)
        .where(
            Event.status == "published",
            Article.id != uuid.UUID(focus.article_id),
            Article.category == focus.category,
            Event.date >= event.date - timedelta(days=14),
            Event.date <= event.date + timedelta(days=14),
        )
        .order_by(Event.relevance_score.desc())
        .limit(limit)
    ).all()
    stories: list[StoredStory] = []
    for article, _event in rows:
        loaded = load_story(db, article.id)
        if loaded is not None:
            stories.append(loaded)
    return stories

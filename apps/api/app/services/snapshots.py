"""Article snapshots: a frozen, first-party copy (summary + facts + citation) that
survives later edits of the article. No publisher images or full text."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Article, ArticleSnapshot, Event, EventSource, Source, SourceItem, User
from app.schemas.study import SnapshotFact, SnapshotOut


def snapshot_out(db: Session, snap: ArticleSnapshot, created: bool = False) -> SnapshotOut:
    article = db.get(Article, snap.article_id) if snap.article_id else None
    available = False
    updated_since = False
    if article is not None:
        event = db.get(Event, article.event_id)
        available = bool(event and event.status == "published")
        updated_since = article.updated_at > snap.saved_at
    return SnapshotOut(
        id=snap.id,
        article_id=snap.article_id,
        event_slug=snap.event_slug,
        category=snap.category,
        saved_title=snap.saved_title,
        saved_banglish_summary=snap.saved_banglish_summary,
        saved_key_facts=[SnapshotFact(**f) for f in snap.saved_key_facts or []],
        source_url=snap.source_url,
        source_name=snap.source_name,
        source_published_at=snap.source_published_at,
        verified=snap.verified,
        is_demo=snap.is_demo,
        saved_at=snap.saved_at,
        article_available=available,
        article_updated_since_save=updated_since,
        created=created,
    )


def list_snapshots(db: Session, user: User) -> list[ArticleSnapshot]:
    return list(
        db.scalars(
            select(ArticleSnapshot)
            .where(ArticleSnapshot.user_id == user.id)
            .order_by(ArticleSnapshot.saved_at.desc())
        ).all()
    )


def get_owned(db: Session, user: User, snapshot_id: uuid.UUID) -> ArticleSnapshot | None:
    return db.scalar(
        select(ArticleSnapshot).where(ArticleSnapshot.id == snapshot_id, ArticleSnapshot.user_id == user.id)
    )


def _primary_source(db: Session, event_id: uuid.UUID) -> tuple[SourceItem, Source] | None:
    rows = db.execute(
        select(SourceItem, Source, EventSource.source_role)
        .join(EventSource, EventSource.source_item_id == SourceItem.id)
        .join(Source, Source.id == SourceItem.source_id)
        .where(EventSource.event_id == event_id)
    ).all()
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: (r[2] != "primary", r[1].tier))
    return rows[0][0], rows[0][1]


def save_snapshot(db: Session, user: User, slug: str) -> tuple[ArticleSnapshot, bool]:
    event = db.scalar(select(Event).where(Event.slug == slug, Event.status != "rejected"))
    if event is None:
        raise NotFoundError("Article not found")
    article = db.scalar(select(Article).where(Article.event_id == event.id))
    published = event.status == "published" and article is not None

    if published and article is not None:
        existing = db.scalar(
            select(ArticleSnapshot).where(
                ArticleSnapshot.user_id == user.id, ArticleSnapshot.article_id == article.id
            )
        )
        if existing is not None:
            return existing, False

    primary = _primary_source(db, event.id)
    source_urls: dict[str, str] = {}
    if published and article is not None:
        item_ids = {str(sid) for fact in article.key_facts or [] for sid in fact.get("source_item_ids", [])}
        if item_ids:
            for item in db.scalars(
                select(SourceItem).where(SourceItem.id.in_([uuid.UUID(i) for i in item_ids]))
            ).all():
                source_urls[str(item.id)] = item.original_url

    if published and article is not None:
        facts = [
            {
                "claim": str(f.get("claim", "")),
                "source_url": next(
                    (source_urls[s] for s in map(str, f.get("source_item_ids", [])) if s in source_urls), None
                ),
            }
            for f in (article.key_facts or [])[:5]
        ]
        snap = ArticleSnapshot(
            user_id=user.id,
            article_id=article.id,
            source_item_id=primary[0].id if primary else None,
            event_slug=event.slug,
            category=article.category,
            saved_title=article.headline,
            saved_banglish_summary=article.banglish_summary,
            saved_key_facts=facts,
            source_url=primary[0].original_url if primary else None,
            source_name=(primary[0].publisher or primary[1].name) if primary else None,
            source_published_at=primary[0].published_at if primary else None,
            verified=article.verified_at is not None,
            is_demo=event.is_demo,
        )
    else:
        if primary is None:
            raise NotFoundError("Nothing to save for this item yet")
        item, source = primary
        existing = db.scalar(
            select(ArticleSnapshot).where(
                ArticleSnapshot.user_id == user.id,
                ArticleSnapshot.source_item_id == item.id,
                ArticleSnapshot.article_id.is_(None),
            )
        )
        if existing is not None:
            return existing, False
        snap = ArticleSnapshot(
            user_id=user.id,
            article_id=None,
            source_item_id=item.id,
            event_slug=event.slug,
            category=event.topic,
            saved_title=item.original_title,
            saved_banglish_summary="",
            saved_key_facts=[],
            source_url=item.original_url,
            source_name=item.publisher or source.name,
            source_published_at=item.published_at,
            verified=False,
            is_demo=event.is_demo,
        )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap, True


def delete_snapshot(db: Session, snap: ArticleSnapshot) -> None:
    db.delete(snap)
    db.commit()

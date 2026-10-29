"""Read-side for shared news content. Never calls an AI provider.

Visibility contract:
  * status=published with an article  -> AI article shown ("ready")
  * discovered/queued/generated/needs_review -> ONLY the original source headline +
    short excerpt with an "AI summary pending" label; draft AI text is never exposed
  * rejected -> hidden
"""

from __future__ import annotations

import base64
import json
import uuid
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Article,
    ArticleSnapshot,
    DailyEdition,
    EditionEvent,
    Event,
    EventSource,
    Question,
    Source,
    SourceItem,
    User,
)
from app.schemas.news import (
    ArticleDetail,
    EditionOut,
    KeyFact,
    NewsItem,
    NewsPage,
    SourceRef,
    Verification,
)
from app.services.clock import app_today

VISIBLE_STATUSES = ("published", "discovered", "queued", "generated", "needs_review")
_ROLE_ORDER = {"primary": 0, "supporting": 1, "discovery": 2}


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(json.loads(base64.urlsafe_b64decode(cursor.encode()))["o"]))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return 0


def _sources_for(db: Session, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[SourceRef]]:
    if not event_ids:
        return {}
    rows = db.execute(
        select(EventSource.event_id, EventSource.source_role, SourceItem, Source)
        .join(SourceItem, SourceItem.id == EventSource.source_item_id)
        .join(Source, Source.id == SourceItem.source_id)
        .where(EventSource.event_id.in_(event_ids), SourceItem.fetch_status != "revoked")
    ).all()
    out: dict[uuid.UUID, list[SourceRef]] = defaultdict(list)
    for event_id, role, item, source in rows:
        out[event_id].append(
            SourceRef(
                id=item.id,
                name=item.publisher or source.name,
                url=item.original_url,
                published_at=item.published_at,
                tier=source.tier,
                role=role,
                is_demo=item.is_demo,
            )
        )
    for refs in out.values():
        refs.sort(key=lambda r: (_ROLE_ORDER.get(r.role, 9), r.tier, r.name))
    return out


def _excerpts_for(db: Session, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not event_ids:
        return {}
    rows = db.execute(
        select(EventSource.event_id, SourceItem.short_excerpt, EventSource.source_role)
        .join(SourceItem, SourceItem.id == EventSource.source_item_id)
        .where(EventSource.event_id.in_(event_ids))
    ).all()
    best: dict[uuid.UUID, tuple[int, str]] = {}
    for event_id, excerpt, role in rows:
        if not excerpt:
            continue
        rank = _ROLE_ORDER.get(role, 9)
        if event_id not in best or rank < best[event_id][0]:
            best[event_id] = (rank, excerpt)
    return {k: v[1] for k, v in best.items()}


def _ai_status(event: Event, article: Article | None) -> str:
    if event.status == "published" and article is not None:
        return "ready"
    if event.status in ("generated", "needs_review"):
        return "in_review"
    return "pending"


def _item(
    event: Event,
    article: Article | None,
    sources: list[SourceRef],
    excerpt: str | None,
    saved: bool,
) -> NewsItem:
    status = _ai_status(event, article)
    ready = status == "ready" and article is not None
    primary = sources[0] if sources else None
    return NewsItem(
        event_id=event.id,
        slug=event.slug,
        category=(article.category if ready and article else event.topic),
        date=event.date,
        status=event.status,
        ai_status=status,
        headline=article.headline if ready and article else event.title,
        tldr=(article.banglish_summary if ready and article else (excerpt or "")),
        exam_tags=list(article.exam_tags or []) if ready and article else [],
        relevance_score=round(event.relevance_score, 1),
        importance_score=article.importance_score if ready and article else None,
        sensitive=event.sensitive or bool(ready and article and article.sensitive_story),
        is_demo=event.is_demo,
        correction_status=event.correction_status,
        source_count=len(sources),
        primary_source=primary,
        last_updated_at=max(event.updated_at, article.updated_at) if ready and article else event.updated_at,
        saved=saved,
    )


def _saved_article_ids(db: Session, user: User | None, article_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if user is None or not article_ids:
        return set()
    rows = db.scalars(
        select(ArticleSnapshot.article_id).where(
            ArticleSnapshot.user_id == user.id, ArticleSnapshot.article_id.in_(article_ids)
        )
    ).all()
    return {r for r in rows if r is not None}


def build_items(db: Session, pairs: list[tuple[Event, Article | None]], user: User | None) -> list[NewsItem]:
    event_ids = [e.id for e, _ in pairs]
    sources = _sources_for(db, event_ids)
    excerpts = _excerpts_for(db, event_ids)
    saved = _saved_article_ids(db, user, [a.id for _, a in pairs if a is not None])
    return [
        _item(e, a, sources.get(e.id, []), excerpts.get(e.id), bool(a and a.id in saved)) for e, a in pairs
    ]


def _base_query(include_demo: bool) -> Any:
    stmt = (
        select(Event, Article)
        .outerjoin(Article, Article.event_id == Event.id)
        .where(Event.status.in_(VISIBLE_STATUSES))
    )
    if not include_demo:
        stmt = stmt.where(Event.is_demo.is_(False))
    return stmt


def list_news(
    db: Session,
    *,
    user: User | None,
    day: date | None = None,
    category: str | None = None,
    exam: str | None = None,
    importance: str | None = None,
    region: str | None = None,
    q: str | None = None,
    kind: str = "all",
    include_demo: bool | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> NewsPage:
    include_demo = get_settings().demo_mode if include_demo is None else include_demo
    stmt = _base_query(include_demo)
    if day:
        stmt = stmt.where(Event.date == day)
    if category:
        stmt = stmt.where(Event.topic == category)
    if region in ("india", "world"):
        stmt = stmt.where(Event.region == region)
    if importance == "high":
        stmt = stmt.where(Event.relevance_score >= 70)
    elif importance == "medium":
        stmt = stmt.where(Event.relevance_score >= 40)
    if kind == "ai":
        stmt = stmt.where(Event.status == "published", Article.id.is_not(None))
    elif kind == "source":
        stmt = stmt.where(Event.status != "published")
    if exam:
        stmt = stmt.where(Event.status == "published", Article.exam_tags.contains([exam.upper()]))
    if q:
        term = f"%{q.strip()[:80]}%"
        stmt = stmt.where(
            or_(
                Event.title.ilike(term),
                (Event.status == "published") & Article.headline.ilike(term),
                (Event.status == "published") & Article.neutral_summary.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    offset = decode_cursor(cursor)
    limit = max(1, min(limit, 50))
    rows = db.execute(
        stmt.order_by(Event.date.desc(), Event.relevance_score.desc(), Event.id).offset(offset).limit(limit)
    ).all()
    items = build_items(db, [(r[0], r[1]) for r in rows], user)
    next_cursor = encode_cursor(offset + limit) if offset + limit < total else None
    return NewsPage(items=items, next_cursor=next_cursor, total=total)


def get_article(db: Session, slug: str, user: User | None) -> ArticleDetail | None:
    row = db.execute(_base_query(include_demo=True).where(Event.slug == slug)).first()
    if row is None:
        return None
    event, article = row[0], row[1]
    base = build_items(db, [(event, article)], user)[0]
    sources = _sources_for(db, [event.id]).get(event.id, [])
    ready = base.ai_status == "ready" and article is not None

    snapshot_id = None
    if user is not None and article is not None:
        snapshot_id = db.scalar(
            select(ArticleSnapshot.id).where(
                ArticleSnapshot.user_id == user.id, ArticleSnapshot.article_id == article.id
            )
        )
    practice = 0
    if ready and article is not None:
        practice = (
            db.scalar(
                select(func.count(Question.id)).where(
                    Question.article_id == article.id, Question.validation_status == "validated"
                )
            )
            or 0
        )

    flags = (article.confidence_flags or {}) if ready and article else {}
    return ArticleDetail(
        **base.model_dump(),
        neutral_summary=article.neutral_summary if ready and article else None,
        banglish_summary=article.banglish_summary if ready and article else None,
        why_matters=article.why_matters if ready and article else None,
        context=article.context if ready and article else None,
        key_facts=[
            KeyFact(
                claim=str(f.get("claim", "")), source_item_ids=[str(s) for s in f.get("source_item_ids", [])]
            )
            for f in (article.key_facts if ready and article else [])
        ],
        mnemonics=[str(m) for m in (article.mnemonics if ready and article else [])],
        uncertainties=[str(u) for u in flags.get("uncertainties", [])],
        verification=Verification(
            verified_at=article.verified_at,
            method=article.verification_method,
            ai_provider=article.ai_provider,
            ai_model=article.ai_model,
            prompt_version=article.prompt_version,
        )
        if ready and article
        else None,
        sources=sources,
        relevance_reasons=[str(r) for r in (event.relevance_reasons or [])],
        correction_note=event.correction_note,
        practice_question_count=practice,
        snapshot_id=snapshot_id,
    )


def get_today_edition(db: Session, user: User | None) -> EditionOut:
    settings = get_settings()
    today = app_today()
    edition = db.scalar(
        select(DailyEdition).where(
            DailyEdition.edition_date == today,
            DailyEdition.timezone == settings.app_timezone,
            DailyEdition.status == "published",
        )
    )
    is_fallback = False
    if edition is None:
        is_fallback = True
        edition = db.scalar(
            select(DailyEdition)
            .where(DailyEdition.status == "published", DailyEdition.timezone == settings.app_timezone)
            .order_by(DailyEdition.edition_date.desc())
            .limit(1)
        )

    if edition is not None:
        rows = db.execute(
            select(Event, Article)
            .join(EditionEvent, EditionEvent.event_id == Event.id)
            .outerjoin(Article, Article.event_id == Event.id)
            .where(EditionEvent.edition_id == edition.id, Event.status.in_(VISIBLE_STATUSES))
            .order_by(EditionEvent.ranking)
        ).all()
        items = build_items(db, [(r[0], r[1]) for r in rows], user)
        return EditionOut(
            id=edition.id,
            edition_date=edition.edition_date,
            timezone=edition.timezone,
            title=edition.title,
            is_demo=edition.is_demo,
            is_fallback=is_fallback,
            published_at=edition.published_at,
            items=items,
            generated_count=sum(1 for i in items if i.ai_status == "ready"),
            pending_count=sum(1 for i in items if i.ai_status != "ready"),
        )

    page = list_news(db, user=user, limit=20)
    return EditionOut(
        id=None,
        edition_date=today,
        timezone=settings.app_timezone,
        title=None,
        is_demo=any(i.is_demo for i in page.items),
        is_fallback=True,
        published_at=None,
        items=page.items,
        generated_count=sum(1 for i in page.items if i.ai_status == "ready"),
        pending_count=sum(1 for i in page.items if i.ai_status != "ready"),
    )

"""Daily edition: 15-25 curated items. Published AI articles first, then clearly
labelled source-only headlines ("AI summary pending") when generation lags."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DailyEdition, EditionEvent, Event, utcnow
from app.services.clock import app_today

TARGET_MIN = 15
TARGET_MAX = 25
MAX_PER_TOPIC = 6
SOURCE_ONLY_MIN_SCORE = 30.0
DEMO_FILL_THRESHOLD = 6


def build_edition(db: Session, settings: Settings, now: datetime | None = None) -> DailyEdition | None:
    now = now or utcnow()
    today = app_today(now)
    recent = db.scalars(
        select(Event)
        .where(
            Event.is_demo.is_(False),
            Event.date >= today - timedelta(days=1),
            Event.status.in_(("published", "discovered", "queued", "generated", "needs_review")),
        )
        .order_by(Event.relevance_score.desc())
    ).all()

    chosen: list[Event] = []
    per_topic: dict[str, int] = defaultdict(int)

    def take(events: list[Event], limit: int) -> None:
        for event in events:
            if len(chosen) >= limit:
                return
            if event in chosen or per_topic[event.topic] >= MAX_PER_TOPIC:
                continue
            chosen.append(event)
            per_topic[event.topic] += 1

    take([e for e in recent if e.status == "published"], TARGET_MAX)
    if len(chosen) < TARGET_MIN:
        take(
            [e for e in recent if e.status != "published" and e.relevance_score >= SOURCE_ONLY_MIN_SCORE],
            TARGET_MAX,
        )

    real_items = len(chosen)
    if settings.demo_mode and len(chosen) < DEMO_FILL_THRESHOLD:
        demo = db.scalars(
            select(Event)
            .where(Event.is_demo.is_(True), Event.status == "published")
            .order_by(Event.relevance_score.desc())
        ).all()
        take(list(demo), max(len(chosen) + len(demo), TARGET_MIN))
    if not chosen:
        return None

    edition = db.scalar(
        select(DailyEdition).where(
            DailyEdition.edition_date == today, DailyEdition.timezone == settings.app_timezone
        )
    )
    if edition is None:
        edition = DailyEdition(edition_date=today, timezone=settings.app_timezone)
        db.add(edition)
        db.flush()
    edition.status = "published"
    edition.published_at = edition.published_at or now
    edition.is_demo = real_items == 0
    edition.title = (
        "DEMO edition - evergreen explainers (not today's news)"
        if edition.is_demo
        else ("Aajke-r edition" + (" + DEMO explainers" if len(chosen) > real_items else ""))
    )
    db.execute(delete(EditionEvent).where(EditionEvent.edition_id == edition.id))
    for rank, event in enumerate(chosen, start=1):
        db.add(EditionEvent(edition_id=edition.id, event_id=event.id, ranking=rank))
    db.commit()
    return edition

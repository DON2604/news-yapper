"""Overnight prep: once local time (APP_TIMEZONE) passes NIGHTLY_PREP_HOUR the coordinator fetches
every enabled source, gives recent stories whose AI rewrite failed one more chance and queues the
Banglish rewrite, so the morning edition is already stored when readers open the app.

Runs once per local day. If the worker was down at that hour it runs as soon as it is back."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Event, WorkerLease
from app.services.clock import local_date, tz
from pipeline.generate import FAILED_NOTE, plan_news_jobs
from pipeline.ingest import run_ingestion

MARKER = "nightly_prep"
TRIGGER = "nightly"


def prep_window_start(settings: Settings, now: datetime) -> datetime | None:
    zone = tz(settings.app_timezone)
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time(hour=settings.nightly_prep_hour), tzinfo=zone)
    return start.astimezone(UTC) if local >= start else None


def prep_due(db: Session, settings: Settings, now: datetime) -> bool:
    if not settings.nightly_prep_enabled or prep_window_start(settings, now) is None:
        return False
    marker = db.get(WorkerLease, MARKER)
    today = local_date(now, settings.app_timezone).isoformat()
    return marker is None or (marker.info or {}).get("date") != today


def reopen_failed(db: Session, settings: Settings, now: datetime) -> int:
    today = local_date(now, settings.app_timezone)
    events = db.scalars(
        select(Event).where(
            Event.is_demo.is_(False),
            Event.status == "discovered",
            Event.date >= today - timedelta(days=settings.ai_news_lookback_days),
            Event.review_note.like(f"{FAILED_NOTE}%"),
        )
    ).all()
    for event in events:
        event.review_note = None
    db.commit()
    return len(events)


def _mark_done(db: Session, settings: Settings, now: datetime, report: dict[str, Any]) -> None:
    info = {
        "date": local_date(now, settings.app_timezone).isoformat(),
        "finished_at": now.isoformat(),
        **report,
    }
    db.execute(
        insert(WorkerLease)
        .values(name=MARKER, owner=TRIGGER, lease_until=now, heartbeat_at=now, info=info)
        .on_conflict_do_update(
            index_elements=["name"], set_={"lease_until": now, "heartbeat_at": now, "info": info}
        )
    )
    db.commit()


def run_nightly_prep(
    session_factory: Callable[[], Session], settings: Settings, now: datetime
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    if settings.enable_live_ingestion:
        summary = run_ingestion(session_factory, settings, trigger=TRIGGER, now=now)
        report["ingested"] = summary.inserted
        report["source_errors"] = [o.slug for o in summary.outcomes if o.error]
    with session_factory() as db:
        report["reopened"] = reopen_failed(db, settings, now)
        report["planned_news_jobs"] = plan_news_jobs(db, settings, now)
        _mark_done(db, settings, now, report)
    return report

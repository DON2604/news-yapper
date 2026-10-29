from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.db import SessionLocal
from app.models import AIJob, Event
from pipeline.generate import FAILED_NOTE
from pipeline.nightly import prep_due, run_nightly_prep

KOLKATA = ZoneInfo("Asia/Kolkata")


def _local(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 15, hour, minute, tzinfo=KOLKATA).astimezone(UTC)


def test_prep_waits_for_the_configured_hour_then_runs_once_per_day(ai_settings):
    settings = ai_settings(app_timezone="Asia/Kolkata", nightly_prep_hour=2, enable_live_ingestion=False)
    with SessionLocal() as db:
        assert not prep_due(db, settings, _local(1, 59))
        assert prep_due(db, settings, _local(2, 0))
    run_nightly_prep(SessionLocal, settings, _local(2, 0))
    with SessionLocal() as db:
        assert not prep_due(db, settings, _local(9, 30))
        assert not prep_due(db, settings, _local(23, 59))


def test_prep_can_be_switched_off(ai_settings):
    settings = ai_settings(nightly_prep_enabled=False)
    with SessionLocal() as db:
        assert not prep_due(db, settings, _local(3, 0))


def test_prep_reopens_failed_stories_and_queues_rewrites(ai_settings, make_event):
    settings = ai_settings(app_timezone="Asia/Kolkata", enable_live_ingestion=False)
    now = _local(2, 5)
    event = make_event(day=now.astimezone(KOLKATA).date())
    with SessionLocal() as db:
        db.get(Event, event.id).review_note = f"{FAILED_NOTE}: max_attempts"
        db.commit()

    report = run_nightly_prep(SessionLocal, settings, now)

    assert report["reopened"] == 1
    assert report["planned_news_jobs"] == 1
    with SessionLocal() as db:
        refreshed = db.get(Event, event.id)
        assert refreshed.review_note is None and refreshed.status == "queued"
        assert db.query(AIJob).filter(AIJob.kind == "news_batch").count() == 1

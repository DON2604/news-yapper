"""Aajke Ki Scene worker - the single project-wide coordinator.

uv run python -m worker run                 # loop: ingest (if enabled) -> plan -> AI queue -> edition
uv run python -m worker tick                # one coordinator tick
uv run python -m worker ingest [--source pib] [--allow-live]
uv run python -m worker ai [--max-jobs 3]
uv run python -m worker edition
uv run python -m worker sync-models         # verify configured model IDs against provider listings
uv run python -m worker status
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import AIJob, IngestionRun, Source, WorkerLease, utcnow
from pipeline.ai_orchestrator import AIOrchestrator, default_owner
from pipeline.editions import build_edition
from pipeline.generate import plan_news_jobs
from pipeline.ingest import run_ingestion

log = logging.getLogger("aks.worker")
LEASE_NAME = "coordinator"
LEASE_TTL = timedelta(seconds=90)
TICK_SECONDS = 15
EDITION_EVERY = timedelta(minutes=10)


def acquire_lease(owner: str, now: datetime | None = None, info: dict[str, Any] | None = None) -> bool:
    now = now or utcnow()
    with SessionLocal() as db:
        stmt = (
            insert(WorkerLease)
            .values(
                name=LEASE_NAME, owner=owner, lease_until=now + LEASE_TTL, heartbeat_at=now, info=info or {}
            )
            .on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "owner": owner,
                    "lease_until": now + LEASE_TTL,
                    "heartbeat_at": now,
                    "info": info or {},
                },
                where=(WorkerLease.lease_until < now) | (WorkerLease.owner == owner),
            )
            .returning(WorkerLease.owner)
        )
        holder = db.execute(stmt).scalar_one_or_none()
        db.commit()
        return holder == owner


def release_lease(owner: str) -> None:
    with SessionLocal() as db:
        lease = db.get(WorkerLease, LEASE_NAME)
        if lease is not None and lease.owner == owner:
            lease.lease_until = utcnow()
            db.commit()


def process_requested_ingestion(settings: Settings) -> int:
    with SessionLocal() as db:
        runs = db.scalars(
            select(IngestionRun).where(IngestionRun.status == "requested").order_by(IngestionRun.created_at)
        ).all()
        requests = [(r.id, r.source_id, r.requested_by) for r in runs]
    handled = 0
    for run_id, source_id, requested_by in requests:
        with SessionLocal() as db:
            run = db.get(IngestionRun, run_id)
            if run is None:
                continue
            if not settings.enable_live_ingestion:
                run.status = "skipped"
                run.error_details = [{"error": "ENABLE_LIVE_INGESTION=false"}]
                run.ended_at = utcnow()
                db.commit()
                continue
            slug = db.scalar(select(Source.slug).where(Source.id == source_id)) if source_id else None
            run.status = "running"
            run.started_at = utcnow()
            db.commit()
        summary = run_ingestion(
            SessionLocal,
            settings,
            source_slugs=[slug] if slug else None,
            trigger="admin",
            requested_by=requested_by,
        )
        with SessionLocal() as db:
            run = db.get(IngestionRun, run_id)
            if run is not None:
                errors = [{"source": o.slug, "error": o.error} for o in summary.outcomes if o.error]
                run.status = (
                    "partial"
                    if errors and len(errors) < len(summary.outcomes)
                    else ("failed" if errors else "succeeded")
                )
                run.fetched_count = sum(o.fetched for o in summary.outcomes)
                run.inserted_count = summary.inserted
                run.duplicate_count = sum(o.duplicates for o in summary.outcomes)
                run.clustered_count = sum(o.new_events + o.attached for o in summary.outcomes)
                run.error_details = errors
                run.ended_at = utcnow()
                db.commit()
        handled += 1
    return handled


class Coordinator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.owner = default_owner()
        self.orchestrator = AIOrchestrator(SessionLocal, settings, owner=self.owner)
        self.last_edition: datetime | None = None

    def tick(self) -> dict[str, Any]:
        now = utcnow()
        report: dict[str, Any] = {}
        report["admin_ingestion_runs"] = process_requested_ingestion(self.settings)
        if self.settings.enable_live_ingestion:
            summary = run_ingestion(SessionLocal, self.settings, only_due=True)
            report["ingested"] = summary.inserted
            if summary.outcomes:
                self.last_edition = None
        with SessionLocal() as db:
            report["planned_news_jobs"] = plan_news_jobs(db, self.settings, now)
        report["jobs"] = [o.status for o in self.orchestrator.run_once(max_jobs=3)]
        if self.last_edition is None or now - self.last_edition >= EDITION_EVERY or report["jobs"]:
            with SessionLocal() as db:
                edition = build_edition(db, self.settings, now)
            report["edition_items"] = len(edition.items) if edition is not None else 0
            self.last_edition = now
        return report

    def run_forever(self) -> None:
        stop = {"flag": False}

        def _stop(*_: object) -> None:
            stop["flag"] = True

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
        log.info(
            "Worker %s started (live_ingestion=%s, providers=%s)",
            self.owner,
            self.settings.enable_live_ingestion,
            list(self.orchestrator.providers) or "none - source-only/offline mode",
        )
        try:
            while not stop["flag"]:
                info = {
                    "providers": list(self.orchestrator.providers),
                    "live": self.settings.enable_live_ingestion,
                }
                if acquire_lease(self.owner, info=info):
                    try:
                        report = self.tick()
                        if any(
                            report.get(k)
                            for k in ("ingested", "planned_news_jobs", "jobs", "admin_ingestion_runs")
                        ):
                            log.info("tick: %s", report)
                    except Exception:  # noqa: BLE001 - keep the coordinator alive
                        log.exception("Coordinator tick failed")
                else:
                    log.debug("Another coordinator holds the lease; standing by.")
                for _ in range(TICK_SECONDS):
                    if stop["flag"]:
                        break
                    time.sleep(1)
        finally:
            release_lease(self.owner)
            log.info("Worker stopped.")


def status() -> dict[str, Any]:
    with SessionLocal() as db:
        jobs = dict(db.execute(select(AIJob.status, func.count()).group_by(AIJob.status)).all())
        lease = db.get(WorkerLease, LEASE_NAME)
        return {
            "jobs": jobs,
            "coordinator": {"owner": lease.owner, "lease_until": str(lease.lease_until)} if lease else None,
        }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="worker")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run")
    sub.add_parser("tick")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--source", action="append", dest="sources")
    ingest.add_argument("--allow-live", action="store_true", help="operator consent for a one-off live fetch")
    ai = sub.add_parser("ai")
    ai.add_argument("--max-jobs", type=int, default=3)
    sub.add_parser("edition")
    sub.add_parser("sync-models")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "run":
        Coordinator(settings).run_forever()
        return 0
    if args.command == "tick":
        print(json.dumps(Coordinator(settings).tick(), default=str, indent=2))
        return 0
    if args.command == "ingest":
        if not (settings.enable_live_ingestion or args.allow_live):
            print(
                "Live ingestion is disabled. Set ENABLE_LIVE_INGESTION=true or pass --allow-live.",
                file=sys.stderr,
            )
            return 2
        summary = run_ingestion(SessionLocal, settings, source_slugs=args.sources, trigger="cli")
        for o in summary.outcomes:
            print(
                f"{o.slug:16} fetched={o.fetched:<4} new={o.inserted:<4} dup={o.duplicates:<4} "
                f"events+={o.new_events:<3} attached={o.attached:<3} {('ERROR ' + o.error) if o.error else 'ok'}"
            )
        with SessionLocal() as db:
            build_edition(db, settings)
        return 0
    if args.command == "ai":
        outcomes = AIOrchestrator(SessionLocal, settings).run_once(max_jobs=args.max_jobs)
        print(json.dumps([o.__dict__ for o in outcomes], default=str, indent=2))
        return 0
    if args.command == "edition":
        with SessionLocal() as db:
            edition = build_edition(db, settings)
            print(
                f"Edition {edition.edition_date} with {len(edition.items)} items"
                if edition
                else "Nothing to publish"
            )
        return 0
    if args.command == "sync-models":
        print(json.dumps(AIOrchestrator(SessionLocal, settings).sync_models(), indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(status(), default=str, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

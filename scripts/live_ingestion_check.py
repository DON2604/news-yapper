"""Verify the live feeds end to end without touching your data.

Creates a temporary database next to DATABASE_URL, migrates it, runs one real ingestion
for the chosen sources, prints what happened, then drops the temporary database.
Credentials come from the normal settings loader and are never printed.

    uv run python scripts/live_ingestion_check.py rbi-press un-news pib gdelt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import get_engine, normalize_database_url
from app.models import EditionEvent, Event
from app.seed.sources import seed_sources
from pipeline.editions import build_edition
from pipeline.ingest import run_ingestion

TEMP_DB = "aajke_live_check"
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+", help="source slugs, e.g. rbi-press un-news pib gdelt")
    args = parser.parse_args()

    settings = get_settings()
    base = make_url(normalize_database_url(settings.direct_url or settings.database_url))
    admin_dsn = base.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    temp_url = base.set(database=TEMP_DB).render_as_string(hide_password=False)

    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEMP_DB}"')
        conn.execute(f'CREATE DATABASE "{TEMP_DB}"')
    try:
        cfg = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
        cfg.cmd_opts = argparse.Namespace(x=[f"url={temp_url}"])
        command.upgrade(cfg, "head")
        session_factory = sessionmaker(bind=get_engine(temp_url), expire_on_commit=False)
        with session_factory() as db:
            seed_sources(db)
            db.commit()

        summary = run_ingestion(session_factory, settings, source_slugs=args.sources, trigger="cli")
        for o in summary.outcomes:
            status = f"ERROR {o.error}" if o.error else "ok"
            print(
                f"{o.slug:12} fetched={o.fetched:<3} new={o.inserted:<3} events+={o.new_events:<3} attached={o.attached:<3} {status}"
            )

        with session_factory() as db:
            build_edition(db, settings)
            print("\nTop events by heuristic relevance:")
            rows = db.execute(
                select(Event.relevance_score, Event.topic, Event.region, Event.sensitive, Event.title)
                .order_by(Event.relevance_score.desc())
                .limit(8)
            ).all()
            for score, topic, region, sensitive, title in rows:
                flag = "SENSITIVE " if sensitive else ""
                print(f"  {score:5.1f}  {topic:13} {region:5}  {flag}{title[:88]}")
            events = db.scalar(select(func.count(Event.id)))
            items = db.scalar(select(func.count()).select_from(EditionEvent))
            print(f"\n{events} events, {items} in today's edition")
    finally:
        get_engine(temp_url).dispose()
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{TEMP_DB}"')
        print("temporary database dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

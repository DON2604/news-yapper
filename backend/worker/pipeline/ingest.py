"""Ingestion run: fetch (concurrently, per-host paced) -> normalise -> upsert raw metadata ->
cluster -> score. No AI calls happen here."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.base import RawItem, SourceConfig
from adapters.http import FetchError, SafeFetcher
from adapters.registry import adapter_for
from app.config import Settings
from app.models import Event, EventSource, IngestionRun, Source, SourceItem, utcnow
from pipeline.deduplicate import cluster_items
from pipeline.normalize import NormalizedItem, normalize_item, normalize_title
from pipeline.relevance import score

log = logging.getLogger("aks.ingest")
FetcherFactory = Callable[[set[str]], SafeFetcher]
HOST_INTERVALS = {"api.gdeltproject.org": 6.0}


@dataclass
class SourceOutcome:
    slug: str
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    corrected: int = 0
    new_events: int = 0
    attached: int = 0
    error: str | None = None


@dataclass
class IngestionSummary:
    outcomes: list[SourceOutcome] = field(default_factory=list)

    @property
    def inserted(self) -> int:
        return sum(o.inserted for o in self.outcomes)


def source_config(source: Source) -> SourceConfig:
    return SourceConfig(
        id=source.id,
        slug=source.slug,
        name=source.name,
        type=source.type,
        feed_url=source.feed_url,
        home_url=source.home_url,
        country=source.country,
        language=source.language,
        config=dict(source.config or {}),
        last_success_at=source.last_success_at,
    )


def default_fetcher_factory(settings: Settings) -> FetcherFactory:
    def factory(hosts: set[str]) -> SafeFetcher:
        return SafeFetcher(
            user_agent=settings.ingestion_user_agent, allowed_hosts=hosts, host_intervals=HOST_INTERVALS
        )

    return factory


def is_due(source: Source, now: datetime) -> bool:
    if source.last_fetch_at is None:
        return True
    backoff = 2 ** min(source.consecutive_failures, 4)
    return now - source.last_fetch_at >= timedelta(minutes=source.fetch_interval_minutes * backoff)


def _store(
    db: Session, source: Source, items: list[NormalizedItem], outcome: SourceOutcome
) -> list[SourceItem]:
    fresh: list[SourceItem] = []
    seen: set[str] = set()
    for item in items:
        if item.canonical_url in seen:
            outcome.duplicates += 1
            continue
        seen.add(item.canonical_url)
        existing = db.scalar(select(SourceItem).where(SourceItem.canonical_url == item.canonical_url))
        if existing is not None:
            outcome.duplicates += 1
            if normalize_title(existing.original_title) != normalize_title(item.title):
                _record_correction(db, existing, item)
                outcome.corrected += 1
            continue
        row = SourceItem(
            source_id=source.id,
            canonical_url=item.canonical_url,
            original_url=item.original_url,
            original_title=item.title,
            short_excerpt=item.excerpt,
            publisher=item.publisher,
            author=item.author,
            published_at=item.published_at,
            language=item.language,
            country=item.country,
            tags=item.tags,
            item_metadata=item.metadata,
            content_hash=item.content_hash,
            fetch_status="new",
            rights_notes="Metadata + short excerpt only; see source legal notes.",
        )
        db.add(row)
        fresh.append(row)
    db.flush()
    outcome.inserted = len(fresh)
    return fresh


def _record_correction(db: Session, existing: SourceItem, item: NormalizedItem) -> None:
    """Publisher changed the headline of a URL we already hold: keep history, flag the event."""
    meta: dict[str, Any] = dict(existing.item_metadata or {})
    history = list(meta.get("title_history", []))
    history.append({"title": existing.original_title, "replaced_at": utcnow().isoformat()})
    meta["title_history"] = history[-5:]
    existing.item_metadata = meta
    existing.original_title = item.title
    existing.short_excerpt = item.excerpt or existing.short_excerpt
    for event in db.scalars(
        select(Event)
        .join(EventSource, EventSource.event_id == Event.id)
        .where(EventSource.source_item_id == existing.id)
    ).all():
        if event.status == "published":
            event.correction_status = "corrected"
            event.correction_note = (
                f"Source headline updated by the publisher on {utcnow().date().isoformat()}."
            )
        else:
            event.title = item.title


def rescore(db: Session, event_ids: set[Any], now: datetime) -> None:
    if not event_ids:
        return
    rows = db.execute(
        select(Event, SourceItem, Source)
        .join(EventSource, EventSource.event_id == Event.id)
        .join(SourceItem, SourceItem.id == EventSource.source_item_id)
        .join(Source, Source.id == SourceItem.source_id)
        .where(Event.id.in_(event_ids))
    ).all()
    grouped: dict[Any, list[tuple[SourceItem, Source]]] = {}
    events: dict[Any, Event] = {}
    for event, item, source in rows:
        grouped.setdefault(event.id, []).append((item, source))
        events[event.id] = event
    for event_id, pairs in grouped.items():
        event = events[event_id]
        primary_source = pairs[0][1]
        result = score(
            titles=[i.original_title for i, _ in pairs],
            excerpts=[i.short_excerpt or "" for i, _ in pairs],
            tiers=[s.tier for _, s in pairs],
            authority=[s.authority_weight for _, s in pairs],
            publishers={(i.publisher or s.name).lower() for i, s in pairs},
            latest=max((i.published_at or i.discovered_at) for i, _ in pairs),
            now=now,
            default_topic=primary_source.default_topic,
            source_country=primary_source.country,
        )
        event.relevance_score = result.score
        event.relevance_reasons = result.reasons
        event.sensitive = result.sensitive
        event.region = result.region
        if event.status in ("discovered", "queued"):
            event.topic = result.category


def run_ingestion(
    session_factory: Callable[[], Session],
    settings: Settings,
    *,
    source_slugs: list[str] | None = None,
    trigger: str = "schedule",
    requested_by: Any = None,
    only_due: bool = False,
    fetcher_factory: FetcherFactory | None = None,
    now: datetime | None = None,
) -> IngestionSummary:
    now = now or utcnow()
    summary = IngestionSummary()
    with session_factory() as db:
        stmt = select(Source).where(Source.enabled.is_(True), Source.type.in_(("rss", "gdelt")))
        if source_slugs:
            stmt = stmt.where(Source.slug.in_(source_slugs))
        sources = [s for s in db.scalars(stmt).all() if not only_due or is_due(s, now)]
        configs = [source_config(s) for s in sources]

    if not configs:
        return summary

    hosts = {(urlsplit(c.feed_url).hostname or "").lower() for c in configs if c.feed_url}
    factory = fetcher_factory or default_fetcher_factory(settings)
    fetcher = factory(hosts)

    def fetch(cfg: SourceConfig) -> tuple[SourceConfig, list[RawItem] | None, str | None]:
        adapter = adapter_for(cfg)
        if adapter is None:
            return cfg, None, f"No adapter for source type {cfg.type}"
        try:
            return cfg, adapter.fetch(cfg, fetcher, now), None
        except FetchError as exc:
            return cfg, None, f"{exc.kind}: {exc}"
        except Exception as exc:  # noqa: BLE001 - one broken feed must not stop the run
            log.exception("Unexpected adapter failure for %s", cfg.slug)
            return cfg, None, f"unexpected: {exc.__class__.__name__}: {exc}"

    try:
        with ThreadPoolExecutor(max_workers=min(4, len(configs))) as pool:
            results = list(pool.map(fetch, configs))
    finally:
        fetcher.close()

    for cfg, raws, error in results:
        outcome = SourceOutcome(slug=cfg.slug)
        summary.outcomes.append(outcome)
        with session_factory() as db:
            source = db.get(Source, cfg.id)
            if source is None:
                continue
            run = IngestionRun(
                source_id=source.id,
                status="running",
                trigger=trigger,
                requested_by=requested_by,
                started_at=now,
            )
            db.add(run)
            source.last_fetch_at = now
            if error is not None or raws is None:
                outcome.error = error
                source.last_error = (error or "unknown error")[:500]
                source.consecutive_failures += 1
                run.status = "failed"
                run.error_details = [{"source": cfg.slug, "error": outcome.error}]
                run.ended_at = utcnow()
                db.commit()
                log.warning("Ingestion failed for %s: %s", cfg.slug, error)
                continue

            outcome.fetched = len(raws)
            normalized = [n for n in (normalize_item(r, cfg, now) for r in raws) if n is not None]
            fresh = _store(db, source, normalized, outcome)
            stats = cluster_items(db, fresh, {source.id: source}, now)
            outcome.new_events, outcome.attached = stats.new_events, stats.attached
            touched = set(
                db.scalars(
                    select(EventSource.event_id).where(EventSource.source_item_id.in_([f.id for f in fresh]))
                ).all()
            )
            rescore(db, touched, now)
            source.last_success_at = now
            source.last_error = None
            source.consecutive_failures = 0
            run.status = "succeeded"
            run.fetched_count = outcome.fetched
            run.inserted_count = outcome.inserted
            run.duplicate_count = outcome.duplicates
            run.clustered_count = stats.new_events + stats.attached
            run.ended_at = utcnow()
            db.commit()
            log.info(
                "Ingested %s: fetched=%d new=%d dup=%d events+=%d",
                cfg.slug,
                outcome.fetched,
                outcome.inserted,
                outcome.duplicates,
                stats.new_events,
            )
    return summary

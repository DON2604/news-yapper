"""Cluster source items into events: exact URL (unique key) -> content fingerprint ->
fuzzy headline similarity within a time window. Every supporting URL is retained."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventSource, Source, SourceItem
from app.services.clock import local_date
from pipeline.normalize import normalize_title, title_tokens

JACCARD_THRESHOLD = 0.55
SEQUENCE_THRESHOLD = 0.82
CLUSTER_WINDOW = timedelta(hours=48)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def title_similarity(a: str, b: str) -> float:
    ja = jaccard(title_tokens(a), title_tokens(b))
    seq = SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()
    return max(ja, seq if seq >= SEQUENCE_THRESHOLD else 0.0)


def is_same_story(a: str, b: str) -> bool:
    return title_similarity(a, b) >= JACCARD_THRESHOLD


def slugify(text: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "story"


@dataclass
class Candidate:
    event: Event
    titles: list[str]
    when: datetime
    source_ids: set[object]


@dataclass
class ClusterStats:
    new_events: int = 0
    attached: int = 0


def item_time(item: SourceItem) -> datetime:
    return item.published_at or item.discovered_at


def _candidates(db: Session, now: datetime) -> list[Candidate]:
    since = now - timedelta(hours=72)
    rows = db.execute(
        select(Event, SourceItem)
        .join(EventSource, EventSource.event_id == Event.id)
        .join(SourceItem, SourceItem.id == EventSource.source_item_id)
        .where(Event.status != "rejected", Event.is_demo.is_(False), Event.updated_at >= since)
    ).all()
    grouped: dict[object, Candidate] = {}
    for event, item in rows:
        cand = grouped.get(event.id)
        when = item_time(item)
        if cand is None:
            grouped[event.id] = Candidate(
                event=event, titles=[item.original_title], when=when, source_ids={item.source_id}
            )
        else:
            cand.titles.append(item.original_title)
            cand.when = max(cand.when, when)
            cand.source_ids.add(item.source_id)
    return list(grouped.values())


def cluster_items(
    db: Session, items: list[SourceItem], sources: dict[object, Source], now: datetime
) -> ClusterStats:
    stats = ClusterStats()
    candidates = _candidates(db, now)
    by_hash: dict[str, Event] = {}
    for item in sorted(items, key=item_time):
        when = item_time(item)
        match: Event | None = None

        existing = by_hash.get(item.content_hash)
        if existing is None:
            existing = db.scalar(
                select(Event)
                .join(EventSource, EventSource.event_id == Event.id)
                .join(SourceItem, SourceItem.id == EventSource.source_item_id)
                .where(
                    SourceItem.content_hash == item.content_hash,
                    SourceItem.id != item.id,
                    Event.is_demo.is_(False),
                )
                .limit(1)
            )
        if existing is not None:
            match = existing
        else:
            best_score = 0.0
            for cand in candidates:
                # A publisher's own templated titles ("penalty on bank X" / "on bank Y") are
                # distinct events; fuzzy clustering only merges coverage across sources.
                if abs(cand.when - when) > CLUSTER_WINDOW or item.source_id in cand.source_ids:
                    continue
                s = max(title_similarity(item.original_title, t) for t in cand.titles)
                if s >= JACCARD_THRESHOLD and s > best_score:
                    best_score, match = s, cand.event

        source = sources.get(item.source_id)
        if match is not None:
            db.add(EventSource(event_id=match.id, source_item_id=item.id, source_role="supporting"))
            match.last_source_at = max(filter(None, [match.last_source_at, when]))
            if source is not None and source.tier == "A" and match.status == "discovered":
                match.title = item.original_title
            stats.attached += 1
            for cand in candidates:
                if cand.event.id == match.id:
                    cand.titles.append(item.original_title)
                    cand.source_ids.add(item.source_id)
        else:
            day = local_date(when)
            digest = hashlib.sha256(item.canonical_url.encode()).hexdigest()
            match = Event(
                topic=(source.default_topic if source and source.default_topic else "other"),
                title=item.original_title,
                slug=f"{slugify(item.original_title)}-{day.strftime('%Y%m%d')}-{digest[:6]}",
                status="discovered",
                date=day,
                cluster_hash=item.content_hash,
                last_source_at=when,
                region="india" if (source and source.country == "IN") else "world",
            )
            db.add(match)
            db.flush()
            db.add(EventSource(event_id=match.id, source_item_id=item.id, source_role="primary"))
            candidates.append(
                Candidate(event=match, titles=[item.original_title], when=when, source_ids={item.source_id})
            )
            stats.new_events += 1
        by_hash[item.content_hash] = match
        item.fetch_status = "clustered"
    db.flush()
    return stats

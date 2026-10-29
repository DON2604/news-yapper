"""GDELT DOC 2.0 API (mode=artlist, format=json) - discovery references only."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from adapters.base import RawItem, SourceConfig
from adapters.http import FetchError, SafeFetcher

MAX_WINDOW_HOURS = 72
GDELT_SPACING_SECONDS = 6.0


def parse_seendate(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse_gdelt(content: bytes) -> list[RawItem]:
    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    if not text.startswith("{"):
        raise FetchError(f"GDELT returned a non-JSON response: {text[:160]!r}", kind="parse")
    try:
        data = json.loads(text, strict=False)
    except json.JSONDecodeError as exc:
        raise FetchError(f"GDELT JSON could not be parsed: {exc}", kind="parse") from exc
    items: list[RawItem] = []
    for article in data.get("articles") or []:
        url = (article.get("url") or "").strip()
        title = (article.get("title") or "").strip()
        if not url or not title:
            continue
        items.append(
            RawItem(
                title=title,
                url=url,
                published=parse_seendate(article.get("seendate")),
                published_is_discovery_time=True,
                publisher=article.get("domain"),
                language=(article.get("language") or "")[:16] or None,
                country=(article.get("sourcecountry") or "")[:64] or None,
                extra={"gdelt_domain": article.get("domain")},
            )
        )
    return items


class GDELTAdapter:
    def __init__(self, sleep: Callable[[float], None] = time.sleep) -> None:
        self._sleep = sleep

    def fetch(self, source: SourceConfig, fetcher: SafeFetcher, now: datetime) -> list[RawItem]:
        if not source.feed_url:
            raise FetchError("GDELT source has no endpoint", kind="config")
        cfg = source.config or {}
        queries = [q for q in cfg.get("queries", []) if isinstance(q, str) and q.strip()]
        if not queries:
            raise FetchError("GDELT source has no queries configured", kind="config")
        window = timedelta(hours=min(int(cfg.get("window_hours", 24)), MAX_WINDOW_HOURS))
        start = now - window
        if source.last_success_at and source.last_success_at > start:
            start = source.last_success_at - timedelta(minutes=15)
        max_records = max(1, min(int(cfg.get("max_records", 50)), 250))

        seen: set[str] = set()
        items: list[RawItem] = []
        for index, query in enumerate(queries):
            if index:
                self._sleep(GDELT_SPACING_SECONDS)
            result = fetcher.get(
                source.feed_url,
                params={
                    "query": query,
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": max_records,
                    "sort": "datedesc",
                    "startdatetime": start.strftime("%Y%m%d%H%M%S"),
                    "enddatetime": now.strftime("%Y%m%d%H%M%S"),
                },
            )
            for item in parse_gdelt(result.content):
                if item.url not in seen:
                    seen.add(item.url)
                    item.extra["gdelt_query"] = query
                    items.append(item)
        return items

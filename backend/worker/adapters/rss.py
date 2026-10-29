from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

import feedparser

from adapters.base import RawItem, SourceConfig
from adapters.http import FetchError, SafeFetcher
from pipeline.normalize import split_publisher_suffix


def _struct_to_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def parse_feed(
    content: bytes, *, default_publisher: str | None, publisher_in_title: bool = False
) -> list[RawItem]:
    # Always pass bytes: given a str that looks like a URL, feedparser would fetch it itself.
    parsed = feedparser.parse(bytes(content))
    if not parsed.entries:
        if getattr(parsed, "bozo", False):
            raise FetchError(
                f"Malformed feed: {getattr(parsed, 'bozo_exception', 'unknown error')}", kind="parse"
            )
        return []
    items: list[RawItem] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        publisher = default_publisher
        source_meta = entry.get("source") or {}
        if publisher_in_title:
            title, suffix = split_publisher_suffix(title)
            publisher = (
                (source_meta.get("title") if isinstance(source_meta, dict) else None) or suffix or publisher
            )
        published = _struct_to_dt(entry.get("published_parsed") or entry.get("updated_parsed"))
        extra: dict[str, Any] = {}
        if entry.get("id"):
            extra["guid"] = str(entry.get("id"))[:300]
        if publisher_in_title and isinstance(source_meta, dict) and source_meta.get("href"):
            extra["publisher_home"] = source_meta.get("href")
        items.append(
            RawItem(
                title=title,
                url=link,
                summary=entry.get("summary") or entry.get("description"),
                published=published,
                author=entry.get("author"),
                publisher=publisher,
                tags=[str(t["term"]) for t in entry.get("tags", []) if isinstance(t, dict) and t.get("term")],
                extra=extra,
            )
        )
    return items


class RSSAdapter:
    def __init__(self, *, default_publisher: str | None = None, publisher_in_title: bool = False) -> None:
        self.default_publisher = default_publisher
        self.publisher_in_title = publisher_in_title

    def fetch(self, source: SourceConfig, fetcher: SafeFetcher, now: datetime) -> list[RawItem]:
        if not source.feed_url:
            raise FetchError(f"{source.slug} has no feed_url", kind="config")
        result = fetcher.get(source.feed_url)
        return parse_feed(
            result.content,
            default_publisher=self.default_publisher or source.name,
            publisher_in_title=self.publisher_in_title,
        )

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from adapters.http import SafeFetcher


@dataclass
class RawItem:
    title: str
    url: str
    summary: str | None = None
    published: datetime | None = None
    published_is_discovery_time: bool = False
    author: str | None = None
    publisher: str | None = None
    language: str | None = None
    country: str | None = None
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceConfig:
    id: Any
    slug: str
    name: str
    type: str
    feed_url: str | None
    home_url: str | None
    country: str | None
    language: str
    config: dict[str, Any]
    last_success_at: datetime | None


class SourceAdapter(Protocol):
    def fetch(self, source: SourceConfig, fetcher: SafeFetcher, now: datetime) -> list[RawItem]: ...

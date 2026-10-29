"""Google News RSS (supplementary discovery). Titles carry a ' - Publisher' suffix.

Disabled by default: the feed's own copyright notice limits use to personal,
non-commercial feed readers (see app/seed/sources.py)."""

from __future__ import annotations

from adapters.rss import RSSAdapter


class GoogleNewsAdapter(RSSAdapter):
    def __init__(self) -> None:
        super().__init__(default_publisher=None, publisher_in_title=True)

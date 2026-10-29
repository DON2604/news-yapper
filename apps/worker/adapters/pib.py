"""PIB (Press Information Bureau) RSS. Item links point to PressReleasePage.aspx?PRID=..."""

from __future__ import annotations

from adapters.rss import RSSAdapter


class PIBAdapter(RSSAdapter):
    def __init__(self) -> None:
        super().__init__(default_publisher="Press Information Bureau")

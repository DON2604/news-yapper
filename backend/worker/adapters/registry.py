from __future__ import annotations

from adapters.base import SourceAdapter, SourceConfig
from adapters.gdelt import GDELTAdapter
from adapters.google_news import GoogleNewsAdapter
from adapters.pib import PIBAdapter
from adapters.rss import RSSAdapter

PUBLISHERS = {
    "rbi-press": "Reserve Bank of India",
    "un-news": "UN News",
}


def adapter_for(source: SourceConfig) -> SourceAdapter | None:
    if source.slug == "pib":
        return PIBAdapter()
    if source.slug == "google-news-in":
        return GoogleNewsAdapter()
    if source.type == "gdelt":
        return GDELTAdapter()
    if source.type == "rss":
        return RSSAdapter(default_publisher=PUBLISHERS.get(source.slug, source.name))
    return None

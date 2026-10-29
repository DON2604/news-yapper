"""Source registry (plan section 3). Upserted by slug; operator toggles (enabled) are preserved.

Feed endpoints marked "verified" responded with a valid feed on 2026-10-29 from the
development machine. Live ingestion still requires ENABLE_LIVE_INGESTION=true.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Source

GOOGLE_NEWS_TERMS = (
    "Feed copyright notice (checked 2026-10-29): 'This XML feed is made available solely for the purpose of "
    "rendering Google News results within a personal feed reader for personal, non-commercial use. Any other "
    "use of the feed is expressly prohibited.' Disabled by default; enable only for personal, non-commercial "
    "development after your own review."
)

SOURCES: list[dict[str, Any]] = [
    {
        "slug": "pib",
        "name": "Press Information Bureau (PIB)",
        "type": "rss",
        "tier": "A",
        "home_url": "https://www.pib.gov.in/",
        "feed_url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
        "enabled": True,
        "authority_weight": 1.0,
        "country": "IN",
        "default_topic": "polity",
        "legal_notes": (
            "Government of India press releases. Store URL, title, short excerpt and publication time; write "
            "original summaries. Official releases do not make every asset unrestricted (no image copying). "
            "Note: from some networks pib.gov.in answers automated clients with an Akamai 403; the fetcher records "
            "the error and never tries to bypass it."
        ),
    },
    {
        "slug": "rbi-press",
        "name": "Reserve Bank of India - Press Releases",
        "type": "rss",
        "tier": "A",
        "home_url": "https://www.rbi.org.in/",
        "feed_url": "https://www.rbi.org.in/pressreleases_rss.xml",
        "enabled": True,
        "authority_weight": 1.0,
        "country": "IN",
        "default_topic": "economy",
        "legal_notes": (
            "Feed URL verified from rbi.org.in itself (2026-10-29). Feed states 'Copyright Reserve Bank of India. "
            "All Rights Reserved.' - store links + short excerpts only, attribute RBI, write original summaries."
        ),
    },
    {
        "slug": "un-news",
        "name": "UN News",
        "type": "rss",
        "tier": "A",
        "home_url": "https://news.un.org/en/",
        "feed_url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        "enabled": True,
        "authority_weight": 0.9,
        "country": None,
        "default_topic": "international",
        "legal_notes": (
            "Official UN feed (verified 2026-10-29). Review UN terms of use before public release; links + short "
            "excerpts only."
        ),
    },
    {
        "slug": "gdelt",
        "name": "GDELT DOC 2.0 API",
        "type": "gdelt",
        "tier": "B",
        "home_url": "https://www.gdeltproject.org/",
        "feed_url": "https://api.gdeltproject.org/api/v2/doc/doc",
        "enabled": True,
        "authority_weight": 0.4,
        "fetch_interval_minutes": 60,
        "config": {
            "queries": [
                '(India OR "Government of India") (scheme OR policy OR bill OR cabinet) sourcelang:english',
                '(RBI OR inflation OR GDP OR "monetary policy") sourcecountry:india sourcelang:english',
                '(ISRO OR satellite OR "space mission") sourcelang:english',
                '(summit OR treaty OR "United Nations") India sourcelang:english',
            ],
            "max_records": 50,
            "window_hours": 24,
        },
        "legal_notes": (
            "Discovery references only: GDELT returns publisher URLs + titles, not a licence to republish "
            "publishers' articles. A GDELT headline alone never establishes truth; prefer Tier A corroboration. "
            "Requests are bounded by date window and spaced >= 6 s apart."
        ),
    },
    {
        "slug": "google-news-in",
        "name": "Google News RSS (India)",
        "type": "rss",
        "tier": "B",
        "home_url": "https://news.google.com/",
        "feed_url": "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
        "enabled": False,
        "authority_weight": 0.3,
        "legal_notes": GOOGLE_NEWS_TERMS,
    },
    {
        "slug": "isro",
        "name": "ISRO (manual curation)",
        "type": "manual",
        "tier": "A",
        "home_url": "https://www.isro.gov.in/",
        "enabled": False,
        "authority_weight": 1.0,
        "country": "IN",
        "default_topic": "science",
        "legal_notes": "No machine-readable feed verified. Metadata linking / manual curation only.",
    },
    {
        "slug": "prs",
        "name": "PRS Legislative Research (manual)",
        "type": "manual",
        "tier": "A",
        "home_url": "https://prsindia.org/",
        "enabled": False,
        "authority_weight": 0.8,
        "country": "IN",
        "default_topic": "polity",
        "legal_notes": "Check terms before automated extraction. Treat as interpretation, not primary authority.",
    },
    {
        "slug": "who",
        "name": "World Health Organization (manual)",
        "type": "manual",
        "tier": "A",
        "home_url": "https://www.who.int/",
        "enabled": False,
        "authority_weight": 0.9,
        "legal_notes": "Optional official source; enable only after testing a supported feed and its terms.",
    },
    {
        "slug": "world-bank",
        "name": "World Bank (manual)",
        "type": "manual",
        "tier": "A",
        "home_url": "https://www.worldbank.org/",
        "enabled": False,
        "authority_weight": 0.9,
        "legal_notes": "Optional official source; enable only after testing a supported feed and its terms.",
    },
    {
        "slug": "imf",
        "name": "International Monetary Fund (manual)",
        "type": "manual",
        "tier": "A",
        "home_url": "https://www.imf.org/",
        "enabled": False,
        "authority_weight": 0.9,
        "legal_notes": "Optional official source; enable only after testing a supported feed and its terms.",
    },
    {
        "slug": "guardian",
        "name": "The Guardian Open Platform",
        "type": "api",
        "tier": "B",
        "home_url": "https://open-platform.theguardian.com/",
        "enabled": False,
        "authority_weight": 0.5,
        "legal_notes": (
            "Eligible non-commercial development only (developer key: 500 calls/day, 1 call/s). Commercial or "
            "AI-derived use needs a separate rights review. Adapter not implemented in the MVP."
        ),
    },
    {
        "slug": "demo-reference",
        "name": "DEMO reference links",
        "type": "manual",
        "tier": "A",
        "home_url": None,
        "enabled": False,
        "authority_weight": 0.5,
        "legal_notes": (
            "Seeded DEMO items: evergreen, historical facts written for UI testing. Each links to a reference page "
            "that was checked to resolve; they are not today's news."
        ),
    },
]

_MUTABLE = (
    "name",
    "type",
    "tier",
    "home_url",
    "feed_url",
    "authority_weight",
    "country",
    "default_topic",
    "legal_notes",
)


def seed_sources(db: Session) -> int:
    for spec in SOURCES:
        source = db.scalar(select(Source).where(Source.slug == spec["slug"]))
        if source is None:
            db.add(
                Source(
                    slug=spec["slug"],
                    name=spec["name"],
                    type=spec["type"],
                    tier=spec["tier"],
                    home_url=spec.get("home_url"),
                    feed_url=spec.get("feed_url"),
                    enabled=spec.get("enabled", False),
                    authority_weight=spec.get("authority_weight", 0.5),
                    country=spec.get("country"),
                    default_topic=spec.get("default_topic"),
                    fetch_interval_minutes=spec.get("fetch_interval_minutes", 60),
                    config=spec.get("config", {}),
                    legal_notes=spec["legal_notes"],
                )
            )
        else:
            for key in _MUTABLE:
                setattr(source, key, spec.get(key))
            source.config = spec.get("config", {})
    db.flush()
    return len(SOURCES)

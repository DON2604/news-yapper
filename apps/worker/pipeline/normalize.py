"""Deterministic normalisation of raw feed items (no AI)."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from adapters.base import RawItem, SourceConfig

TRACKING_PARAMS = {
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "cmpid",
    "ocid",
    "igshid",
    "spm",
    "_ga",
    "ved",
    "usg",
    "s_cid",
    "at_medium",
    "at_campaign",
    "smid",
}
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "at", "by", "from", "as", "is",
    "are", "was", "were", "be", "been", "this", "that", "its", "it", "into", "over", "after", "before",
    "about", "amid", "says", "said", "new", "will", "has", "have", "had", "not", "but", "than", "more",
    "up", "out", "his", "her", "their", "our", "your", "who", "what", "how", "why", "when", "all",
}  # fmt: skip
EXCERPT_CHARS = 400
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass
class NormalizedItem:
    canonical_url: str
    original_url: str
    title: str
    excerpt: str | None
    published_at: datetime | None
    publisher: str | None
    author: str | None
    language: str | None
    country: str | None
    tags: list[str]
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG.sub(" ", value)
    text = html.unescape(text)
    return _SPACE.sub(" ", text).strip()


def make_excerpt(text: str, max_chars: int = EXCERPT_CHARS) -> str | None:
    text = text.strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:- ")
    return cut + "…"


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    query = urlencode(
        sorted(
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
        )
    )
    return urlunsplit(("https", netloc, path, query, ""))


def normalize_title(title: str) -> str:
    return _SPACE.sub(" ", _NON_WORD.sub(" ", title.lower())).strip()


def title_tokens(title: str) -> set[str]:
    return {t for t in normalize_title(title).split() if len(t) > 2 and t not in STOPWORDS}


def content_fingerprint(title: str, excerpt: str | None) -> str:
    basis = normalize_title(title) + "|" + normalize_title(excerpt or "")[:300]
    return hashlib.sha256(basis.encode()).hexdigest()


def to_utc(value: datetime | None, now: datetime) -> tuple[datetime | None, str | None]:
    """Returns (timestamp, problem). Future timestamps (> 1 day ahead) are dropped as invalid."""
    if value is None:
        return None, "missing"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    value = value.astimezone(UTC)
    if value > now + timedelta(days=1):
        return None, "future"
    if value < now - timedelta(days=3650):
        return None, "implausible"
    return value, None


_GOOGLE_SUFFIX = re.compile(r"\s+[-–—]\s+([^-–—]{2,80})$")


def split_publisher_suffix(title: str) -> tuple[str, str | None]:
    """'Headline - Publisher' (Google News style) -> ('Headline', 'Publisher')."""
    match = _GOOGLE_SUFFIX.search(title)
    if not match:
        return title, None
    return title[: match.start()].strip(), match.group(1).strip()


def normalize_item(raw: RawItem, source: SourceConfig, now: datetime) -> NormalizedItem | None:
    title = strip_html(raw.title)[:500]
    url = (raw.url or "").strip()
    if not title or not url.lower().startswith(("http://", "https://")):
        return None
    excerpt = make_excerpt(strip_html(raw.summary))
    if excerpt and normalize_title(excerpt) == normalize_title(title):
        excerpt = None
    published, problem = to_utc(raw.published, now)
    metadata: dict[str, Any] = dict(raw.extra)
    if problem:
        metadata["timestamp_problem"] = problem
    if raw.published_is_discovery_time:
        metadata["timestamp_kind"] = "discovered_by_aggregator"
    return NormalizedItem(
        canonical_url=canonical_url(url),
        original_url=url,
        title=title,
        excerpt=excerpt,
        published_at=published,
        publisher=(raw.publisher or source.name)[:200],
        author=(strip_html(raw.author)[:200] or None) if raw.author else None,
        language=raw.language or source.language,
        country=raw.country or source.country,
        tags=[strip_html(t)[:40] for t in raw.tags if t][:10],
        content_hash=content_fingerprint(title, excerpt),
        metadata=metadata,
    )

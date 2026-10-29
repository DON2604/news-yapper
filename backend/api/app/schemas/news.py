from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class SourceRef(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    published_at: datetime | None
    tier: str
    role: str
    is_demo: bool


class NewsItem(BaseModel):
    event_id: uuid.UUID
    slug: str
    category: str
    date: date
    status: str
    ai_status: Literal["ready", "pending", "in_review"]
    headline: str
    tldr: str
    exam_tags: list[str]
    relevance_score: float
    importance_score: int | None
    sensitive: bool
    is_demo: bool
    correction_status: str
    source_count: int
    primary_source: SourceRef | None
    last_updated_at: datetime
    saved: bool = False


class KeyFact(BaseModel):
    claim: str
    source_item_ids: list[str]


class Verification(BaseModel):
    verified_at: datetime | None
    method: str | None
    ai_provider: str | None
    ai_model: str | None
    prompt_version: str | None


class ArticleDetail(NewsItem):
    neutral_summary: str | None
    banglish_summary: str | None
    why_matters: str | None
    context: str | None
    key_facts: list[KeyFact]
    mnemonics: list[str]
    uncertainties: list[str]
    verification: Verification | None
    sources: list[SourceRef]
    relevance_reasons: list[str]
    correction_note: str | None
    practice_question_count: int
    snapshot_id: uuid.UUID | None = None


class NewsPage(BaseModel):
    items: list[NewsItem]
    next_cursor: str | None
    total: int


class EditionOut(BaseModel):
    id: uuid.UUID | None
    edition_date: date
    timezone: str
    title: str | None
    is_demo: bool
    is_fallback: bool
    published_at: datetime | None
    items: list[NewsItem]
    generated_count: int
    pending_count: int

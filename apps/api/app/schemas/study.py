"""Notes, snapshots, mistakes, collections, flashcards, crunch."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

NoteColor = Literal["mango", "lavender", "mint", "pink"]


class NoteIn(BaseModel):
    title: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=5000)
    color: NoteColor = "mango"
    tags: list[str] = Field(default_factory=list, max_length=12)
    exam_topic: str | None = Field(default=None, max_length=32)
    board_x: float = Field(default=0, ge=-5000, le=5000)
    board_y: float = Field(default=0, ge=-5000, le=5000)
    pinned: bool = False
    snapshot_id: uuid.UUID | None = None


class NotePatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=5000)
    color: NoteColor | None = None
    tags: list[str] | None = Field(default=None, max_length=12)
    exam_topic: str | None = Field(default=None, max_length=32)
    board_x: float | None = Field(default=None, ge=-5000, le=5000)
    board_y: float | None = Field(default=None, ge=-5000, le=5000)
    pinned: bool | None = None
    archived: bool | None = None
    expected_version: int | None = None


class NoteOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    color: str
    tags: list[str]
    exam_topic: str | None
    board_x: float
    board_y: float
    pinned: bool
    archived: bool
    revision_version: int
    snapshot_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SnapshotIn(BaseModel):
    article_slug: str = Field(max_length=160)


class SnapshotFact(BaseModel):
    claim: str
    source_url: str | None = None


class SnapshotOut(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID | None
    event_slug: str | None
    category: str | None
    saved_title: str
    saved_banglish_summary: str
    saved_key_facts: list[SnapshotFact]
    source_url: str | None
    source_name: str | None
    source_published_at: datetime | None
    verified: bool
    is_demo: bool
    saved_at: datetime
    article_available: bool
    article_updated_since_save: bool
    created: bool = False


class MistakeOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    prompt: str
    options: list[str]
    incorrect_choice: int
    correct_choice: int
    explanation: str
    evidence_urls: list[str]
    topic: str
    error_count: int
    correct_review_count: int
    status: str
    review_after: datetime | None
    added_at: datetime
    last_wrong_at: datetime
    last_reviewed_at: datetime | None
    resolved_at: datetime | None


class MistakeReviewIn(BaseModel):
    action: Literal["answer", "snooze", "resolve"] = "answer"
    selected_index: int | None = Field(default=None, ge=0, le=3)


class MistakeReviewOut(BaseModel):
    mistake: MistakeOut
    is_correct: bool | None


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: NoteColor = "lavender"
    description: str = Field(default="", max_length=500)


class CollectionItemIn(BaseModel):
    item_type: Literal["note", "snapshot", "mistake", "crunch"]
    item_id: uuid.UUID


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    description: str
    item_counts: dict[str, int]
    items: list[CollectionItemIn]
    created_at: datetime


class FlashcardOut(BaseModel):
    id: uuid.UUID
    front: str
    back: str
    exam_topic: str | None
    source_ref: dict[str, Any]
    due_at: datetime
    interval_days: int
    ease_factor: float
    repetitions: int
    lapses: int
    last_reviewed_at: datetime | None
    crunch_output_id: uuid.UUID | None


class FlashcardReviewIn(BaseModel):
    outcome: Literal["again", "hard", "good", "easy"]


class FlashcardReviewOut(BaseModel):
    flashcard: FlashcardOut
    next_due_at: datetime
    interval_days: int


class UpcomingDay(BaseModel):
    date: date
    count: int


class CrunchOutputBrief(BaseModel):
    id: uuid.UUID
    title: str
    engine: str
    created_at: datetime
    bullet_count: int
    flashcard_count: int


class RevisionDueOut(BaseModel):
    flashcards: list[FlashcardOut]
    due_flashcards: int
    total_flashcards: int
    mistakes_due: list[MistakeOut]
    active_mistakes: int
    upcoming: list[UpcomingDay]
    recaps: list[CrunchOutputBrief]


class CrunchSettings(BaseModel):
    length: Literal["short", "detailed"] = "short"
    language: Literal["banglish", "english"] = "banglish"
    exam: Literal["SSC", "UPSC", "STATE_PSC", "BANKING", "RAILWAYS", "GENERAL"] = "SSC"
    flashcards: int = Field(default=8, ge=5, le=15)
    include_traps: bool = True


class CrunchIn(BaseModel):
    note_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    snapshot_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    mistake_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    collection_id: uuid.UUID | None = None
    last_week: bool = False
    settings: CrunchSettings = Field(default_factory=CrunchSettings)
    engine: Literal["auto", "ai", "offline"] = "auto"


class CrunchJobOut(BaseModel):
    id: uuid.UUID
    status: str
    engine: str
    status_message: str | None
    output_id: uuid.UUID | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    item_count: int
    cached: bool = False


class CrunchPreviewItem(BaseModel):
    type: Literal["note", "snapshot", "mistake"]
    id: uuid.UUID
    title: str
    chars: int
    verified: bool


class CrunchPreviewOut(BaseModel):
    items: list[CrunchPreviewItem]
    total_chars: int
    token_estimate: int
    max_chars: int
    max_items: int
    within_budget: bool
    digest: str
    engine_resolved: str
    existing_job: CrunchJobOut | None
    disclosure: dict[str, Any]
    warnings: list[str]


class CrunchOutputOut(BaseModel):
    id: uuid.UUID
    title: str
    concise_bullets: list[dict[str, Any]]
    topic_sections: list[dict[str, Any]]
    mnemonics: list[str]
    exam_traps: list[dict[str, Any]]
    source_refs: list[dict[str, Any]]
    warnings: list[str]
    engine: str
    model: str | None
    prompt_version: str
    created_at: datetime
    flashcards: list[FlashcardOut]

"""Private, user-owned study data. Every row carries user_id and is scoped by it in services."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, in_check, utcnow

NOTE_COLORS = ("mango", "lavender", "mint", "pink")
SESSION_TYPES = ("daily", "mistakes", "practice")
MISTAKE_STATUSES = ("active", "resolved")
COLLECTION_ITEM_TYPES = ("note", "snapshot", "mistake", "crunch")
CRUNCH_STATUSES = ("queued", "running", "deferred", "completed", "failed")
REVIEW_OUTCOMES = ("again", "hard", "good", "easy")


def _user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)


class QuizSession(UUIDPk, Timestamps, Base):
    __tablename__ = "quiz_sessions"
    __table_args__ = (
        CheckConstraint(in_check("type", SESSION_TYPES), name="type_valid"),
        Index("ix_quiz_sessions_user_type_date", "user_id", "type", "session_date"),
    )

    user_id: Mapped[uuid.UUID] = _user_fk()
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_editions.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(16), default="daily")
    session_date: Mapped[date] = mapped_column(Date)
    question_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    question_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class QuizAttempt(UUIDPk, Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id"),
        CheckConstraint("selected_index BETWEEN 0 AND 3", name="selected_index_range"),
        Index("ix_quiz_attempts_user_correct_answered", "user_id", "is_correct", "answered_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = _user_fk()
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), index=True)
    selected_index: Mapped[int] = mapped_column(SmallInteger)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    response_ms: Mapped[int | None] = mapped_column(Integer)


class ArticleSnapshot(UUIDPk, Timestamps, Base):
    __tablename__ = "article_snapshots"
    __table_args__ = (
        Index(
            "uq_article_snapshots_user_article",
            "user_id",
            "article_id",
            unique=True,
            postgresql_where=text("article_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = _user_fk()
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    source_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_items.id", ondelete="SET NULL")
    )
    event_slug: Mapped[str | None] = mapped_column(String(160))
    category: Mapped[str | None] = mapped_column(String(32))
    saved_title: Mapped[str] = mapped_column(Text)
    saved_banglish_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    saved_key_facts: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Note(UUIDPk, Timestamps, Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint(in_check("color", NOTE_COLORS), name="color_valid"),
        Index("ix_notes_user_updated", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = _user_fk()
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    color: Mapped[str] = mapped_column(String(16), default="mango", server_default="mango")
    tags: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    exam_topic: Mapped[str | None] = mapped_column(String(32))
    board_x: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    board_y: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    revision_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_snapshots.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MistakeVaultEntry(UUIDPk, Timestamps, Base):
    __tablename__ = "mistake_vault"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id"),
        CheckConstraint(in_check("status", MISTAKE_STATUSES), name="status_valid"),
    )

    user_id: Mapped[uuid.UUID] = _user_fk()
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), index=True)
    latest_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="SET NULL")
    )
    incorrect_choice: Mapped[int] = mapped_column(SmallInteger)
    correct_choice: Mapped[int] = mapped_column(SmallInteger)
    prompt_snapshot: Mapped[str] = mapped_column(Text)
    options_snapshot: Mapped[list[Any]] = mapped_column(JSONB)
    explanation_snapshot: Mapped[str] = mapped_column(Text)
    evidence_urls: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    topic: Mapped[str] = mapped_column(String(32))
    error_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    correct_review_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    review_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_wrong_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudyCollection(UUIDPk, Timestamps, Base):
    __tablename__ = "study_collections"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(16), default="lavender", server_default="lavender")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (CheckConstraint(in_check("item_type", COLLECTION_ITEM_TYPES), name="item_type_valid"),)

    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_collections.id", ondelete="CASCADE"), primary_key=True
    )
    item_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class CrunchOutput(UUIDPk, Timestamps, Base):
    __tablename__ = "crunch_outputs"

    user_id: Mapped[uuid.UUID] = _user_fk()
    input_digest: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    concise_bullets: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    topic_sections: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    mnemonics: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    exam_traps: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    source_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    warnings: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    engine: Mapped[str] = mapped_column(String(16))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(32))


class CrunchJob(UUIDPk, Timestamps, Base):
    __tablename__ = "crunch_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "input_digest"),
        CheckConstraint(in_check("status", CRUNCH_STATUSES), name="status_valid"),
        CheckConstraint(in_check("engine", ("ai", "offline")), name="engine_valid"),
    )

    user_id: Mapped[uuid.UUID] = _user_fk()
    input_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    input_digest: Mapped[str] = mapped_column(String(64))
    selected_note_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    selected_snapshot_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    selected_mistake_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    engine: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    status_message: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    error_code: Mapped[str | None] = mapped_column(String(64))
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="SET NULL")
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    output_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crunch_outputs.id", ondelete="SET NULL")
    )


class Flashcard(UUIDPk, Timestamps, Base):
    __tablename__ = "flashcards"
    __table_args__ = (Index("ix_flashcards_user_due", "user_id", "due_at"),)

    user_id: Mapped[uuid.UUID] = _user_fk()
    crunch_output_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crunch_outputs.id", ondelete="SET NULL"), index=True
    )
    source_ref: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    exam_topic: Mapped[str | None] = mapped_column(String(32))
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5, server_default="2.5")
    interval_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    repetitions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    lapses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class FlashcardReview(UUIDPk, Base):
    __tablename__ = "flashcard_reviews"
    __table_args__ = (CheckConstraint(in_check("outcome", REVIEW_OUTCOMES), name="outcome_valid"),)

    user_id: Mapped[uuid.UUID] = _user_fk()
    flashcard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flashcards.id", ondelete="CASCADE"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(8))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    previous_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_interval_days: Mapped[int] = mapped_column(Integer, default=0)
    new_interval_days: Mapped[int] = mapped_column(Integer, default=0)

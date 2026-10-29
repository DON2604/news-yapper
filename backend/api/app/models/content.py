"""Shared (non-personal) content: sources, raw items, events, articles, questions, editions."""

from __future__ import annotations

import datetime as dt
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk, in_check, utcnow

CATEGORIES = ("polity", "economy", "science", "international", "environment", "awards", "sports", "other")
EVENT_STATUSES = ("discovered", "queued", "generated", "needs_review", "published", "rejected")
CORRECTION_STATUSES = ("none", "corrected", "retracted", "source_revoked")
SOURCE_TYPES = ("rss", "gdelt", "api", "manual")
SOURCE_ITEM_STATUSES = ("new", "clustered", "ignored", "revoked")
SOURCE_ROLES = ("primary", "supporting", "discovery")
QUESTION_KINDS = ("current_affairs", "static_gk")
DIFFICULTIES = ("easy", "medium", "hard")
VALIDATION_STATUSES = ("validated", "needs_review", "rejected")


class Source(UUIDPk, Timestamps, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(in_check("type", SOURCE_TYPES), name="type_valid"),
        CheckConstraint(in_check("tier", ("A", "B")), name="tier_valid"),
    )

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(16))
    tier: Mapped[str] = mapped_column(String(1), default="B")
    home_url: Mapped[str | None] = mapped_column(Text)
    feed_url: Mapped[str | None] = mapped_column(Text)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    legal_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    authority_weight: Mapped[float] = mapped_column(Float, default=0.5, server_default="0.5")
    country: Mapped[str | None] = mapped_column(String(8))
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    default_topic: Mapped[str | None] = mapped_column(String(32))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class SourceItem(UUIDPk, Timestamps, Base):
    __tablename__ = "source_items"
    __table_args__ = (
        CheckConstraint(in_check("fetch_status", SOURCE_ITEM_STATUSES), name="fetch_status_valid"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    canonical_url: Mapped[str] = mapped_column(Text, unique=True)
    original_url: Mapped[str] = mapped_column(Text)
    original_title: Mapped[str] = mapped_column(Text)
    short_excerpt: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    language: Mapped[str | None] = mapped_column(String(16))
    country: Mapped[str | None] = mapped_column(String(64))
    tags: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    item_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    fetch_status: Mapped[str] = mapped_column(String(16), default="new", server_default="new")
    rights_notes: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    source: Mapped[Source] = relationship()


class Event(UUIDPk, Timestamps, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(in_check("status", EVENT_STATUSES), name="status_valid"),
        CheckConstraint(in_check("topic", CATEGORIES), name="topic_valid"),
        CheckConstraint(in_check("correction_status", CORRECTION_STATUSES), name="correction_status_valid"),
        Index("ix_events_status_date", "status", "date"),
    )

    topic: Mapped[str] = mapped_column(String(32), default="other", server_default="other")
    title: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="discovered", server_default="discovered")
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    region: Mapped[str] = mapped_column(String(32), default="india", server_default="india")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    relevance_reasons: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    cluster_hash: Mapped[str] = mapped_column(String(64), index=True)
    correction_status: Mapped[str] = mapped_column(String(16), default="none", server_default="none")
    correction_note: Mapped[str | None] = mapped_column(Text)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    last_source_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    article: Mapped[Article | None] = relationship(back_populates="event", uselist=False)
    sources: Mapped[list[EventSource]] = relationship(back_populates="event", cascade="all, delete-orphan")


class EventSource(Base):
    __tablename__ = "event_sources"
    __table_args__ = (CheckConstraint(in_check("source_role", SOURCE_ROLES), name="source_role_valid"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_items.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    source_role: Mapped[str] = mapped_column(String(16), default="supporting", server_default="supporting")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    event: Mapped[Event] = relationship(back_populates="sources")
    source_item: Mapped[SourceItem] = relationship()


class Article(UUIDPk, Timestamps, Base):
    __tablename__ = "articles"
    __table_args__ = (CheckConstraint(in_check("category", CATEGORIES), name="category_valid"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), unique=True
    )
    headline: Mapped[str] = mapped_column(Text)
    banglish_summary: Mapped[str] = mapped_column(Text)
    neutral_summary: Mapped[str] = mapped_column(Text)
    why_matters: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    key_facts: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    exam_tags: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    mnemonics: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    confidence_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    category: Mapped[str] = mapped_column(String(32), default="other", server_default="other")
    importance_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sensitive_story: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    ai_provider: Mapped[str | None] = mapped_column(String(32))
    ai_model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_method: Mapped[str | None] = mapped_column(String(40))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    event: Mapped[Event] = relationship(back_populates="article")


class Question(UUIDPk, Timestamps, Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("correct_index BETWEEN 0 AND 3", name="correct_index_range"),
        CheckConstraint("jsonb_array_length(options) = 4", name="four_options"),
        CheckConstraint(in_check("kind", QUESTION_KINDS), name="kind_valid"),
        CheckConstraint(in_check("difficulty", DIFFICULTIES), name="difficulty_valid"),
        CheckConstraint(in_check("validation_status", VALIDATION_STATUSES), name="validation_status_valid"),
        Index("ix_questions_pool", "validation_status", "kind", "active_from"),
    )

    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"), index=True
    )
    exam_topic: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(20), default="current_affairs")
    difficulty: Mapped[str] = mapped_column(String(8), default="medium", server_default="medium")
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]] = mapped_column(JSONB)
    correct_index: Mapped[int] = mapped_column(SmallInteger)
    explanation: Mapped[str] = mapped_column(Text)
    evidence_urls: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    evidence_source_item_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    validation_status: Mapped[str] = mapped_column(String(16), default="needs_review")
    generation_version: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active_from: Mapped[date | None] = mapped_column(Date)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class DailyEdition(UUIDPk, Timestamps, Base):
    __tablename__ = "daily_editions"
    __table_args__ = (
        UniqueConstraint("edition_date", "timezone"),
        CheckConstraint(in_check("status", ("draft", "published")), name="status_valid"),
    )

    edition_date: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    title: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    items: Mapped[list[EditionEvent]] = relationship(
        back_populates="edition", cascade="all, delete-orphan", order_by="EditionEvent.ranking"
    )


class EditionEvent(Base):
    __tablename__ = "edition_events"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_editions.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    ranking: Mapped[int] = mapped_column(Integer)

    edition: Mapped[DailyEdition] = relationship(back_populates="items")
    event: Mapped[Event] = relationship()

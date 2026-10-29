"""AI job queue, quota ledger, ingestion runs, audit log and worker leases."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, in_check, utcnow

AI_JOB_KINDS = ("news_batch", "crunch", "quiz_prep", "classification", "article_chat")
AI_JOB_STATUSES = ("queued", "running", "deferred", "succeeded", "failed", "dead_letter", "cancelled")
USAGE_OUTCOMES = (
    "reserved",
    "success",
    "rate_limited",
    "quota_exhausted",
    "server_error",
    "timeout",
    "client_error",
    "auth_error",
    "invalid_output",
    "abandoned",
    "cancelled",
)
INGESTION_STATUSES = ("requested", "running", "succeeded", "partial", "failed", "skipped")


class AIJob(UUIDPk, Timestamps, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        CheckConstraint(in_check("kind", AI_JOB_KINDS), name="kind_valid"),
        CheckConstraint(in_check("status", AI_JOB_STATUSES), name="status_valid"),
        Index("ix_ai_jobs_claim", "status", "next_run_at", "priority"),
    )

    requested_provider: Mapped[str | None] = mapped_column(String(32))
    attempted_providers: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    kind: Mapped[str] = mapped_column(String(32))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_digest: Mapped[str | None] = mapped_column(String(64))
    result_ref: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    last_provider: Mapped[str | None] = mapped_column(String(32))
    last_model: Mapped[str | None] = mapped_column(String(120))
    contains_private_data: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIUsage(UUIDPk, Base):
    """One row per provider request reservation; reconciled with real usage after the call."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_no"),
        CheckConstraint(in_check("outcome", USAGE_OUTCOMES), name="outcome_valid"),
        Index("ix_ai_usage_window", "provider", "project_id", "model", "started_at"),
        Index("ix_ai_usage_outcome", "outcome"),
    )

    provider: Mapped[str] = mapped_column(String(32))
    project_id: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(32))
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="SET NULL")
    )
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    day_key: Mapped[date] = mapped_column(Date)
    requests: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(20), default="reserved", server_default="reserved")
    provider_error_class: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuotaState(UUIDPk, Timestamps, Base):
    __tablename__ = "quota_state"
    __table_args__ = (UniqueConstraint("provider", "project_id", "model"),)

    provider: Mapped[str] = mapped_column(String(32))
    project_id: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    day_key: Mapped[date | None] = mapped_column(Date)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    block_reason: Mapped[str | None] = mapped_column(String(64))
    daily_reserved_requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    daily_spent_requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    daily_spent_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_provider_limit_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_limits: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    available: Mapped[bool | None] = mapped_column(Boolean)
    availability_note: Mapped[str | None] = mapped_column(Text)


class IngestionRun(UUIDPk, Timestamps, Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (CheckConstraint(in_check("status", INGESTION_STATUSES), name="status_valid"),)

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="requested", server_default="requested")
    trigger: Mapped[str] = mapped_column(String(16), default="schedule", server_default="schedule")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    inserted_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    clustered_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_details: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))


class AuditEvent(UUIDPk, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


class WorkerLease(Base):
    """Single-coordinator guard that also works through Neon's transaction-mode pooler."""

    __tablename__ = "worker_leases"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(120))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    info: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))

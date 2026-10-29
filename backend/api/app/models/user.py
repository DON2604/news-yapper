from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk, in_check

EXAMS = ("SSC", "UPSC", "STATE_PSC", "BANKING", "RAILWAYS", "GENERAL")
TONES = ("chill", "balanced", "serious")
AI_CONSENT = ("none", "primary_only", "allow_fallback")


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    auth_provider_id: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    preferences: Mapped[UserPreferences | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )


class UserPreferences(UUIDPk, Timestamps, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint(in_check("target_exam", EXAMS), name="target_exam_valid"),
        CheckConstraint(in_check("tone_preference", TONES), name="tone_valid"),
        CheckConstraint(in_check("crunch_ai_consent", AI_CONSENT), name="ai_consent_valid"),
        CheckConstraint("banglish_intensity BETWEEN 0 AND 3", name="banglish_intensity_range"),
        CheckConstraint("daily_minutes BETWEEN 1 AND 240", name="daily_minutes_range"),
        CheckConstraint("daily_goal BETWEEN 1 AND 50", name="daily_goal_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    target_exam: Mapped[str] = mapped_column(String(32), default="SSC", server_default="SSC")
    target_exams: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    region: Mapped[str] = mapped_column(String(64), default="West Bengal", server_default="West Bengal")
    topics: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    banglish_intensity: Mapped[int] = mapped_column(SmallInteger, default=2, server_default="2")
    daily_minutes: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", server_default="Asia/Kolkata")
    daily_goal: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    tone_preference: Mapped[str] = mapped_column(String(16), default="balanced", server_default="balanced")
    study_reminders: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    reminder_time: Mapped[str | None] = mapped_column(String(5))
    crunch_ai_consent: Mapped[str] = mapped_column(String(20), default="none", server_default="none")
    leaderboard_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="preferences")

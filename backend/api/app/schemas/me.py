from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Exam = Literal["SSC", "UPSC", "STATE_PSC", "BANKING", "RAILWAYS", "GENERAL"]
Topic = Literal["polity", "economy", "science", "international", "environment", "awards", "sports", "other"]


class PreferencesIn(BaseModel):
    target_exam: Exam = "SSC"
    target_exams: list[Exam] = Field(default_factory=list, max_length=6)
    region: str = Field(default="West Bengal", max_length=64)
    topics: list[Topic] = Field(default_factory=list, max_length=8)
    banglish_intensity: int = Field(default=2, ge=0, le=3)
    daily_minutes: int = Field(default=10, ge=1, le=240)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    daily_goal: int = Field(default=10, ge=1, le=50)
    tone_preference: Literal["chill", "balanced", "serious"] = "balanced"
    study_reminders: bool = False
    reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    crunch_ai_consent: Literal["none", "primary_only", "allow_fallback"] = "none"
    leaderboard_opt_in: bool = False
    mark_onboarded: bool = False

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return value


class PreferencesOut(BaseModel):
    target_exam: str
    target_exams: list[str]
    region: str
    topics: list[str]
    banglish_intensity: int
    daily_minutes: int
    timezone: str
    daily_goal: int
    tone_preference: str
    study_reminders: bool
    reminder_time: str | None
    crunch_ai_consent: str
    leaderboard_opt_in: bool
    onboarded_at: datetime | None


class MeOut(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str | None
    is_admin: bool
    created_at: datetime
    preferences: PreferencesOut
    demo_mode: bool
    crunch_ai: dict[str, Any]


class UserSyncIn(BaseModel):
    auth_provider_id: str = Field(min_length=3, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=120)


class PasswordRegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=240)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _normalize_email(value)


class PasswordLoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=240)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _normalize_email(value)


class PasswordAuthOut(BaseModel):
    auth_provider_id: str
    email: str
    display_name: str


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
        raise ValueError("Enter a valid email")
    local, _, domain = email.partition("@")
    if not local or "." not in domain:
        raise ValueError("Enter a valid email")
    return email


class UserSyncOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    is_admin: bool
    onboarded: bool


class TopicAccuracy(BaseModel):
    topic: str
    attempts: int
    correct: int
    accuracy: float


class ActivityDay(BaseModel):
    date: date
    count: int


class MissedQuestion(BaseModel):
    mistake_id: uuid.UUID
    prompt: str
    topic: str
    error_count: int
    status: str
    last_wrong_at: datetime


class ProgressOut(BaseModel):
    xp_total: int
    level: int
    level_floor_xp: int
    next_level_xp: int
    streak_current: int
    streak_best: int
    studied_today: bool
    today_answered: int
    daily_goal: int
    accuracy_overall: float | None
    accuracy_by_topic: list[TopicAccuracy]
    weak_topics: list[str]
    due_flashcards: int
    active_mistakes: int
    resolved_mistakes: int
    recent_missed: list[MissedQuestion]
    activity: list[ActivityDay]
    totals: dict[str, int]

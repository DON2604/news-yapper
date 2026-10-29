from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class QuizQuestionPublic(BaseModel):
    id: uuid.UUID
    prompt: str
    options: list[str]
    exam_topic: str
    kind: str
    difficulty: str
    is_demo: bool
    event_slug: str | None = None
    reason: str | None = None


class AnsweredState(BaseModel):
    question_id: uuid.UUID
    selected_index: int
    is_correct: bool
    correct_index: int
    explanation: str
    evidence_urls: list[str]


class QuizSessionOut(BaseModel):
    id: uuid.UUID
    type: str
    session_date: date
    started_at: datetime
    completed_at: datetime | None
    score: int
    question_count: int
    xp_earned: int
    questions: list[QuizQuestionPublic]
    answers: list[AnsweredState]


class DailyQuizOut(BaseModel):
    date: date
    target_count: int
    pool_size: int
    current_affairs_available: int
    static_gk_available: int
    session: QuizSessionOut | None


class CreateSessionIn(BaseModel):
    type: Literal["daily", "practice"] = "daily"
    article_slug: str | None = Field(default=None, max_length=160)


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    selected_index: int = Field(ge=0, le=3)
    response_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class MistakeBrief(BaseModel):
    id: uuid.UUID
    status: str
    error_count: int


class SessionProgress(BaseModel):
    answered: int
    total: int
    score: int


class AnswerOut(AnsweredState):
    already_answered: bool
    mistake: MistakeBrief | None
    progress: SessionProgress


class TopicStat(BaseModel):
    topic: str
    attempts: int
    correct: int
    accuracy: float


class FinishOut(BaseModel):
    session: QuizSessionOut
    topic_breakdown: list[TopicStat]
    weak_topics: list[str]
    xp_earned: int

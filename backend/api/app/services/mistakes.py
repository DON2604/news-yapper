from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.errors import InvalidInputError, NotFoundError
from app.models import MistakeVaultEntry, Question, QuizAttempt, QuizSession, User, utcnow
from app.schemas.study import MistakeOut, MistakeReviewIn, MistakeReviewOut
from app.services.clock import local_date

REVIEW_DELAY = timedelta(days=1)


def mistake_out(entry: MistakeVaultEntry) -> MistakeOut:
    return MistakeOut(
        id=entry.id,
        question_id=entry.question_id,
        prompt=entry.prompt_snapshot,
        options=[str(o) for o in entry.options_snapshot],
        incorrect_choice=entry.incorrect_choice,
        correct_choice=entry.correct_choice,
        explanation=entry.explanation_snapshot,
        evidence_urls=[str(u) for u in entry.evidence_urls or []],
        topic=entry.topic,
        error_count=entry.error_count,
        correct_review_count=entry.correct_review_count,
        status=entry.status,
        review_after=entry.review_after,
        added_at=entry.added_at,
        last_wrong_at=entry.last_wrong_at,
        last_reviewed_at=entry.last_reviewed_at,
        resolved_at=entry.resolved_at,
    )


def record_wrong_answer(
    db: Session, user: User, question: Question, attempt: QuizAttempt
) -> MistakeVaultEntry:
    """Upsert one vault row per (user, question); full history stays in quiz_attempts."""
    now = utcnow()
    stmt = (
        insert(MistakeVaultEntry)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            question_id=question.id,
            latest_attempt_id=attempt.id,
            incorrect_choice=attempt.selected_index,
            correct_choice=question.correct_index,
            prompt_snapshot=question.prompt,
            options_snapshot=list(question.options),
            explanation_snapshot=question.explanation,
            evidence_urls=list(question.evidence_urls or []),
            topic=question.exam_topic,
            error_count=1,
            correct_review_count=0,
            status="active",
            review_after=now + REVIEW_DELAY,
            revision_version=1,
            added_at=now,
            last_wrong_at=now,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[MistakeVaultEntry.user_id, MistakeVaultEntry.question_id],
            set_={
                "latest_attempt_id": attempt.id,
                "incorrect_choice": attempt.selected_index,
                "error_count": MistakeVaultEntry.error_count + 1,
                "status": "active",
                "resolved_at": None,
                "review_after": now + REVIEW_DELAY,
                "revision_version": MistakeVaultEntry.revision_version + 1,
                "last_wrong_at": now,
                "updated_at": now,
            },
        )
        .returning(MistakeVaultEntry.id)
    )
    entry_id = db.execute(stmt).scalar_one()
    db.flush()
    entry = db.get(MistakeVaultEntry, entry_id, populate_existing=True)
    assert entry is not None
    return entry


def record_correct_answer(db: Session, user: User, question_id: uuid.UUID) -> MistakeVaultEntry | None:
    entry = db.scalar(
        select(MistakeVaultEntry).where(
            MistakeVaultEntry.user_id == user.id,
            MistakeVaultEntry.question_id == question_id,
            MistakeVaultEntry.status == "active",
        )
    )
    if entry is None:
        return None
    now = utcnow()
    entry.correct_review_count += 1
    entry.status = "resolved"
    entry.resolved_at = now
    entry.last_reviewed_at = now
    return entry


def list_mistakes(db: Session, user: User, status: str = "active") -> list[MistakeOut]:
    stmt = select(MistakeVaultEntry).where(MistakeVaultEntry.user_id == user.id)
    if status in ("active", "resolved"):
        stmt = stmt.where(MistakeVaultEntry.status == status)
    entries = db.scalars(stmt.order_by(MistakeVaultEntry.last_wrong_at.desc())).all()
    return [mistake_out(e) for e in entries]


def get_owned(db: Session, user: User, mistake_id: uuid.UUID) -> MistakeVaultEntry | None:
    return db.scalar(
        select(MistakeVaultEntry).where(
            MistakeVaultEntry.id == mistake_id, MistakeVaultEntry.user_id == user.id
        )
    )


def review(
    db: Session, user: User, entry: MistakeVaultEntry, payload: MistakeReviewIn, tz_name: str
) -> MistakeReviewOut:
    now = utcnow()
    if payload.action == "snooze":
        entry.review_after = now + REVIEW_DELAY
        db.commit()
        return MistakeReviewOut(mistake=mistake_out(entry), is_correct=None)
    if payload.action == "resolve":
        entry.status = "resolved"
        entry.resolved_at = now
        entry.last_reviewed_at = now
        db.commit()
        return MistakeReviewOut(mistake=mistake_out(entry), is_correct=None)

    if payload.selected_index is None:
        raise InvalidInputError("selected_index is required to answer a mistake review")
    question = db.get(Question, entry.question_id)
    if question is None:
        raise NotFoundError("Question no longer exists")

    session = QuizSession(
        user_id=user.id,
        type="mistakes",
        session_date=local_date(now, tz_name),
        question_ids=[str(question.id)],
        question_count=1,
        started_at=now,
        completed_at=now,
    )
    db.add(session)
    db.flush()
    is_correct = payload.selected_index == question.correct_index
    attempt = QuizAttempt(
        session_id=session.id,
        user_id=user.id,
        question_id=question.id,
        selected_index=payload.selected_index,
        is_correct=is_correct,
        answered_at=now,
    )
    db.add(attempt)
    db.flush()
    session.score = 1 if is_correct else 0
    entry.last_reviewed_at = now
    if is_correct:
        entry.correct_review_count += 1
        entry.status = "resolved"
        entry.resolved_at = now
    else:
        entry.error_count += 1
        entry.incorrect_choice = payload.selected_index
        entry.latest_attempt_id = attempt.id
        entry.last_wrong_at = now
        entry.review_after = now + REVIEW_DELAY
        entry.revision_version += 1
    db.commit()
    db.refresh(entry)
    return MistakeReviewOut(mistake=mistake_out(entry), is_correct=is_correct)

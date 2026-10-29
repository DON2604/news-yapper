from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CrunchOutput, Flashcard, FlashcardReview, MistakeVaultEntry, User, utcnow
from app.schemas.study import (
    CrunchOutputBrief,
    FlashcardOut,
    FlashcardReviewOut,
    RevisionDueOut,
    UpcomingDay,
)
from app.services import srs
from app.services.clock import local_date
from app.services.mistakes import mistake_out


def flashcard_out(card: Flashcard) -> FlashcardOut:
    return FlashcardOut(
        id=card.id,
        front=card.front,
        back=card.back,
        exam_topic=card.exam_topic,
        source_ref=dict(card.source_ref or {}),
        due_at=card.due_at,
        interval_days=card.interval_days,
        ease_factor=card.ease_factor,
        repetitions=card.repetitions,
        lapses=card.lapses,
        last_reviewed_at=card.last_reviewed_at,
        crunch_output_id=card.crunch_output_id,
    )


def crunch_brief(db: Session, out: CrunchOutput) -> CrunchOutputBrief:
    cards = db.scalar(select(func.count(Flashcard.id)).where(Flashcard.crunch_output_id == out.id)) or 0
    return CrunchOutputBrief(
        id=out.id,
        title=out.title,
        engine=out.engine,
        created_at=out.created_at,
        bullet_count=len(out.concise_bullets or []),
        flashcard_count=int(cards),
    )


def due(db: Session, user: User, tz_name: str, limit: int = 50) -> RevisionDueOut:
    now = utcnow()
    base = select(Flashcard).where(Flashcard.user_id == user.id, Flashcard.suspended.is_(False))
    due_cards = db.scalars(base.where(Flashcard.due_at <= now).order_by(Flashcard.due_at).limit(limit)).all()
    due_count = db.scalar(
        select(func.count(Flashcard.id)).where(
            Flashcard.user_id == user.id, Flashcard.suspended.is_(False), Flashcard.due_at <= now
        )
    )
    total = db.scalar(select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id))

    week_end = now + timedelta(days=7)
    upcoming_cards = db.scalars(
        select(Flashcard.due_at).where(
            Flashcard.user_id == user.id,
            Flashcard.suspended.is_(False),
            Flashcard.due_at > now,
            Flashcard.due_at <= week_end,
        )
    ).all()
    buckets: dict = {}
    for due_at in upcoming_cards:
        d = local_date(due_at, tz_name)
        buckets[d] = buckets.get(d, 0) + 1

    mistakes_due = db.scalars(
        select(MistakeVaultEntry)
        .where(
            MistakeVaultEntry.user_id == user.id,
            MistakeVaultEntry.status == "active",
            (MistakeVaultEntry.review_after.is_(None)) | (MistakeVaultEntry.review_after <= now),
        )
        .order_by(MistakeVaultEntry.error_count.desc())
        .limit(20)
    ).all()
    active = db.scalar(
        select(func.count(MistakeVaultEntry.id)).where(
            MistakeVaultEntry.user_id == user.id, MistakeVaultEntry.status == "active"
        )
    )
    recaps = db.scalars(
        select(CrunchOutput)
        .where(CrunchOutput.user_id == user.id)
        .order_by(CrunchOutput.created_at.desc())
        .limit(6)
    ).all()
    return RevisionDueOut(
        flashcards=[flashcard_out(c) for c in due_cards],
        due_flashcards=int(due_count or 0),
        total_flashcards=int(total or 0),
        mistakes_due=[mistake_out(m) for m in mistakes_due],
        active_mistakes=int(active or 0),
        upcoming=[UpcomingDay(date=d, count=c) for d, c in sorted(buckets.items())],
        recaps=[crunch_brief(db, r) for r in recaps],
    )


def list_flashcards(db: Session, user: User) -> list[Flashcard]:
    return list(
        db.scalars(
            select(Flashcard).where(Flashcard.user_id == user.id).order_by(Flashcard.due_at).limit(500)
        ).all()
    )


def get_owned_card(db: Session, user: User, card_id: uuid.UUID) -> Flashcard | None:
    return db.scalar(select(Flashcard).where(Flashcard.id == card_id, Flashcard.user_id == user.id))


def review_card(db: Session, user: User, card: Flashcard, outcome: str) -> FlashcardReviewOut:
    now = utcnow()
    previous_due = card.due_at
    previous_interval = card.interval_days
    result = srs.schedule(
        srs.CardState(card.ease_factor, card.interval_days, card.repetitions, card.lapses), outcome, now
    )
    card.ease_factor = result.state.ease_factor
    card.interval_days = result.state.interval_days
    card.repetitions = result.state.repetitions
    card.lapses = result.state.lapses
    card.due_at = result.due_at
    card.last_reviewed_at = now
    db.add(
        FlashcardReview(
            user_id=user.id,
            flashcard_id=card.id,
            outcome=outcome,
            reviewed_at=now,
            previous_due_at=previous_due,
            next_due_at=result.due_at,
            previous_interval_days=previous_interval,
            new_interval_days=result.state.interval_days,
        )
    )
    db.commit()
    db.refresh(card)
    return FlashcardReviewOut(
        flashcard=flashcard_out(card), next_due_at=card.due_at, interval_days=card.interval_days
    )

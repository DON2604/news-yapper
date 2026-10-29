"""Progress is derived from activity rows (no separate XP ledger to drift out of sync).

XP: +10 per correct answer, +20 per finished quiz session, +2 per flashcard review,
+15 per Crunch output, +3 per saved snapshot. Level n starts at 100*n*(n-1)/2 XP.
Streaks count consecutive local days with any study activity; there is no penalty
or shaming for a broken streak.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Date, cast, func, select, union_all
from sqlalchemy.orm import Session

from app.models import (
    ArticleSnapshot,
    CrunchOutput,
    Flashcard,
    FlashcardReview,
    MistakeVaultEntry,
    Note,
    QuizAttempt,
    QuizSession,
    User,
    UserPreferences,
    utcnow,
)
from app.schemas.me import ActivityDay, MissedQuestion, ProgressOut, TopicAccuracy
from app.services.clock import local_date
from app.services.quiz import topic_accuracy, weak_topics


def level_for(xp: int) -> tuple[int, int, int]:
    level = 1
    while 100 * (level + 1) * level // 2 <= xp:
        level += 1
    return level, 100 * level * (level - 1) // 2, 100 * (level + 1) * level // 2


def _count(db: Session, stmt: Any) -> int:
    return int(db.scalar(stmt) or 0)


def streaks(days: set[date], today: date) -> tuple[int, int]:
    if not days:
        return 0, 0
    current = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)
    best = 0
    run = 0
    prev: date | None = None
    for d in sorted(days):
        run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return current, best


def compute(db: Session, user: User, prefs: UserPreferences) -> ProgressOut:
    uid = user.id
    tz_name = prefs.timezone
    now = utcnow()
    today = local_date(now, tz_name)

    correct = _count(
        db, select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == uid, QuizAttempt.is_correct)
    )
    answered = _count(db, select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == uid))
    sessions_done = _count(
        db,
        select(func.count(QuizSession.id)).where(
            QuizSession.user_id == uid, QuizSession.completed_at.is_not(None), QuizSession.type != "mistakes"
        ),
    )
    reviews = _count(db, select(func.count(FlashcardReview.id)).where(FlashcardReview.user_id == uid))
    crunches = _count(db, select(func.count(CrunchOutput.id)).where(CrunchOutput.user_id == uid))
    snapshots = _count(db, select(func.count(ArticleSnapshot.id)).where(ArticleSnapshot.user_id == uid))
    notes = _count(db, select(func.count(Note.id)).where(Note.user_id == uid, Note.deleted_at.is_(None)))
    cards = _count(db, select(func.count(Flashcard.id)).where(Flashcard.user_id == uid))
    xp = correct * 10 + sessions_done * 20 + reviews * 2 + crunches * 15 + snapshots * 3
    level, floor_xp, next_xp = level_for(xp)

    def local_day(col: Any) -> Any:
        return cast(func.timezone(tz_name, col), Date)

    activity_union = union_all(
        select(local_day(QuizAttempt.answered_at).label("d")).where(QuizAttempt.user_id == uid),
        select(local_day(FlashcardReview.reviewed_at).label("d")).where(FlashcardReview.user_id == uid),
        select(local_day(Note.created_at).label("d")).where(Note.user_id == uid),
        select(local_day(ArticleSnapshot.saved_at).label("d")).where(ArticleSnapshot.user_id == uid),
    ).subquery()
    per_day = db.execute(select(activity_union.c.d, func.count()).group_by(activity_union.c.d)).all()
    counts = {d: int(c) for d, c in per_day}
    current, best = streaks(set(counts), today)

    today_answered = _count(
        db,
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.user_id == uid, local_day(QuizAttempt.answered_at) == today
        ),
    )
    stats = topic_accuracy(db, uid, days=3650)
    accuracy = [
        TopicAccuracy(topic=t, attempts=n, correct=c, accuracy=round(c / n, 3) if n else 0.0)
        for t, (n, c) in sorted(stats.items(), key=lambda kv: -kv[1][0])
    ]
    due_cards = _count(
        db,
        select(func.count(Flashcard.id)).where(
            Flashcard.user_id == uid, Flashcard.due_at <= now, Flashcard.suspended.is_(False)
        ),
    )
    active = _count(
        db,
        select(func.count(MistakeVaultEntry.id)).where(
            MistakeVaultEntry.user_id == uid, MistakeVaultEntry.status == "active"
        ),
    )
    resolved = _count(
        db,
        select(func.count(MistakeVaultEntry.id)).where(
            MistakeVaultEntry.user_id == uid, MistakeVaultEntry.status == "resolved"
        ),
    )
    missed = db.scalars(
        select(MistakeVaultEntry)
        .where(MistakeVaultEntry.user_id == uid)
        .order_by(MistakeVaultEntry.last_wrong_at.desc())
        .limit(8)
    ).all()

    return ProgressOut(
        xp_total=xp,
        level=level,
        level_floor_xp=floor_xp,
        next_level_xp=next_xp,
        streak_current=current,
        streak_best=best,
        studied_today=today in counts,
        today_answered=today_answered,
        daily_goal=prefs.daily_goal,
        accuracy_overall=round(correct / answered, 3) if answered else None,
        accuracy_by_topic=accuracy,
        weak_topics=weak_topics(topic_accuracy(db, uid)),
        due_flashcards=due_cards,
        active_mistakes=active,
        resolved_mistakes=resolved,
        recent_missed=[
            MissedQuestion(
                mistake_id=m.id,
                prompt=m.prompt_snapshot,
                topic=m.topic,
                error_count=m.error_count,
                status=m.status,
                last_wrong_at=m.last_wrong_at,
            )
            for m in missed
        ],
        activity=[
            ActivityDay(date=today - timedelta(days=i), count=counts.get(today - timedelta(days=i), 0))
            for i in range(13, -1, -1)
        ],
        totals={
            "answered": answered,
            "correct": correct,
            "quizzes_completed": sessions_done,
            "flashcard_reviews": reviews,
            "crunch_outputs": crunches,
            "snapshots": snapshots,
            "notes": notes,
            "flashcards": cards,
        },
    )

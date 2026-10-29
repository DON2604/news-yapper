"""Daily quiz selection + answering. Deterministic database logic only:
no AI call per user, per question or per answer."""

from __future__ import annotations

import hashlib
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.models import (
    Article,
    Event,
    MistakeVaultEntry,
    Question,
    QuizAttempt,
    QuizSession,
    User,
    UserPreferences,
    utcnow,
)
from app.schemas.quiz import (
    AnsweredState,
    AnswerIn,
    AnswerOut,
    DailyQuizOut,
    FinishOut,
    MistakeBrief,
    QuizQuestionPublic,
    QuizSessionOut,
    SessionProgress,
    TopicStat,
)
from app.services import mistakes as mistake_service
from app.services.clock import local_date

MIN_DAILY = 10
MAX_DAILY = 15
CURRENT_AFFAIRS_WINDOW_DAYS = 14
XP_PER_CORRECT = 10
XP_SESSION_BONUS = 20
WEAK_ACCURACY = 0.6


@dataclass
class Pick:
    question: Question
    reason: str


def daily_target(prefs: UserPreferences) -> int:
    return max(MIN_DAILY, min(MAX_DAILY, prefs.daily_goal))


def topic_accuracy(db: Session, user_id: uuid.UUID, days: int = 30) -> dict[str, tuple[int, int]]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        select(Question.exam_topic, func.count(QuizAttempt.id), func.count().filter(QuizAttempt.is_correct))
        .join(Question, Question.id == QuizAttempt.question_id)
        .where(QuizAttempt.user_id == user_id, QuizAttempt.answered_at >= since)
        .group_by(Question.exam_topic)
    ).all()
    return {topic: (int(total), int(correct)) for topic, total, correct in rows}


def weak_topics(stats: dict[str, tuple[int, int]], min_attempts: int = 3) -> list[str]:
    weak = [(t, c / n) for t, (n, c) in stats.items() if n >= min_attempts and c / n < WEAK_ACCURACY]
    return [t for t, _ in sorted(weak, key=lambda x: x[1])]


def _rng(user_id: uuid.UUID, day: date) -> random.Random:
    seed = int(hashlib.sha256(f"{user_id}:{day.isoformat()}".encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def pool_counts(db: Session, day: date) -> tuple[int, int]:
    since = day - timedelta(days=CURRENT_AFFAIRS_WINDOW_DAYS)
    ca = db.scalar(
        select(func.count(Question.id)).where(
            Question.validation_status == "validated",
            Question.kind == "current_affairs",
            Question.active_from >= since,
        )
    )
    gk = db.scalar(
        select(func.count(Question.id)).where(
            Question.validation_status == "validated", Question.kind == "static_gk"
        )
    )
    return int(ca or 0), int(gk or 0)


def select_daily_questions(db: Session, user: User, prefs: UserPreferences, day: date) -> list[Pick]:
    target = daily_target(prefs)
    rng = _rng(user.id, day)
    now = utcnow()
    stats = topic_accuracy(db, user.id)
    weak = set(weak_topics(stats))
    preferred = set(prefs.topics or [])

    recent_correct = set(
        db.scalars(
            select(QuizAttempt.question_id).where(
                QuizAttempt.user_id == user.id,
                QuizAttempt.is_correct.is_(True),
                QuizAttempt.answered_at >= now - timedelta(days=7),
            )
        ).all()
    )
    recently_seen = set(
        db.scalars(
            select(QuizAttempt.question_id).where(
                QuizAttempt.user_id == user.id, QuizAttempt.answered_at >= now - timedelta(days=3)
            )
        ).all()
    )

    picks: list[Pick] = []
    chosen: set[uuid.UUID] = set()

    due_mistakes = db.scalars(
        select(MistakeVaultEntry)
        .where(
            MistakeVaultEntry.user_id == user.id,
            MistakeVaultEntry.status == "active",
            (MistakeVaultEntry.review_after.is_(None)) | (MistakeVaultEntry.review_after <= now),
        )
        .order_by(MistakeVaultEntry.error_count.desc(), MistakeVaultEntry.last_wrong_at)
        .limit(3)
    ).all()
    for entry in due_mistakes:
        q = db.get(Question, entry.question_id)
        if q is not None and q.validation_status == "validated":
            picks.append(Pick(q, "Mistake Vault revision"))
            chosen.add(q.id)

    since = day - timedelta(days=CURRENT_AFFAIRS_WINDOW_DAYS)
    candidates = db.scalars(
        select(Question).where(
            Question.validation_status == "validated",
            (Question.kind == "static_gk")
            | ((Question.kind == "current_affairs") & (Question.active_from >= since)),
        )
    ).all()

    def score(q: Question) -> float:
        s = rng.random()
        if q.exam_topic in weak:
            s += 1.5
        if q.exam_topic in preferred:
            s += 0.8
        if q.kind == "current_affairs" and q.active_from:
            age = max(0, (day - q.active_from).days)
            s += max(0.0, 1.0 - age / CURRENT_AFFAIRS_WINDOW_DAYS)
        if q.id in recently_seen:
            s -= 2.0
        return s

    scored = sorted(
        (q for q in candidates if q.id not in chosen and q.id not in recent_correct),
        key=score,
        reverse=True,
    )
    remaining = target - len(picks)
    ca_quota = round(remaining * 0.6)
    per_topic: dict[str, int] = defaultdict(int)
    for p in picks:
        per_topic[p.question.exam_topic] += 1

    def take(pool: list[Question], limit: int, topic_cap: int) -> None:
        for q in pool:
            if limit <= 0 or len(picks) >= target:
                return
            if q.id in chosen or per_topic[q.exam_topic] >= topic_cap:
                continue
            reason = (
                "Weak topic boost"
                if q.exam_topic in weak
                else ("Current affairs" if q.kind == "current_affairs" else "Static GK")
            )
            picks.append(Pick(q, reason))
            chosen.add(q.id)
            per_topic[q.exam_topic] += 1
            limit -= 1

    current = [q for q in scored if q.kind == "current_affairs"]
    static = [q for q in scored if q.kind == "static_gk"]
    take(current, ca_quota, topic_cap=3)
    take(static, target - len(picks), topic_cap=3)
    # Relax caps (and allow recently-correct questions) if the pool is small.
    if len(picks) < target:
        take(scored, target - len(picks), topic_cap=target)
    if len(picks) < target:
        fallback = [q for q in candidates if q.id not in chosen]
        rng.shuffle(fallback)
        take(fallback, target - len(picks), topic_cap=target)

    head, tail = picks[: len(due_mistakes)], picks[len(due_mistakes) :]
    rng.shuffle(tail)
    return head + tail


def _event_slugs(db: Session, questions: list[Question]) -> dict[uuid.UUID, str]:
    event_ids = {q.event_id for q in questions if q.event_id}
    if not event_ids:
        return {}
    rows = db.execute(
        select(Event.id, Event.slug).where(Event.id.in_(event_ids), Event.status == "published")
    ).all()
    return {eid: slug for eid, slug in rows}


def public_question(q: Question, slug: str | None = None, reason: str | None = None) -> QuizQuestionPublic:
    return QuizQuestionPublic(
        id=q.id,
        prompt=q.prompt,
        options=[str(o) for o in q.options],
        exam_topic=q.exam_topic,
        kind=q.kind,
        difficulty=q.difficulty,
        is_demo=q.is_demo,
        event_slug=slug,
        reason=reason,
    )


def answered_state(attempt: QuizAttempt, q: Question) -> AnsweredState:
    return AnsweredState(
        question_id=q.id,
        selected_index=attempt.selected_index,
        is_correct=attempt.is_correct,
        correct_index=q.correct_index,
        explanation=q.explanation,
        evidence_urls=[str(u) for u in q.evidence_urls or []],
    )


def session_out(
    db: Session, session: QuizSession, reasons: dict[uuid.UUID, str] | None = None
) -> QuizSessionOut:
    ids = [uuid.UUID(str(i)) for i in session.question_ids]
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(ids))).all()}
    ordered = [questions[i] for i in ids if i in questions]
    slugs = _event_slugs(db, ordered)
    attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.session_id == session.id)).all()
    return QuizSessionOut(
        id=session.id,
        type=session.type,
        session_date=session.session_date,
        started_at=session.started_at,
        completed_at=session.completed_at,
        score=session.score,
        question_count=session.question_count,
        xp_earned=session.xp_earned,
        questions=[
            public_question(q, slugs.get(q.event_id) if q.event_id else None, (reasons or {}).get(q.id))
            for q in ordered
        ],
        answers=[answered_state(a, questions[a.question_id]) for a in attempts if a.question_id in questions],
    )


def _existing_daily(db: Session, user: User, day: date) -> QuizSession | None:
    return db.scalar(
        select(QuizSession)
        .where(QuizSession.user_id == user.id, QuizSession.type == "daily", QuizSession.session_date == day)
        .order_by(QuizSession.started_at.desc())
        .limit(1)
    )


def daily_overview(db: Session, user: User, prefs: UserPreferences) -> DailyQuizOut:
    day = local_date(utcnow(), prefs.timezone)
    existing = _existing_daily(db, user, day)
    ca, gk = pool_counts(db, day)
    return DailyQuizOut(
        date=day,
        target_count=daily_target(prefs),
        pool_size=ca + gk,
        current_affairs_available=ca,
        static_gk_available=gk,
        session=session_out(db, existing) if existing else None,
    )


def create_session(
    db: Session, user: User, prefs: UserPreferences, kind: str, article_slug: str | None = None
) -> QuizSessionOut:
    now = utcnow()
    day = local_date(now, prefs.timezone)
    if kind == "daily":
        existing = _existing_daily(db, user, day)
        if existing is not None:
            return session_out(db, existing)
        picks = select_daily_questions(db, user, prefs, day)
        if not picks:
            raise NotFoundError("No validated questions available yet")
        session = QuizSession(
            user_id=user.id,
            type="daily",
            session_date=day,
            question_ids=[str(p.question.id) for p in picks],
            question_count=len(picks),
            started_at=now,
        )
        db.add(session)
        db.commit()
        return session_out(db, session, {p.question.id: p.reason for p in picks})

    if not article_slug:
        raise InvalidInputError("article_slug is required for practice sessions")
    article = db.scalar(
        select(Article)
        .join(Event, Event.id == Article.event_id)
        .where(Event.slug == article_slug, Event.status == "published")
    )
    if article is None:
        raise NotFoundError("Article not found")
    questions = db.scalars(
        select(Question)
        .where(Question.article_id == article.id, Question.validation_status == "validated")
        .order_by(Question.created_at)
    ).all()
    if not questions:
        raise NotFoundError("No practice questions for this article")
    session = QuizSession(
        user_id=user.id,
        type="practice",
        session_date=day,
        question_ids=[str(q.id) for q in questions],
        question_count=len(questions),
        started_at=now,
    )
    db.add(session)
    db.commit()
    return session_out(db, session)


def get_owned_session(db: Session, user: User, session_id: uuid.UUID) -> QuizSession | None:
    return db.scalar(select(QuizSession).where(QuizSession.id == session_id, QuizSession.user_id == user.id))


def _progress(db: Session, session: QuizSession) -> SessionProgress:
    answered = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.session_id == session.id)) or 0
    return SessionProgress(answered=int(answered), total=session.question_count, score=session.score)


def answer(db: Session, user: User, session: QuizSession, payload: AnswerIn) -> AnswerOut:
    if str(payload.question_id) not in {str(i) for i in session.question_ids}:
        raise NotFoundError("Question is not part of this session")
    question = db.get(Question, payload.question_id)
    if question is None:
        raise NotFoundError("Question not found")

    existing = db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.session_id == session.id, QuizAttempt.question_id == question.id
        )
    )
    if existing is not None:
        entry = db.scalar(
            select(MistakeVaultEntry).where(
                MistakeVaultEntry.user_id == user.id, MistakeVaultEntry.question_id == question.id
            )
        )
        return AnswerOut(
            **answered_state(existing, question).model_dump(),
            already_answered=True,
            mistake=MistakeBrief(id=entry.id, status=entry.status, error_count=entry.error_count)
            if entry
            else None,
            progress=_progress(db, session),
        )
    if session.completed_at is not None:
        raise ForbiddenError("Session already finished")

    is_correct = payload.selected_index == question.correct_index
    attempt = QuizAttempt(
        session_id=session.id,
        user_id=user.id,
        question_id=question.id,
        selected_index=payload.selected_index,
        is_correct=is_correct,
        response_ms=payload.response_ms,
        answered_at=utcnow(),
    )
    db.add(attempt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return answer(db, user, session, payload)

    mistake = None
    if is_correct:
        db.execute(
            update(QuizSession).where(QuizSession.id == session.id).values(score=QuizSession.score + 1)
        )
        resolved = mistake_service.record_correct_answer(db, user, question.id)
        if resolved is not None:
            mistake = MistakeBrief(id=resolved.id, status=resolved.status, error_count=resolved.error_count)
    else:
        entry = mistake_service.record_wrong_answer(db, user, question, attempt)
        mistake = MistakeBrief(id=entry.id, status=entry.status, error_count=entry.error_count)
    db.commit()
    db.refresh(session)
    return AnswerOut(
        **answered_state(attempt, question).model_dump(),
        already_answered=False,
        mistake=mistake,
        progress=_progress(db, session),
    )


def topic_breakdown(db: Session, session: QuizSession) -> list[TopicStat]:
    rows = db.execute(
        select(Question.exam_topic, func.count(QuizAttempt.id), func.count().filter(QuizAttempt.is_correct))
        .join(Question, Question.id == QuizAttempt.question_id)
        .where(QuizAttempt.session_id == session.id)
        .group_by(Question.exam_topic)
    ).all()
    return [
        TopicStat(topic=t, attempts=int(n), correct=int(c), accuracy=round(c / n, 2) if n else 0.0)
        for t, n, c in rows
    ]


def finish(db: Session, user: User, session: QuizSession) -> FinishOut:
    if session.completed_at is None:
        session.completed_at = utcnow()
        session.xp_earned = session.score * XP_PER_CORRECT + XP_SESSION_BONUS
        db.commit()
    stats = topic_accuracy(db, user.id)
    return FinishOut(
        session=session_out(db, session),
        topic_breakdown=topic_breakdown(db, session),
        weak_topics=weak_topics(stats),
        xp_earned=session.xp_earned,
    )

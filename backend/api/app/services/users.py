from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.models import (
    AIJob,
    ArticleSnapshot,
    CrunchJob,
    CrunchOutput,
    Flashcard,
    FlashcardReview,
    MistakeVaultEntry,
    Note,
    QuizAttempt,
    QuizSession,
    StudyCollection,
    User,
    UserPreferences,
    utcnow,
)
from app.schemas.me import PasswordLoginIn, PasswordRegisterIn, PreferencesIn, PreferencesOut, UserSyncIn
from app.security.passwords import hash_password, verify_password
from app.security.sanitize import clean_text
from app.services import audit


def sync_user(db: Session, payload: UserSyncIn) -> User:
    settings = get_settings()
    provider_id = payload.auth_provider_id.strip()
    if provider_id.startswith("demo:") and not settings.demo_mode:
        raise ForbiddenError("Demo sign-in is disabled outside DEMO_MODE")

    user = db.scalar(select(User).where(User.auth_provider_id == provider_id))
    name = clean_text(payload.display_name, 120) or "Notun bondhu"
    email = (payload.email or "").strip().lower() or None
    if user is None:
        user = User(auth_provider_id=provider_id, display_name=name, email=email)
        db.add(user)
        db.flush()
        db.add(UserPreferences(user_id=user.id, timezone=settings.app_timezone))
        audit.record(
            db, "user.created", "user", user.id, actor_user_id=user.id, provider=provider_id.split(":")[0]
        )
    else:
        user.display_name = name or user.display_name
        if email:
            user.email = email

    should_be_admin = bool(email and email in settings.admin_email_set) or (
        settings.demo_mode and settings.demo_grant_admin and provider_id == "demo:admin"
    )
    if should_be_admin and not user.is_admin:
        user.is_admin = True
        audit.record(db, "user.admin_granted", "user", user.id, actor_user_id=user.id, via="config")
    db.commit()
    db.refresh(user)
    return user


def register_with_password(db: Session, payload: PasswordRegisterIn) -> User:
    provider_id = f"password:{payload.email}"
    existing = db.scalar(select(User).where(User.auth_provider_id == provider_id))
    if existing is not None:
        raise ConflictError("An account with that email already exists.")
    name = clean_text(payload.display_name, 120) or payload.email.split("@", 1)[0][:120]
    user = User(
        auth_provider_id=provider_id,
        display_name=name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    db.add(UserPreferences(user_id=user.id, timezone=get_settings().app_timezone))
    settings = get_settings()
    if payload.email in settings.admin_email_set:
        user.is_admin = True
        audit.record(db, "user.admin_granted", "user", user.id, actor_user_id=user.id, via="config")
    audit.record(db, "user.created", "user", user.id, actor_user_id=user.id, provider="password")
    db.commit()
    db.refresh(user)
    return user


def authenticate_password(db: Session, payload: PasswordLoginIn) -> User:
    user = db.scalar(select(User).where(User.auth_provider_id == f"password:{payload.email}"))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Email or password didn't match.")
    user.last_seen_at = utcnow()
    db.commit()
    db.refresh(user)
    return user


def get_preferences(db: Session, user: User) -> UserPreferences:
    prefs = db.scalar(select(UserPreferences).where(UserPreferences.user_id == user.id))
    if prefs is None:
        prefs = UserPreferences(user_id=user.id, timezone=get_settings().app_timezone)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def preferences_out(prefs: UserPreferences) -> PreferencesOut:
    return PreferencesOut(
        target_exam=prefs.target_exam,
        target_exams=list(prefs.target_exams or []),
        region=prefs.region,
        topics=list(prefs.topics or []),
        banglish_intensity=prefs.banglish_intensity,
        daily_minutes=prefs.daily_minutes,
        timezone=prefs.timezone,
        daily_goal=prefs.daily_goal,
        tone_preference=prefs.tone_preference,
        study_reminders=prefs.study_reminders,
        reminder_time=prefs.reminder_time,
        crunch_ai_consent=prefs.crunch_ai_consent,
        leaderboard_opt_in=prefs.leaderboard_opt_in,
        onboarded_at=prefs.onboarded_at,
    )


def update_preferences(db: Session, user: User, payload: PreferencesIn) -> UserPreferences:
    prefs = get_preferences(db, user)
    previous_consent = prefs.crunch_ai_consent
    data = payload.model_dump(exclude={"mark_onboarded"})
    data["region"] = clean_text(data["region"], 64) or "India"
    for key, value in data.items():
        setattr(prefs, key, value)
    if payload.mark_onboarded and prefs.onboarded_at is None:
        prefs.onboarded_at = utcnow()
    if previous_consent != prefs.crunch_ai_consent:
        audit.record(
            db,
            "privacy.crunch_consent_changed",
            "user",
            user.id,
            actor_user_id=user.id,
            consent=prefs.crunch_ai_consent,
        )
    db.commit()
    db.refresh(prefs)
    return prefs


def export_user_data(db: Session, user: User) -> dict[str, Any]:
    def rows(model: Any) -> list[dict[str, Any]]:
        items = db.scalars(select(model).where(model.user_id == user.id)).all()
        return [
            {
                c.key: _jsonable(getattr(item, c.key))
                for c in model.__mapper__.column_attrs
                if c.key not in {"user_id", "password_hash"}
            }
            for item in items
        ]

    prefs = get_preferences(db, user)
    return {
        "exported_at": utcnow().isoformat(),
        "user": {
            "id": str(user.id),
            "display_name": user.display_name,
            "email": user.email,
            "created_at": user.created_at.isoformat(),
        },
        "preferences": preferences_out(prefs).model_dump(mode="json"),
        "notes": rows(Note),
        "snapshots": rows(ArticleSnapshot),
        "mistakes": rows(MistakeVaultEntry),
        "quiz_sessions": rows(QuizSession),
        "quiz_attempts": rows(QuizAttempt),
        "collections": rows(StudyCollection),
        "crunch_outputs": rows(CrunchOutput),
        "flashcards": rows(Flashcard),
        "flashcard_reviews": rows(FlashcardReview),
    }


def delete_user(db: Session, user: User) -> None:
    """Hard-delete the account; FK cascades remove all private rows."""
    user_id = user.id
    crunch_ai_job_ids = db.scalars(
        select(CrunchJob.ai_job_id).where(CrunchJob.user_id == user_id, CrunchJob.ai_job_id.is_not(None))
    ).all()
    if crunch_ai_job_ids:
        db.execute(delete(AIJob).where(AIJob.id.in_([j for j in crunch_ai_job_ids if j])))
    db.delete(user)
    audit.record(db, "user.deleted", "user", user_id)
    db.commit()


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from app.ai_config import crunch_disclosure
from app.config import get_settings
from app.schemas.me import MeOut, PreferencesIn, PreferencesOut, ProgressOut, UserSyncIn, UserSyncOut
from app.security.auth import DB, CurrentUser, require_internal
from app.security.rate_limit import rate_limit
from app.services import progress as progress_service
from app.services import users as user_service

router = APIRouter(tags=["me"])


@router.post(
    "/auth/sync", response_model=UserSyncOut, dependencies=[Depends(require_internal)], tags=["auth"]
)
def sync_user(payload: UserSyncIn, db: DB) -> UserSyncOut:
    user = user_service.sync_user(db, payload)
    prefs = user_service.get_preferences(db, user)
    return UserSyncOut(
        user_id=user.id,
        display_name=user.display_name,
        is_admin=user.is_admin,
        onboarded=prefs.onboarded_at is not None,
    )


@router.get("/me", response_model=MeOut)
def me(db: DB, user: CurrentUser) -> MeOut:
    prefs = user_service.get_preferences(db, user)
    settings = get_settings()
    return MeOut(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at,
        preferences=user_service.preferences_out(prefs),
        demo_mode=settings.demo_mode,
        crunch_ai=crunch_disclosure(settings, prefs.crunch_ai_consent),
    )


@router.get("/me/preferences", response_model=PreferencesOut)
def get_preferences(db: DB, user: CurrentUser) -> PreferencesOut:
    return user_service.preferences_out(user_service.get_preferences(db, user))


@router.put("/me/preferences", response_model=PreferencesOut, dependencies=[Depends(rate_limit("prefs", 30))])
def put_preferences(payload: PreferencesIn, db: DB, user: CurrentUser) -> PreferencesOut:
    return user_service.preferences_out(user_service.update_preferences(db, user, payload))


@router.get("/me/export", dependencies=[Depends(rate_limit("export", 5, 300))])
def export(db: DB, user: CurrentUser) -> dict[str, Any]:
    return user_service.export_user_data(db, user)


@router.delete("/me", status_code=204, dependencies=[Depends(rate_limit("delete-me", 3, 300))])
def delete_me(db: DB, user: CurrentUser) -> Response:
    user_service.delete_user(db, user)
    return Response(status_code=204)


@router.get("/progress", response_model=ProgressOut)
def progress(db: DB, user: CurrentUser) -> ProgressOut:
    return progress_service.compute(db, user, user_service.get_preferences(db, user))

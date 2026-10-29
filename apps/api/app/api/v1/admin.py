from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.security.auth import DB, AdminUser, require_admin
from app.security.rate_limit import rate_limit
from app.services import admin as admin_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin), Depends(rate_limit("admin", 120))],
)


class IngestionRunIn(BaseModel):
    source_slug: str | None = Field(default=None, max_length=64)


class ApproveIn(BaseModel):
    approve_questions: bool = False


class RejectIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class SourceToggleIn(BaseModel):
    enabled: bool


@router.get("/overview")
def overview(db: DB) -> dict[str, Any]:
    return admin_service.overview(db)


@router.post("/ingestion/run", status_code=202)
def run_ingestion(payload: IngestionRunIn, db: DB, admin: AdminUser) -> dict[str, Any]:
    run = admin_service.request_ingestion(db, admin, payload.source_slug)
    return {
        "id": str(run.id),
        "status": run.status,
        "message": "Queued - the worker picks this up within a minute.",
    }


@router.get("/ai/usage")
def ai_usage(db: DB, days: int = Query(default=30, ge=1, le=90)) -> dict[str, Any]:
    return admin_service.usage(db, days)


@router.get("/jobs")
def jobs(db: DB, status: str | None = Query(default=None, max_length=16)) -> list[dict[str, Any]]:
    return admin_service.list_jobs(db, status)


@router.get("/review-queue")
def review_queue(db: DB) -> list[dict[str, Any]]:
    return admin_service.review_queue(db)


@router.post("/events/{event_id}/approve")
def approve(event_id: uuid.UUID, payload: ApproveIn, db: DB, admin: AdminUser) -> dict[str, Any]:
    event = admin_service.approve_event(db, admin, event_id, payload.approve_questions)
    return {"id": str(event.id), "status": event.status}


@router.post("/events/{event_id}/reject")
def reject(event_id: uuid.UUID, payload: RejectIn, db: DB, admin: AdminUser) -> dict[str, Any]:
    event = admin_service.reject_event(db, admin, event_id, payload.note)
    return {"id": str(event.id), "status": event.status}


@router.post("/sources/{slug}/toggle")
def toggle_source(slug: str, payload: SourceToggleIn, db: DB, admin: AdminUser) -> dict[str, Any]:
    source = admin_service.toggle_source(db, admin, slug, payload.enabled)
    return {"slug": source.slug, "enabled": source.enabled}

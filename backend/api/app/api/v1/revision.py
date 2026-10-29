from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from app.schemas.study import (
    CrunchIn,
    CrunchJobOut,
    CrunchOutputBrief,
    CrunchOutputOut,
    CrunchPreviewOut,
    FlashcardOut,
    FlashcardReviewIn,
    FlashcardReviewOut,
    RevisionDueOut,
)
from app.security.auth import DB, CurrentUser
from app.security.rate_limit import rate_limit
from app.services import crunch as crunch_service
from app.services import revision as revision_service
from app.services.users import get_preferences

router = APIRouter(dependencies=[Depends(rate_limit("revision", 300))])


@router.get("/revision/due", response_model=RevisionDueOut, tags=["revision"])
def revision_due(db: DB, user: CurrentUser) -> RevisionDueOut:
    return revision_service.due(db, user, get_preferences(db, user).timezone)


@router.get("/flashcards", response_model=list[FlashcardOut], tags=["revision"])
def list_flashcards(db: DB, user: CurrentUser) -> list[FlashcardOut]:
    return [revision_service.flashcard_out(c) for c in revision_service.list_flashcards(db, user)]


@router.post("/flashcards/{card_id}/reviews", response_model=FlashcardReviewOut, tags=["revision"])
def review_flashcard(
    card_id: uuid.UUID, payload: FlashcardReviewIn, db: DB, user: CurrentUser
) -> FlashcardReviewOut:
    card = revision_service.get_owned_card(db, user, card_id)
    if card is None:
        raise HTTPException(404, "Flashcard not found")
    return revision_service.review_card(db, user, card, payload.outcome)


@router.post(
    "/crunch/preview",
    response_model=CrunchPreviewOut,
    tags=["crunch"],
    dependencies=[Depends(rate_limit("crunch-preview", 30))],
)
def crunch_preview(payload: CrunchIn, db: DB, user: CurrentUser) -> CrunchPreviewOut:
    preview, _ = crunch_service.preview(db, user, get_preferences(db, user), payload)
    return preview


@router.post(
    "/crunch",
    response_model=CrunchJobOut,
    status_code=202,
    tags=["crunch"],
    dependencies=[Depends(rate_limit("crunch", 12))],
)
def crunch(payload: CrunchIn, response: Response, db: DB, user: CurrentUser) -> CrunchJobOut | JSONResponse:
    try:
        job, cached = crunch_service.request_crunch(db, user, get_preferences(db, user), payload)
    except crunch_service.CrunchLimitError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        status = 429 if exc.retry_after else 413
        return JSONResponse(status_code=status, content={"detail": str(exc)}, headers=headers)
    response.headers["Location"] = f"/api/v1/crunch/jobs/{job.id}"
    if cached:
        response.status_code = 200
    return crunch_service.job_out(db, job, cached=cached)


@router.get("/crunch/jobs/{job_id}", response_model=CrunchJobOut, tags=["crunch"])
def crunch_job(job_id: uuid.UUID, db: DB, user: CurrentUser) -> CrunchJobOut:
    job = crunch_service.get_owned_job(db, user, job_id)
    if job is None:
        raise HTTPException(404, "Crunch job not found")
    return crunch_service.job_out(db, job)


@router.get("/crunch/outputs", response_model=list[CrunchOutputBrief], tags=["crunch"])
def crunch_outputs(db: DB, user: CurrentUser) -> list[CrunchOutputBrief]:
    return [revision_service.crunch_brief(db, o) for o in crunch_service.list_outputs(db, user)]


@router.get("/crunch/outputs/{output_id}", response_model=CrunchOutputOut, tags=["crunch"])
def crunch_output(output_id: uuid.UUID, db: DB, user: CurrentUser) -> CrunchOutputOut:
    out = crunch_service.get_owned_output(db, user, output_id)
    if out is None:
        raise HTTPException(404, "Crunch output not found")
    return crunch_service.output_out(db, out)

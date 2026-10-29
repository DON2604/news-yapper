from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.quiz import AnswerIn, AnswerOut, CreateSessionIn, DailyQuizOut, FinishOut, QuizSessionOut
from app.security.auth import DB, CurrentUser
from app.security.rate_limit import rate_limit
from app.services import quiz as quiz_service
from app.services.users import get_preferences

router = APIRouter(prefix="/quizzes", tags=["quizzes"], dependencies=[Depends(rate_limit("quiz", 120))])


@router.get("/daily", response_model=DailyQuizOut)
def daily(db: DB, user: CurrentUser) -> DailyQuizOut:
    return quiz_service.daily_overview(db, user, get_preferences(db, user))


@router.post("/sessions", response_model=QuizSessionOut, status_code=201)
def create_session(payload: CreateSessionIn, db: DB, user: CurrentUser) -> QuizSessionOut:
    return quiz_service.create_session(
        db, user, get_preferences(db, user), payload.type, payload.article_slug
    )


@router.get("/sessions/{session_id}", response_model=QuizSessionOut)
def get_session(session_id: uuid.UUID, db: DB, user: CurrentUser) -> QuizSessionOut:
    session = quiz_service.get_owned_session(db, user, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return quiz_service.session_out(db, session)


@router.post("/sessions/{session_id}/answers", response_model=AnswerOut)
def answer(session_id: uuid.UUID, payload: AnswerIn, db: DB, user: CurrentUser) -> AnswerOut:
    session = quiz_service.get_owned_session(db, user, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return quiz_service.answer(db, user, session, payload)


@router.post("/sessions/{session_id}/finish", response_model=FinishOut)
def finish(session_id: uuid.UUID, db: DB, user: CurrentUser) -> FinishOut:
    session = quiz_service.get_owned_session(db, user, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return quiz_service.finish(db, user, session)

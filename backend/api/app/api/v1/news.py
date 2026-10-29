from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.schemas.chat import ChatAskIn, ChatThreadOut
from app.schemas.news import ArticleDetail, EditionOut, NewsArchive, NewsPage
from app.security.auth import DB, CurrentUser, OptionalUser
from app.security.rate_limit import rate_limit
from app.services import chat as chat_service
from app.services import news as news_service

router = APIRouter(tags=["news"], dependencies=[Depends(rate_limit("news", 240))])


@router.get("/news", response_model=NewsPage)
def list_news(
    db: DB,
    user: OptionalUser,
    date_: date | None = Query(default=None, alias="date"),
    category: str | None = Query(default=None, max_length=32),
    exam: str | None = Query(default=None, max_length=16),
    importance: Literal["high", "medium"] | None = None,
    region: Literal["india", "world"] | None = None,
    q: str | None = Query(default=None, max_length=80),
    kind: Literal["all", "ai", "source"] = "all",
    demo: bool | None = None,
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
) -> NewsPage:
    return news_service.list_news(
        db,
        user=user,
        day=date_,
        category=category,
        exam=exam,
        importance=importance,
        region=region,
        q=q,
        kind=kind,
        include_demo=demo,
        cursor=cursor,
        limit=limit,
    )


@router.get("/news/archive", response_model=NewsArchive)
def archive(db: DB, demo: bool | None = None) -> NewsArchive:
    return news_service.list_archive(db, include_demo=demo)


@router.get("/news/{slug}/chat", response_model=ChatThreadOut)
def get_chat(slug: str, db: DB, user: CurrentUser) -> ChatThreadOut:
    return chat_service.get_thread(db, user, slug)


@router.post(
    "/news/{slug}/chat",
    response_model=ChatThreadOut,
    dependencies=[Depends(rate_limit("article_chat", 20, 3600))],
)
def post_chat(slug: str, payload: ChatAskIn, response: Response, db: DB, user: CurrentUser) -> ChatThreadOut:
    thread, queued = chat_service.ask(db, user, slug, payload.message)
    response.status_code = 202 if queued else 200
    return thread


@router.get("/news/{slug}", response_model=ArticleDetail)
def get_news(slug: str, db: DB, user: OptionalUser) -> ArticleDetail:
    detail = news_service.get_article(db, slug[:160], user)
    if detail is None:
        raise HTTPException(404, "Article not found")
    return detail


@router.get("/editions/today", response_model=EditionOut)
def today(db: DB, user: OptionalUser) -> EditionOut:
    return news_service.get_today_edition(db, user)

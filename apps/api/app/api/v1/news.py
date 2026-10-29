from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.news import ArticleDetail, EditionOut, NewsPage
from app.security.auth import DB, OptionalUser
from app.security.rate_limit import rate_limit
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


@router.get("/news/{slug}", response_model=ArticleDetail)
def get_news(slug: str, db: DB, user: OptionalUser) -> ArticleDetail:
    detail = news_service.get_article(db, slug[:160], user)
    if detail is None:
        raise HTTPException(404, "Article not found")
    return detail


@router.get("/editions/today", response_model=EditionOut)
def today(db: DB, user: OptionalUser) -> EditionOut:
    return news_service.get_today_edition(db, user)

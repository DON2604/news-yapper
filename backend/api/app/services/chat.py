"""Article chat. Opening a story never calls a model.

A question is answered from the saved article (retrieval happens in the worker).
The same question on the same article is served from article_chat_cache.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ConflictError, DomainError, InvalidInputError, NotFoundError
from app.models import (
    AIJob,
    Article,
    ArticleChat,
    ArticleChatCache,
    ArticleChatMessage,
    Event,
    User,
    utcnow,
)
from app.schemas.chat import ChatMessageOut, ChatThreadOut
from app.services.clock import app_today, start_of_local_day

CHAT_PRIORITY = 85
DAILY_LIMIT = 30
_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]+", re.UNICODE)


class ChatLimitError(DomainError):
    status_code = 429


def normalise_question(text: str) -> str:
    compact = _SPACE.sub(" ", _PUNCT.sub(" ", text.strip().lower()))
    return compact.strip()


def question_hash(article_id: uuid.UUID, question: str) -> str:
    basis = f"{article_id}:{normalise_question(question)}"
    return hashlib.sha256(basis.encode()).hexdigest()


def _published_article(db: Session, slug: str) -> tuple[Event, Article] | None:
    row = db.execute(
        select(Event, Article)
        .join(Article, Article.event_id == Event.id)
        .where(Event.slug == slug[:160], Event.status == "published")
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def _thread(db: Session, chat: ArticleChat | None, *, available: bool, serious: bool) -> ChatThreadOut:
    if chat is None:
        return ChatThreadOut(available=available, serious=serious, pending=False, messages=[])
    rows = db.scalars(
        select(ArticleChatMessage)
        .where(ArticleChatMessage.chat_id == chat.id)
        .order_by(ArticleChatMessage.created_at, ArticleChatMessage.id)
    ).all()
    messages = [
        ChatMessageOut(
            id=m.id,
            role="user" if m.role == "user" else "assistant",
            body=m.body,
            status="pending" if m.status == "pending" else "failed" if m.status == "failed" else "ready",
            cached=m.cached,
            created_at=m.created_at,
        )
        for m in rows
    ]
    return ChatThreadOut(
        available=available,
        serious=serious,
        pending=any(m.status == "pending" for m in messages),
        messages=messages,
    )


def get_thread(db: Session, user: User, slug: str) -> ChatThreadOut:
    found = _published_article(db, slug)
    if found is None:
        event = db.scalar(select(Event).where(Event.slug == slug[:160], Event.status != "rejected"))
        if event is None:
            raise NotFoundError("Article not found")
        return ChatThreadOut(available=False, serious=event.sensitive, pending=False, messages=[])
    event, article = found
    chat = db.scalar(
        select(ArticleChat).where(ArticleChat.user_id == user.id, ArticleChat.article_id == article.id)
    )
    return _thread(db, chat, available=True, serious=event.sensitive or article.sensitive_story)


def ask(db: Session, user: User, slug: str, message: str) -> tuple[ChatThreadOut, bool]:
    """Returns (thread, queued). queued=False means the answer was already cached."""
    text = message.strip()
    if len(text) < 2 or len(text) > 500:
        raise InvalidInputError("Question should be between 2 and 500 characters.")
    found = _published_article(db, slug)
    if found is None:
        event = db.scalar(select(Event).where(Event.slug == slug[:160], Event.status != "rejected"))
        if event is None:
            raise NotFoundError("Article not found")
        raise InvalidInputError(
            "This story is still a source headline. Chat opens after the saved summary is ready."
        )
    event, article = found
    serious = event.sensitive or article.sensitive_story

    chat = db.scalar(
        select(ArticleChat).where(ArticleChat.user_id == user.id, ArticleChat.article_id == article.id)
    )
    if chat is None:
        chat = ArticleChat(user_id=user.id, article_id=article.id)
        db.add(chat)
        db.flush()

    pending = db.scalar(
        select(ArticleChatMessage.id).where(
            ArticleChatMessage.chat_id == chat.id, ArticleChatMessage.status == "pending"
        )
    )
    if pending is not None:
        raise ConflictError("Agerr reply ta ekhono ashche. Ektu wait kor.")

    settings = get_settings()
    day_start = start_of_local_day(app_today(), settings.app_timezone)
    sent_today = db.scalar(
        select(func.count(ArticleChatMessage.id))
        .join(ArticleChat, ArticleChat.id == ArticleChatMessage.chat_id)
        .where(
            ArticleChat.user_id == user.id,
            ArticleChatMessage.role == "user",
            ArticleChatMessage.created_at >= day_start,
        )
    )
    if int(sent_today or 0) >= DAILY_LIMIT:
        raise ChatLimitError("Aajker chat limit shesh. Kal abar jiggesh koris.")

    now = utcnow()
    digest = question_hash(article.id, text)
    cached = db.scalar(
        select(ArticleChatCache).where(
            ArticleChatCache.article_id == article.id, ArticleChatCache.question_hash == digest
        )
    )
    db.add(
        ArticleChatMessage(
            chat_id=chat.id, role="user", body=text, status="ready", cached=False, created_at=now
        )
    )
    if cached is not None:
        db.add(
            ArticleChatMessage(
                chat_id=chat.id,
                role="assistant",
                body=cached.answer,
                status="ready",
                cached=True,
                created_at=now + timedelta(milliseconds=1),
            )
        )
        db.commit()
        return _thread(db, chat, available=True, serious=serious), False

    assistant = ArticleChatMessage(
        chat_id=chat.id,
        role="assistant",
        body="",
        status="pending",
        cached=False,
        created_at=now + timedelta(milliseconds=1),
    )
    db.add(assistant)
    db.flush()
    db.add(
        AIJob(
            kind="article_chat",
            resource_type="article_chat_message",
            resource_id=assistant.id,
            payload={
                "message_id": str(assistant.id),
                "article_id": str(article.id),
                "question": text,
                "consent": "primary",
            },
            dedupe_key=f"chat:{assistant.id}",
            priority=CHAT_PRIORITY,
            status="queued",
            max_attempts=settings.ai_max_job_attempts,
            token_estimate=1200,
            contains_private_data=True,
            next_run_at=now,
        )
    )
    db.commit()
    return _thread(db, chat, available=True, serious=serious), True

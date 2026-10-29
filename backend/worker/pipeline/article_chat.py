"""Answer a follow-up from stories already saved in the database."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_config import load_routing
from app.config import Settings
from app.models import AIJob, ArticleChatCache, ArticleChatMessage, utcnow
from app.services.chat import question_hash
from pipeline.ai_types import Prepared, ResourceGone
from pipeline.prompts import CHAT_SYSTEM, chat_user_prompt, estimate_tokens
from pipeline.providers.base import GenerationResult
from pipeline.retrieve import load_story, related_stories
from pipeline.validate import ChatAnswerOut, validate_chat_answer


class ArticleChatHandler:
    kind = "article_chat"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.route = load_routing(settings)["article_chat"]

    def prepare(self, db: Session, job: AIJob) -> Prepared:
        message_id = uuid.UUID(str(job.payload.get("message_id") or job.resource_id))
        message = db.get(ArticleChatMessage, message_id)
        article_id = job.payload.get("article_id")
        question = str(job.payload.get("question") or "")
        if message is None or message.status != "pending" or not article_id or not question.strip():
            raise ResourceGone("Chat reply is no longer waiting")
        focus = load_story(db, uuid.UUID(str(article_id)))
        if focus is None:
            raise ResourceGone("Saved article is no longer published")
        related = related_stories(db, focus)
        focus_payload = {
            "date": focus.date,
            "category": focus.category,
            "sensitive": str(focus.sensitive).lower(),
            "text": focus.text,
        }
        related_payload = [
            {
                "date": story.date,
                "category": story.category,
                "sensitive": str(story.sensitive).lower(),
                "text": story.text,
            }
            for story in related
        ]
        user = chat_user_prompt(focus_payload, related_payload, question)
        corpus = "\n".join([focus.text, *[story.text for story in related]])
        return Prepared(
            system=CHAT_SYSTEM,
            user=user,
            schema=ChatAnswerOut.model_json_schema(),
            schema_name="article_chat",
            estimated_tokens=estimate_tokens(CHAT_SYSTEM, user) + self.route.max_output_tokens,
            max_output_tokens=self.route.max_output_tokens,
            context={
                "consent": str(job.payload.get("consent") or "primary"),
                "message_id": str(message.id),
                "article_id": focus.article_id,
                "question": question,
                "corpus": corpus,
                "sensitive": focus.sensitive,
            },
        )

    def accept(
        self, db: Session, job: AIJob, prepared: Prepared, result: GenerationResult, provider: str, model: str
    ) -> str:
        answer = validate_chat_answer(
            result.data, str(prepared.context["corpus"]), sensitive=bool(prepared.context["sensitive"])
        )
        message = db.get(ArticleChatMessage, uuid.UUID(str(prepared.context["message_id"])))
        if message is None:
            raise ResourceGone("Chat message disappeared")
        message.body = answer
        message.status = "ready"
        article_id = uuid.UUID(str(prepared.context["article_id"]))
        digest = question_hash(article_id, str(prepared.context["question"]))
        existing = db.scalar(
            select(ArticleChatCache.id).where(
                ArticleChatCache.article_id == article_id, ArticleChatCache.question_hash == digest
            )
        )
        if existing is None:
            db.add(
                ArticleChatCache(
                    article_id=article_id, question_hash=digest, answer=answer, created_at=utcnow()
                )
            )
        db.commit()
        return f"chat:{provider}:{model}"

    def run_offline(self, db: Session, job: AIJob, prepared: Prepared) -> str:
        raise NotImplementedError("Article chat has no offline engine")

    def on_deferred(self, db: Session, job: AIJob, message: str) -> None:
        return None

    def on_failed(self, db: Session, job: AIJob, code: str, message: str) -> None:
        message_id = job.payload.get("message_id") or job.resource_id
        if message_id is None:
            return
        row = db.get(ArticleChatMessage, uuid.UUID(str(message_id)))
        if row is not None and row.status == "pending":
            row.status = "failed"
            row.body = "Reply ta save hoyni. Ektu pore abar try kor."
            db.commit()

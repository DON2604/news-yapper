"""Build quiz questions by retrieving saved articles. Page loads never run this.

Questions are written once per article and stored. A later worker tick only picks
articles that still have fewer than two validated questions.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai_config import load_routing, provider_settings
from app.config import Settings
from app.models import AIJob, Article, Event, Question, utcnow
from app.services.clock import app_today, start_of_local_day
from pipeline.ai_types import Prepared, ResourceGone
from pipeline.prompts import QUIZ_PROMPT_VERSION, QUIZ_SYSTEM, estimate_tokens, quiz_user_prompt
from pipeline.providers.base import GenerationResult
from pipeline.retrieve import load_story
from pipeline.validate import RagQuizBatchOut, StoredCorpus, validate_quiz_rag

QUIZ_PRIORITY = 60
QUESTIONS_PER_ARTICLE = 2
BATCH_SIZE = 2
MAX_JOBS_PER_DAY = 6


def quiz_provider_ready(settings: Settings) -> bool:
    cfgs = provider_settings(settings)
    route = load_routing(settings)["quiz_prep"]
    return any(
        c.provider in cfgs and cfgs[c.provider].operational and c.resolve_model(cfgs)
        for c in route.candidates
    )


def articles_needing_quiz(db: Session, limit: int = 12) -> list[Article]:
    ready = (
        select(func.count(Question.id))
        .where(Question.article_id == Article.id, Question.validation_status == "validated")
        .correlate(Article)
        .scalar_subquery()
    )
    return list(
        db.scalars(
            select(Article)
            .join(Event, Event.id == Article.event_id)
            .where(
                Event.status == "published",
                Event.is_demo.is_(False),
                Article.is_demo.is_(False),
                ready < QUESTIONS_PER_ARTICLE,
            )
            .order_by(Article.published_at.desc().nulls_last(), Article.created_at.desc())
            .limit(limit)
        ).all()
    )


def plan_quiz_jobs(db: Session, settings: Settings, now: datetime | None = None) -> int:
    now = now or utcnow()
    if not quiz_provider_ready(settings):
        return 0
    today = app_today(now)
    created_today = (
        db.scalar(
            select(func.count(AIJob.id)).where(
                AIJob.kind == "quiz_prep",
                AIJob.created_at >= start_of_local_day(today, settings.app_timezone),
            )
        )
        or 0
    )
    remaining = MAX_JOBS_PER_DAY - int(created_today)
    if remaining <= 0:
        return 0
    articles = articles_needing_quiz(db, limit=remaining * BATCH_SIZE)
    created = 0
    for offset in range(0, len(articles), BATCH_SIZE):
        if created >= remaining:
            break
        batch = articles[offset : offset + BATCH_SIZE]
        ids = sorted(str(a.id) for a in batch)
        dedupe_key = f"quiz:{QUIZ_PROMPT_VERSION}:{hashlib.sha256(','.join(ids).encode()).hexdigest()[:24]}"
        if db.scalar(select(AIJob.id).where(AIJob.dedupe_key == dedupe_key)) is not None:
            continue
        db.add(
            AIJob(
                kind="quiz_prep",
                resource_type="article_batch",
                payload={"article_ids": ids},
                dedupe_key=dedupe_key,
                priority=QUIZ_PRIORITY,
                status="queued",
                max_attempts=settings.ai_max_job_attempts,
                token_estimate=900 * len(batch),
                next_run_at=now,
            )
        )
        created += 1
    db.commit()
    return created


class QuizRagHandler:
    kind = "quiz_prep"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.route = load_routing(settings)["quiz_prep"]

    def prepare(self, db: Session, job: AIJob) -> Prepared:
        ids = [uuid.UUID(i) for i in job.payload.get("article_ids", [])]
        stories = []
        corpora: dict[str, dict[str, object]] = {}
        for article_id in ids:
            story = load_story(db, article_id)
            if story is None:
                continue
            stories.append(
                {
                    "article_id": story.article_id,
                    "date": story.date,
                    "category": story.category,
                    "sensitive": str(story.sensitive).lower(),
                    "text": story.text,
                }
            )
            corpora[story.article_id] = {
                "text": story.text,
                "sensitive": story.sensitive,
                "event_id": story.event_id,
                "event_date": story.date,
                "category": story.category,
                "source_urls": story.source_urls,
                "source_item_ids": story.source_item_ids,
            }
        if not stories:
            raise ResourceGone("Saved articles are no longer published")
        user = quiz_user_prompt(stories)
        return Prepared(
            system=QUIZ_SYSTEM,
            user=user,
            schema=RagQuizBatchOut.model_json_schema(),
            schema_name="quiz_rag",
            estimated_tokens=estimate_tokens(QUIZ_SYSTEM, user) + self.route.max_output_tokens,
            max_output_tokens=self.route.max_output_tokens,
            context={"corpora": corpora},
        )

    def accept(
        self, db: Session, job: AIJob, prepared: Prepared, result: GenerationResult, provider: str, model: str
    ) -> str:
        corpora = {
            key: StoredCorpus(article_id=key, text=str(value["text"]), sensitive=bool(value["sensitive"]))
            for key, value in prepared.context["corpora"].items()
        }
        accepted = validate_quiz_rag(result.data, corpora)
        now = utcnow()
        kept = 0
        for question in accepted:
            meta = prepared.context["corpora"][question.article_id]
            digest = hashlib.sha256((question.prompt + "|" + "|".join(question.options)).encode()).hexdigest()
            event_date = date.fromisoformat(str(meta["event_date"]))
            inserted = db.execute(
                insert(Question)
                .values(
                    id=uuid.uuid4(),
                    event_id=uuid.UUID(str(meta["event_id"])),
                    article_id=uuid.UUID(question.article_id),
                    exam_topic=str(meta["category"]),
                    kind="current_affairs",
                    difficulty="medium",
                    prompt=question.prompt,
                    options=question.options,
                    correct_index=question.correct_index,
                    explanation=question.explanation,
                    evidence_urls=list(meta["source_urls"]),
                    evidence_source_item_ids=list(meta["source_item_ids"]),
                    validation_status="validated",
                    generation_version=f"{QUIZ_PROMPT_VERSION}:{provider}:{model}",
                    content_hash=digest,
                    active_from=event_date,
                    is_demo=False,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["content_hash"])
                .returning(Question.id)
            ).scalar_one_or_none()
            if inserted is not None:
                kept += 1
        db.commit()
        if kept == 0 and accepted:
            return "questions:0"
        return f"questions:{kept}"

    def run_offline(self, db: Session, job: AIJob, prepared: Prepared) -> str:
        raise NotImplementedError("Quiz retrieval has no offline engine")

    def on_deferred(self, db: Session, job: AIJob, message: str) -> None:
        return None

    def on_failed(self, db: Session, job: AIJob, code: str, message: str) -> None:
        return None

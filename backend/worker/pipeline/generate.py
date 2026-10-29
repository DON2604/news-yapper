"""News generation: plan a modest number of batched AI jobs (deterministically, after ingest +
dedupe + scoring) and persist validated output. One article per event, shared by all readers."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai_config import load_routing, provider_settings
from app.config import Settings
from app.models import AIJob, Article, Event, EventSource, Question, Source, SourceItem, utcnow
from app.services.clock import app_today, start_of_local_day
from pipeline.ai_types import Prepared, ResourceGone
from pipeline.prompts import (
    NEWS_PROMPT_VERSION,
    NEWS_SYSTEM,
    EventInput,
    SourceInput,
    estimate_tokens,
    news_user_prompt,
)
from pipeline.providers.base import GenerationResult
from pipeline.validate import EventEvidence, NewsBatchOut, ValidatedArticle, validate_news_batch

NEWS_PRIORITY = 70
MIN_RELEVANCE = 35.0
MAX_PER_TOPIC = 6
BATCH_SIZE = 3
FAILED_NOTE = "AI generation failed"


def news_provider_ready(settings: Settings) -> bool:
    cfgs = provider_settings(settings)
    route = load_routing(settings)["news_batch"]
    return any(
        c.provider in cfgs and cfgs[c.provider].operational and c.resolve_model(cfgs)
        for c in route.candidates
    )


def plan_news_jobs(db: Session, settings: Settings, now: datetime | None = None) -> int:
    now = now or utcnow()
    if not news_provider_ready(settings):
        return 0
    today = app_today(now)
    created_today = (
        db.scalar(
            select(func.count(AIJob.id)).where(
                AIJob.kind == "news_batch",
                AIJob.created_at >= start_of_local_day(today, settings.app_timezone),
            )
        )
        or 0
    )
    remaining = settings.ai_daily_news_job_limit - int(created_today)
    if remaining <= 0:
        return 0
    events = db.scalars(
        select(Event)
        .where(
            Event.status == "discovered",
            Event.is_demo.is_(False),
            Event.date >= today - timedelta(days=1),
            Event.relevance_score >= MIN_RELEVANCE,
            or_(Event.review_note.is_(None), Event.review_note.not_like(f"{FAILED_NOTE}%")),
        )
        .order_by(Event.relevance_score.desc())
        .limit(remaining * BATCH_SIZE * 2)
    ).all()

    per_topic: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        if len(per_topic[event.topic]) < MAX_PER_TOPIC:
            per_topic[event.topic].append(event)
    batches: list[list[Event]] = []
    for group in per_topic.values():
        batches += [group[i : i + BATCH_SIZE] for i in range(0, len(group), BATCH_SIZE)]
    batches.sort(key=lambda b: -max(e.relevance_score for e in b))

    created = 0
    for batch in batches[:remaining]:
        ids = sorted(str(e.id) for e in batch)
        key = hashlib.sha256(",".join(ids).encode()).hexdigest()[:24]
        dedupe_key = f"news:{NEWS_PROMPT_VERSION}:{key}"
        if db.scalar(select(AIJob.id).where(AIJob.dedupe_key == dedupe_key)) is not None:
            continue
        estimate = estimate_tokens(*(e.title for e in batch)) + 400 * len(batch) + 1500
        db.add(
            AIJob(
                kind="news_batch",
                resource_type="event_batch",
                payload={"event_ids": ids},
                dedupe_key=dedupe_key,
                priority=NEWS_PRIORITY,
                status="queued",
                max_attempts=settings.ai_max_job_attempts,
                token_estimate=estimate,
                next_run_at=now,
            )
        )
        for event in batch:
            event.status = "queued"
        created += 1
    db.commit()
    return created


class NewsBatchHandler:
    kind = "news_batch"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.route = load_routing(settings)["news_batch"]

    def prepare(self, db: Session, job: AIJob) -> Prepared:
        ids = [uuid.UUID(i) for i in job.payload.get("event_ids", [])]
        events = [
            e
            for e in db.scalars(select(Event).where(Event.id.in_(ids))).all()
            if e.status in ("queued", "discovered")
        ]
        if not events:
            raise ResourceGone("Events are no longer waiting for generation")
        rows = db.execute(
            select(EventSource.event_id, SourceItem, Source)
            .join(SourceItem, SourceItem.id == EventSource.source_item_id)
            .join(Source, Source.id == SourceItem.source_id)
            .where(EventSource.event_id.in_([e.id for e in events]), SourceItem.fetch_status != "revoked")
        ).all()
        by_event: dict[Any, list[tuple[SourceItem, Source]]] = defaultdict(list)
        for event_id, item, source in rows:
            by_event[event_id].append((item, source))

        inputs: list[EventInput] = []
        evidence: dict[str, EventEvidence] = {}
        for event in events:
            pairs = sorted(by_event.get(event.id, []), key=lambda p: (p[1].tier, -(p[1].authority_weight)))[
                :4
            ]
            if not pairs:
                continue
            inputs.append(
                EventInput(
                    event_id=str(event.id),
                    working_title=event.title,
                    date=event.date.isoformat(),
                    topic_hint=event.topic,
                    sensitive_hint=event.sensitive,
                    sources=[
                        SourceInput(
                            id=str(item.id),
                            publisher=item.publisher or source.name,
                            published_at=item.published_at.isoformat() if item.published_at else None,
                            url=item.original_url,
                            title=item.original_title,
                            excerpt=item.short_excerpt,
                        )
                        for item, source in pairs
                    ],
                )
            )
            evidence[str(event.id)] = EventEvidence(
                event_id=str(event.id),
                sensitive=event.sensitive,
                item_texts={str(i.id): f"{i.original_title}. {i.short_excerpt or ''}" for i, _ in pairs},
                item_urls={str(i.id): i.original_url for i, _ in pairs},
            )
        if not inputs:
            raise ResourceGone("No usable source evidence for these events")
        user = news_user_prompt(inputs)
        return Prepared(
            system=NEWS_SYSTEM,
            user=user,
            schema=NewsBatchOut.model_json_schema(),
            schema_name="news_batch",
            estimated_tokens=estimate_tokens(NEWS_SYSTEM, user) + self.route.max_output_tokens,
            max_output_tokens=self.route.max_output_tokens,
            context={"evidence": evidence},
        )

    def accept(
        self, db: Session, job: AIJob, prepared: Prepared, result: GenerationResult, provider: str, model: str
    ) -> str:
        validated = validate_news_batch(result.data, prepared.context["evidence"], app_today())
        count = persist_articles(db, self.settings, validated, prepared.context["evidence"], provider, model)
        return f"articles:{count}"

    def run_offline(self, db: Session, job: AIJob, prepared: Prepared) -> str:
        raise NotImplementedError("News generation has no offline engine")

    def on_deferred(self, db: Session, job: AIJob, message: str) -> None:
        return None

    def on_failed(self, db: Session, job: AIJob, code: str, message: str) -> None:
        ids = [uuid.UUID(i) for i in job.payload.get("event_ids", [])]
        for event in db.scalars(select(Event).where(Event.id.in_(ids), Event.status == "queued")).all():
            event.status = "discovered"
            event.review_note = f"{FAILED_NOTE}: {code}"
        db.commit()


def article_content_hash(evidence: EventEvidence, provider: str, model: str) -> str:
    basis = {
        "facts": sorted(evidence.item_texts.items()),
        "prompt": NEWS_PROMPT_VERSION,
        "model": f"{provider}:{model}",
        "tone": "banglish-genz",
    }
    return hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()


def persist_articles(
    db: Session,
    settings: Settings,
    validated: list[ValidatedArticle],
    evidence: dict[str, EventEvidence],
    provider: str,
    model: str,
) -> int:
    now = utcnow()
    count = 0
    for v in validated:
        event = db.get(Event, uuid.UUID(v.event_id))
        if event is None:
            continue
        ev = evidence[v.event_id]
        art = v.article
        article = db.scalar(select(Article).where(Article.event_id == event.id))
        if article is None:
            article = Article(event_id=event.id, content_hash=article_content_hash(ev, provider, model))
            db.add(article)
        else:
            article.content_hash = article_content_hash(ev, provider, model)
        article.headline = art.headline_banglish
        article.banglish_summary = art.banglish_summary
        article.neutral_summary = art.neutral_summary
        article.why_matters = art.why_it_matters
        article.key_facts = v.key_facts
        article.exam_tags = list(dict.fromkeys(art.exam_tags))
        article.mnemonics = []
        article.category = art.category
        article.importance_score = art.importance_score
        article.sensitive_story = v.sensitive
        article.ai_provider = provider
        article.ai_model = model
        article.prompt_version = NEWS_PROMPT_VERSION
        article.confidence_flags = {
            "uncertainties": art.uncertainties,
            "validation_flags": v.flags,
            "checked_at": now.isoformat(),
        }
        event.topic = art.category
        event.sensitive = event.sensitive or v.sensitive
        if settings.ai_auto_publish_validated and v.publishable:
            event.status = "published"
            article.published_at = now
            article.verified_at = now
            article.verification_method = "automated_evidence_check"
        else:
            event.status = "needs_review"
            article.verified_at = None
            article.published_at = None
        db.flush()
        for q in v.questions:
            digest = hashlib.sha256((q.prompt + "|" + "|".join(q.options)).encode()).hexdigest()
            db.execute(
                insert(Question)
                .values(
                    id=uuid.uuid4(),
                    event_id=event.id,
                    article_id=article.id,
                    exam_topic=art.category,
                    kind="current_affairs",
                    difficulty="medium",
                    prompt=q.prompt,
                    options=q.options,
                    correct_index=q.correct_index,
                    explanation=q.explanation,
                    evidence_urls=[ev.item_urls[i] for i in q.evidence_ids if i in ev.item_urls],
                    evidence_source_item_ids=q.evidence_ids,
                    validation_status=q.status,
                    generation_version=f"{NEWS_PROMPT_VERSION}:{provider}:{model}",
                    content_hash=digest,
                    active_from=event.date,
                    is_demo=False,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["content_hash"])
            )
        count += 1
    db.commit()
    return count

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_config import load_routing, provider_settings
from app.config import get_settings
from app.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.models import (
    AIJob,
    AIUsage,
    Article,
    Event,
    IngestionRun,
    Question,
    QuotaState,
    Source,
    User,
    WorkerLease,
    utcnow,
)
from app.services import audit
from app.services.news import _sources_for


def _iso(value: Any) -> Any:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def quota_view(q: QuotaState) -> dict[str, Any]:
    return {
        "provider": q.provider,
        "project_id": q.project_id,
        "model": q.model,
        "day_key": _iso(q.day_key),
        "daily_spent_requests": q.daily_spent_requests,
        "daily_reserved_requests": q.daily_reserved_requests,
        "daily_spent_tokens": q.daily_spent_tokens,
        "blocked_until": _iso(q.blocked_until),
        "block_reason": q.block_reason,
        "circuit_open_until": _iso(q.circuit_open_until),
        "consecutive_failures": q.consecutive_failures,
        "last_request_at": _iso(q.last_request_at),
        "last_success_at": _iso(q.last_success_at),
        "available": q.available,
        "availability_note": q.availability_note,
        "observed_limits": q.observed_limits or {},
    }


def job_view(job: AIJob) -> dict[str, Any]:
    payload = dict(job.payload or {})
    if job.contains_private_data:
        payload = {k: v for k, v in payload.items() if k in ("crunch_job_id", "engine")}
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "priority": job.priority,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "next_run_at": _iso(job.next_run_at),
        "lease_owner": job.lease_owner,
        "lease_until": _iso(job.lease_until),
        "last_provider": job.last_provider,
        "last_model": job.last_model,
        "attempted_providers": job.attempted_providers or [],
        "error_code": job.error_code,
        "error_detail": (job.error_detail or "")[:300] or None,
        "token_estimate": job.token_estimate,
        "contains_private_data": job.contains_private_data,
        "payload": payload,
        "created_at": _iso(job.created_at),
        "completed_at": _iso(job.completed_at),
    }


def overview(db: Session) -> dict[str, Any]:
    settings = get_settings()
    now = utcnow()
    sources = db.scalars(select(Source).order_by(Source.tier, Source.name)).all()
    by_status = dict(db.execute(select(AIJob.status, func.count()).group_by(AIJob.status)).all())
    by_kind = dict(
        db.execute(
            select(AIJob.kind, func.count())
            .where(AIJob.status.in_(("queued", "deferred", "running")))
            .group_by(AIJob.kind)
        ).all()
    )
    events_by_status = dict(db.execute(select(Event.status, func.count()).group_by(Event.status)).all())
    generated_today = db.scalar(
        select(func.count(Article.id)).where(
            Article.created_at >= now - timedelta(days=1), Article.is_demo.is_(False)
        )
    )
    last_success = db.scalar(select(func.max(AIUsage.ended_at)).where(AIUsage.outcome == "success"))
    runs = db.scalars(select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(10)).all()
    lease = db.get(WorkerLease, "coordinator")
    providers = provider_settings(settings)
    routing = load_routing(settings)
    return {
        "demo_mode": settings.demo_mode,
        "live_ingestion_enabled": settings.enable_live_ingestion,
        "auto_publish_validated": settings.ai_auto_publish_validated,
        "sources": [
            {
                "id": str(s.id),
                "slug": s.slug,
                "name": s.name,
                "type": s.type,
                "tier": s.tier,
                "enabled": s.enabled,
                "feed_url": s.feed_url,
                "home_url": s.home_url,
                "fetch_interval_minutes": s.fetch_interval_minutes,
                "last_fetch_at": _iso(s.last_fetch_at),
                "last_success_at": _iso(s.last_success_at),
                "last_error": s.last_error,
                "consecutive_failures": s.consecutive_failures,
                "legal_notes": s.legal_notes,
            }
            for s in sources
        ],
        "queue": {"by_status": by_status, "active_by_kind": by_kind},
        "events_by_status": events_by_status,
        "review_queue_count": int(events_by_status.get("needs_review", 0))
        + int(events_by_status.get("generated", 0)),
        "generated_articles_last_24h": int(generated_today or 0),
        "last_ai_success_at": _iso(last_success),
        "providers": [p.public_view() for p in providers.values()],
        "routing": {
            task: [
                {
                    "provider": c.provider,
                    "model_role": c.model_role,
                    "model": c.resolve_model(providers) or None,
                }
                for c in route.candidates
            ]
            for task, route in routing.items()
        },
        "quota_states": [
            quota_view(q)
            for q in db.scalars(
                select(QuotaState).where(QuotaState.provider != "*").order_by(QuotaState.provider)
            ).all()
        ],
        "ingestion_runs": [
            {
                "id": str(r.id),
                "status": r.status,
                "trigger": r.trigger,
                "source_id": str(r.source_id) if r.source_id else None,
                "created_at": _iso(r.created_at),
                "started_at": _iso(r.started_at),
                "ended_at": _iso(r.ended_at),
                "fetched": r.fetched_count,
                "inserted": r.inserted_count,
                "duplicates": r.duplicate_count,
                "clustered": r.clustered_count,
                "errors": r.error_details or [],
            }
            for r in runs
        ],
        "worker": {
            "owner": lease.owner if lease else None,
            "lease_until": _iso(lease.lease_until) if lease else None,
            "heartbeat_at": _iso(lease.heartbeat_at) if lease else None,
            "alive": bool(lease and lease.lease_until > now),
            "info": lease.info if lease else {},
        },
    }


def usage(db: Session, days: int = 30) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        select(
            AIUsage.provider,
            AIUsage.model,
            AIUsage.day_key,
            AIUsage.outcome,
            func.count(),
            func.coalesce(func.sum(AIUsage.input_tokens), 0),
            func.coalesce(func.sum(AIUsage.output_tokens), 0),
        )
        .where(AIUsage.started_at >= since)
        .group_by(AIUsage.provider, AIUsage.model, AIUsage.day_key, AIUsage.outcome)
        .order_by(AIUsage.day_key.desc())
    ).all()
    return {
        "since": since.isoformat(),
        "rows": [
            {
                "provider": p,
                "model": m,
                "day": _iso(d),
                "outcome": o,
                "requests": int(n),
                "input_tokens": int(i or 0),
                "output_tokens": int(out or 0),
            }
            for p, m, d, o, n, i, out in rows
        ],
        "quota_states": [
            quota_view(q) for q in db.scalars(select(QuotaState).where(QuotaState.provider != "*")).all()
        ],
        "cost_note": "Costs are not computed: free-tier usage has no price; paid fallback is disabled by default.",
    }


def list_jobs(db: Session, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    stmt = select(AIJob)
    if status:
        stmt = stmt.where(AIJob.status == status)
    jobs = db.scalars(stmt.order_by(AIJob.updated_at.desc()).limit(min(limit, 200))).all()
    return [job_view(j) for j in jobs]


def review_queue(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Event, Article)
        .outerjoin(Article, Article.event_id == Event.id)
        .where(Event.status.in_(("needs_review", "generated")))
        .order_by(Event.relevance_score.desc())
        .limit(50)
    ).all()
    event_ids = [e.id for e, _ in rows]
    sources = _sources_for(db, event_ids)
    out = []
    for event, article in rows:
        questions = []
        if article is not None:
            questions = [
                {
                    "id": str(q.id),
                    "prompt": q.prompt,
                    "options": q.options,
                    "correct_index": q.correct_index,
                    "validation_status": q.validation_status,
                }
                for q in db.scalars(select(Question).where(Question.article_id == article.id)).all()
            ]
        out.append(
            {
                "event_id": str(event.id),
                "slug": event.slug,
                "title": event.title,
                "status": event.status,
                "topic": event.topic,
                "sensitive": event.sensitive,
                "relevance_score": event.relevance_score,
                "sources": [s.model_dump(mode="json") for s in sources.get(event.id, [])],
                "draft": {
                    "headline": article.headline,
                    "banglish_summary": article.banglish_summary,
                    "neutral_summary": article.neutral_summary,
                    "why_matters": article.why_matters,
                    "key_facts": article.key_facts,
                    "confidence_flags": article.confidence_flags,
                    "ai_provider": article.ai_provider,
                    "ai_model": article.ai_model,
                }
                if article is not None
                else None,
                "questions": questions,
            }
        )
    return out


def approve_event(db: Session, admin: User, event_id: uuid.UUID, approve_questions: bool = False) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    article = db.scalar(select(Article).where(Article.event_id == event.id))
    if article is None or event.status not in ("needs_review", "generated"):
        raise InvalidInputError("Only generated or needs-review events with an article can be approved")
    now = utcnow()
    event.status = "published"
    event.reviewed_by = admin.id
    event.reviewed_at = now
    article.published_at = article.published_at or now
    article.verified_at = now
    article.verification_method = "editor_review"
    if approve_questions:
        for q in db.scalars(
            select(Question).where(
                Question.article_id == article.id, Question.validation_status == "needs_review"
            )
        ).all():
            q.validation_status = "validated"
    audit.record(db, "event.approved", "event", event.id, actor_user_id=admin.id, questions=approve_questions)
    db.commit()
    return event


def reject_event(db: Session, admin: User, event_id: uuid.UUID, note: str | None) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    event.status = "rejected"
    event.review_note = (note or "")[:500] or None
    event.reviewed_by = admin.id
    event.reviewed_at = utcnow()
    audit.record(db, "event.rejected", "event", event.id, actor_user_id=admin.id)
    db.commit()
    return event


def request_ingestion(db: Session, admin: User, source_slug: str | None) -> IngestionRun:
    settings = get_settings()
    if not settings.enable_live_ingestion:
        raise ForbiddenError("Live ingestion is disabled (ENABLE_LIVE_INGESTION=false).")
    source = None
    if source_slug:
        source = db.scalar(select(Source).where(Source.slug == source_slug))
        if source is None:
            raise NotFoundError("Unknown source")
    same_target = IngestionRun.source_id == source.id if source else IngestionRun.source_id.is_(None)
    pending = db.scalar(select(IngestionRun).where(IngestionRun.status == "requested", same_target))
    if pending is not None:
        return pending
    run = IngestionRun(
        status="requested", trigger="admin", requested_by=admin.id, source_id=source.id if source else None
    )
    db.add(run)
    audit.record(
        db, "ingestion.requested", "ingestion_run", None, actor_user_id=admin.id, source=source_slug or "all"
    )
    db.commit()
    db.refresh(run)
    return run


def toggle_source(db: Session, admin: User, slug: str, enabled: bool) -> Source:
    source = db.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        raise NotFoundError("Unknown source")
    source.enabled = enabled
    audit.record(db, "source.toggled", "source", source.id, actor_user_id=admin.id, enabled=enabled)
    db.commit()
    return source

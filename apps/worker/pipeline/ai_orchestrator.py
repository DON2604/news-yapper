"""AIOrchestrator: the ONLY place that calls an AI provider (news, Crunch, any future task).

Per job cycle:
  candidates (routing table, provider health, configured model, privacy consent)
    -> quota reservation (persistent ledger) -> provider call -> validation -> persist
  * at most AI_MAX_PROVIDER_ATTEMPTS_PER_CYCLE provider calls (default 2): no ping-pong
  * provider fallback (Gemini -> Groq) and model fallback (Groq quality -> Groq fallback)
    are both just later candidates in the routing table
  * 429 minute limits: Retry-After or full-jitter backoff; daily quota: defer to reset;
    5xx/timeouts: bounded retries + circuit breaker; 400/401/403/404: permanent
  * after AI_MAX_JOB_ATTEMPTS calls the job is dead-lettered and its resource is told
"""

from __future__ import annotations

import logging
import os
import random
import socket
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_config import Candidate, load_routing, provider_settings
from app.config import Settings
from app.models import AIJob, AIUsage, utcnow
from app.services.clock import tz
from pipeline.ai_types import JobHandler, Prepared, ResourceGone
from pipeline.crunch import CrunchHandler
from pipeline.generate import NewsBatchHandler
from pipeline.job_queue import JobQueue
from pipeline.providers.base import (
    AIProvider,
    GenerationRequest,
    InvalidOutput,
    ModelUnavailable,
    ProviderError,
)
from pipeline.providers.gemini import GeminiProvider
from pipeline.providers.groq import GroqProvider
from pipeline.quota_manager import Denial, QuotaManager
from pipeline.validate import OutputRejected

log = logging.getLogger("aks.ai")
BACKOFF_CAPS_SECONDS = (30, 120, 480, 1800)
NO_PROVIDER_RETRY = timedelta(minutes=30)
PERMANENT_DENIAL_RETRY = timedelta(hours=6)
FAIRNESS_RETRY = timedelta(minutes=10)


@dataclass
class JobOutcome:
    job_id: uuid.UUID
    status: str
    detail: str = ""


def build_providers(settings: Settings) -> dict[str, AIProvider]:
    cfgs = provider_settings(settings)
    providers: dict[str, AIProvider] = {}
    if cfgs["gemini"].operational:
        providers["gemini"] = GeminiProvider(cfgs["gemini"])
    if cfgs["groq"].operational:
        providers["groq"] = GroqProvider(cfgs["groq"])
    return providers


def default_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


class AIOrchestrator:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings: Settings,
        *,
        providers: dict[str, AIProvider] | None = None,
        clock: Callable[[], datetime] = utcnow,
        rng: random.Random | None = None,
        owner: str | None = None,
        handlers: dict[str, JobHandler] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.clock = clock
        self.rng = rng or random.Random()
        self.cfgs = provider_settings(settings)
        self.providers = build_providers(settings) if providers is None else providers
        self.routing = load_routing(settings)
        self.quota = QuotaManager(session_factory, self.cfgs, settings, clock)
        self.queue = JobQueue(session_factory, owner or default_owner(), clock=clock)
        self.handlers: dict[str, JobHandler] = handlers or {
            "news_batch": NewsBatchHandler(settings),
            "crunch": CrunchHandler(settings),
        }

    # -- scheduling ------------------------------------------------------------
    def run_once(self, max_jobs: int = 3) -> list[JobOutcome]:
        outcomes: list[JobOutcome] = []
        for _ in range(max_jobs):
            job_id = self.queue.claim()
            if job_id is None:
                break
            try:
                outcomes.append(self.process(job_id))
            except Exception as exc:  # noqa: BLE001 - never leave a job leased after a bug
                log.exception("Unhandled error processing job %s", job_id)
                self.queue.defer(job_id, self.clock() + timedelta(minutes=5), "worker_error", repr(exc)[:300])
                outcomes.append(JobOutcome(job_id, "deferred", "worker_error"))
        return outcomes

    def _crunch_share_exceeded(self) -> bool:
        """Reserve budget for news: AI Crunch may use only AI_CRUNCH_DAILY_SHARE of each provider's day."""
        if not self.queue.waiting_counts().get("news_batch"):
            return False
        now = self.clock()
        with self.session_factory() as db:
            for name, cfg in self.cfgs.items():
                if name not in self.providers or not cfg.operational:
                    continue
                budget = cfg.effective(cfg.rpd_budget) or 0
                used = db.scalar(
                    select(func.count(AIUsage.id)).where(
                        AIUsage.provider == name,
                        AIUsage.kind == "crunch",
                        AIUsage.day_key == self.quota.day_key(name, now),
                    )
                )
                if (used or 0) < budget * self.settings.ai_crunch_daily_share:
                    return False
        return True

    def _candidates(self, job: AIJob, consent: str) -> list[tuple[Candidate, str]]:
        route = self.routing.get(job.kind)
        if route is None:
            return []
        operational = [
            c for c in route.candidates if c.provider in self.providers and self.cfgs[c.provider].operational
        ]
        primary = operational[0].provider if operational else None
        allow_private_fallback = (
            consent == "allow_fallback" and self.settings.ai_allow_private_notes_provider_fallback
        )
        out: list[tuple[Candidate, str]] = []
        seen: set[tuple[str, str]] = set()
        for cand in operational:
            model = cand.resolve_model(self.cfgs)
            if not model or (cand.provider, model) in seen:
                continue
            if job.contains_private_data:
                if consent == "none":
                    continue
                if cand.provider != primary and not allow_private_fallback:
                    continue
            seen.add((cand.provider, model))
            out.append((cand, model))
        return out

    def _backoff(self, attempts: int) -> float:
        cap = BACKOFF_CAPS_SECONDS[min(max(attempts, 1), len(BACKOFF_CAPS_SECONDS)) - 1]
        return max(5.0, self.rng.uniform(0, cap))

    def _fmt(self, when: datetime) -> str:
        return when.astimezone(tz(self.settings.app_timezone)).strftime("%d %b %H:%M")

    # -- processing ------------------------------------------------------------
    def process(self, job_id: uuid.UUID) -> JobOutcome:
        with self.session_factory() as db:
            job = db.get(AIJob, job_id)
            assert job is not None
            handler = self.handlers.get(job.kind)
            if handler is None:
                self.queue.fail(job_id, "no_handler", f"No handler for job kind {job.kind}")
                return JobOutcome(job_id, "dead_letter", "no_handler")
            try:
                prepared = handler.prepare(db, job)
            except ResourceGone as gone:
                db.rollback()
                handler.on_failed(db, job, "resource_gone", str(gone))
                self.queue.fail(job_id, "resource_gone", str(gone), dead_letter=False)
                return JobOutcome(job_id, "failed", str(gone))
            if prepared.offline:
                ref = handler.run_offline(db, job, prepared)
                self.queue.complete(job_id, ref)
                return JobOutcome(job_id, "succeeded", ref)
            job_snapshot = {"attempts": job.attempts, "max_attempts": job.max_attempts, "kind": job.kind}
            consent = str(prepared.context.get("consent", (job.payload or {}).get("consent", "none")))
            if job.contains_private_data and consent == "none":
                message = (
                    "AI Crunch needs your consent (Settings -> Privacy) - or run it with the offline engine."
                )
                handler.on_failed(db, job, "consent_required", message)
                self.queue.fail(job_id, "consent_required", message, dead_letter=False)
                return JobOutcome(job_id, "failed", "consent_required")
            candidates = self._candidates(job, consent)
            if not candidates:
                until = self.clock() + NO_PROVIDER_RETRY
                message = (
                    "Waiting for an AI provider: none is configured/eligible for this job "
                    f"(next check {self._fmt(until)})."
                )
                handler.on_deferred(db, job, message)
                self.queue.defer(job_id, until, "no_provider_available", message)
                return JobOutcome(job_id, "deferred", "no_provider_available")
            if job.kind == "crunch" and self._crunch_share_exceeded():
                until = self.clock() + FAIRNESS_RETRY
                message = (
                    "Today's AI share for Crunch is used up - news publication has priority. Retrying soon."
                )
                handler.on_deferred(db, job, message)
                self.queue.defer(job_id, until, "crunch_share_exhausted", message)
                return JobOutcome(job_id, "deferred", "crunch_share_exhausted")

        return self._attempt(job_id, handler, prepared, candidates, job_snapshot)

    def _attempt(
        self,
        job_id: uuid.UUID,
        handler: JobHandler,
        prepared: Prepared,
        candidates: list[tuple[Candidate, str]],
        snapshot: dict[str, Any],
    ) -> JobOutcome:
        calls = 0
        denials: list[Denial] = []
        errors: list[ProviderError] = []
        for cand, model in candidates:
            if calls >= max(1, self.settings.ai_max_provider_attempts_per_cycle):
                break
            reservation = self.quota.reserve(
                cand.provider,
                model,
                kind=snapshot["kind"],
                job_id=job_id,
                estimated_tokens=prepared.estimated_tokens,
            )
            if isinstance(reservation, Denial):
                log.info("Job %s: %s/%s denied: %s", job_id, cand.provider, model, reservation.reason)
                denials.append(reservation)
                continue
            calls += 1
            self.queue.record_attempt(job_id, cand.provider, model, "started")
            cfg = self.cfgs[cand.provider]
            request = GenerationRequest(
                model=model,
                system_prompt=prepared.system,
                user_prompt=prepared.user,
                json_schema=prepared.schema,
                schema_name=prepared.schema_name,
                max_output_tokens=min(prepared.max_output_tokens, cfg.max_output_tokens),
            )
            try:
                result = self.providers[cand.provider].generate_json(request)
            except ProviderError as err:
                self.quota.reconcile(reservation, err.outcome, error=err, headers=err.headers)
                self.queue.update_last_attempt(job_id, err.outcome)
                if isinstance(err, ModelUnavailable):
                    self.quota.set_availability(cand.provider, model, False, str(err)[:200])
                log.warning("Job %s: %s/%s failed: %s (%s)", job_id, cand.provider, model, err.outcome, err)
                errors.append(err)
                continue
            try:
                with self.session_factory() as db:
                    job = db.get(AIJob, job_id)
                    assert job is not None
                    ref = handler.accept(db, job, prepared, result, cand.provider, model)
            except OutputRejected as rejected:
                self.quota.reconcile(
                    reservation, "invalid_output", usage=result.usage, headers=result.headers
                )
                self.queue.update_last_attempt(job_id, "invalid_output")
                log.warning("Job %s: %s/%s output rejected: %s", job_id, cand.provider, model, rejected)
                errors.append(InvalidOutput(str(rejected)))
                continue
            self.quota.reconcile(reservation, "success", usage=result.usage, headers=result.headers)
            self.queue.update_last_attempt(job_id, "success")
            self.queue.complete(job_id, ref)
            return JobOutcome(job_id, "succeeded", ref)
        return self._after_failed_cycle(job_id, handler, denials, errors, snapshot["attempts"] + calls)

    def _after_failed_cycle(
        self,
        job_id: uuid.UUID,
        handler: JobHandler,
        denials: list[Denial],
        errors: list[ProviderError],
        attempts: int,
    ) -> JobOutcome:
        now = self.clock()
        with self.session_factory() as db:
            job = db.get(AIJob, job_id)
            assert job is not None
            last = errors[-1] if errors else None
            waiting = [d for d in denials if not d.permanent and d.retry_at]

            if errors and attempts >= job.max_attempts:
                message = (
                    f"Gave up after {attempts} provider attempts (last: {last.outcome if last else '?'})."
                )
                handler.on_failed(db, job, "max_attempts", message)
                self.queue.fail(job_id, "max_attempts", f"{message} {last}")
                return JobOutcome(job_id, "dead_letter", message)
            if errors and all(e.permanent for e in errors) and not waiting:
                message = f"Provider rejected the request permanently ({last.outcome if last else '?'}); admin action needed."
                handler.on_failed(db, job, last.outcome if last else "permanent_error", message)
                self.queue.fail(job_id, last.outcome if last else "permanent_error", f"{message} {last}")
                return JobOutcome(job_id, "dead_letter", message)

            if errors:
                hints = [e.retry_after for e in errors if e.retry_after]
                until = now + timedelta(seconds=max(hints) if hints else self._backoff(attempts))
                code = last.outcome if last else "provider_error"
                reason = f"{code}: {last}" if last else code
            elif waiting:
                until = min(d.retry_at for d in waiting if d.retry_at)
                code = "quota_wait"
                reason = "; ".join(d.reason for d in denials)
            else:
                until = now + PERMANENT_DENIAL_RETRY
                code = "no_eligible_provider"
                reason = "; ".join(d.reason for d in denials) or "no provider could take this job"

            until = max(until, now + timedelta(seconds=5))
            message = f"Waiting for AI quota/provider - retrying after {self._fmt(until)} ({reason[:160]})."
            handler.on_deferred(db, job, message)
            self.queue.defer(job_id, until, code, reason)
            return JobOutcome(job_id, "deferred", code)

    # -- model discovery -------------------------------------------------------
    def sync_models(self) -> dict[str, Any]:
        report: dict[str, Any] = {}
        for name, provider in self.providers.items():
            cfg = self.cfgs[name]
            try:
                models = provider.list_models()
            except ProviderError as err:
                report[name] = {"error": f"{err.outcome}: {err}"}
                continue
            listed = {m.id for m in models if m.active and m.supports_generation}
            entry: dict[str, Any] = {"listed_count": len(listed)}
            for role, model in cfg.models.items():
                if not model:
                    continue
                ok = model in listed
                self.quota.set_availability(
                    name, model, ok, None if ok else f"not listed by {name} models endpoint"
                )
                entry[role] = {"model": model, "available": ok}
            report[name] = entry
        return report

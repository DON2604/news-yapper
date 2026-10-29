"""Persistent, project-wide quota ledger in Postgres.

Every provider call must hold a Reservation from here. Reservations are serialised
with row locks (a global row + the provider/model row) so concurrent workers or a
redeploy can never double-spend the budget. Budgets are the operator-configured
values times the safety factor; nothing here claims to know real provider quotas.

Windows:
  * daily (RPD/TPD) keyed by the provider's own reset timezone - Gemini resets at
    midnight America/Los_Angeles, not UTC midnight
  * rolling 60 s window (RPM/TPM) derived from ai_usage rows (reservations included)
  * provider-wide minimum gap between requests, provider + global concurrency caps
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai_config import ProviderSettings
from app.config import Settings
from app.models import AIUsage, QuotaState, utcnow
from app.services.clock import local_date, next_local_midnight
from pipeline.providers.base import ProviderError, Usage, parse_duration

GLOBAL_KEY = ("*", "*", "*")
STALE_RESERVATION = timedelta(minutes=10)
CIRCUIT_THRESHOLD = 3
WINDOW = timedelta(seconds=60)
TOKEN_SPENDING_OUTCOMES = {"success", "invalid_output", "timeout", "abandoned"}


@dataclass(frozen=True)
class Reservation:
    usage_id: uuid.UUID
    provider: str
    project_id: str
    model: str
    reserved_tokens: int


@dataclass(frozen=True)
class Denial:
    reason: str
    retry_at: datetime | None
    permanent: bool = False


class QuotaManager:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        providers: dict[str, ProviderSettings],
        settings: Settings,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.session_factory = session_factory
        self.providers = providers
        self.settings = settings
        self.clock = clock

    # -- time helpers ---------------------------------------------------------
    def day_key(self, provider: str, now: datetime) -> date:
        return local_date(now, self.providers[provider].daily_reset_tz)

    def next_reset(self, provider: str, now: datetime) -> datetime:
        return next_local_midnight(now, self.providers[provider].daily_reset_tz)

    # -- locking --------------------------------------------------------------
    def _lock_row(self, db: Session, provider: str, project_id: str, model: str) -> QuotaState:
        now = self.clock()
        db.execute(
            insert(QuotaState)
            .values(
                id=uuid.uuid4(),
                provider=provider,
                project_id=project_id,
                model=model,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["provider", "project_id", "model"])
        )
        return db.execute(
            select(QuotaState)
            .where(
                QuotaState.provider == provider,
                QuotaState.project_id == project_id,
                QuotaState.model == model,
            )
            .with_for_update()
        ).scalar_one()

    def _sweep_stale(self, db: Session, now: datetime) -> None:
        stale = db.scalars(
            select(AIUsage).where(AIUsage.outcome == "reserved", AIUsage.started_at < now - STALE_RESERVATION)
        ).all()
        for row in stale:
            row.outcome = "abandoned"
            row.ended_at = now
            state = db.scalar(
                select(QuotaState).where(
                    QuotaState.provider == row.provider,
                    QuotaState.project_id == row.project_id,
                    QuotaState.model == row.model,
                )
            )
            if state is not None:
                state.daily_reserved_requests = max(0, state.daily_reserved_requests - 1)
                if state.day_key == row.day_key:
                    # Unknown whether the request reached the provider: count it (conservative).
                    state.daily_spent_requests += 1
                    state.daily_spent_tokens += row.reserved_tokens
        # Sessions run with autoflush off; the budget checks that follow must see the sweep.
        db.flush()

    # -- public API -----------------------------------------------------------
    def reserve(
        self,
        provider: str,
        model: str,
        *,
        kind: str,
        job_id: uuid.UUID | None,
        estimated_tokens: int,
    ) -> Reservation | Denial:
        cfg = self.providers.get(provider)
        if cfg is None or not cfg.operational:
            problems = ", ".join(cfg.problems()) if cfg else "unknown provider"
            return Denial(f"{provider} not operational ({problems})", None, permanent=True)
        now = self.clock()
        with self.session_factory() as db:
            self._lock_row(db, *GLOBAL_KEY)
            state = self._lock_row(db, provider, cfg.project_id, model)
            self._sweep_stale(db, now)
            denial = self._check(db, cfg, state, model, estimated_tokens, now)
            if denial is not None:
                db.commit()
                return denial
            attempt_no = 1
            if job_id is not None:
                attempt_no += int(
                    db.scalar(select(func.max(AIUsage.attempt_no)).where(AIUsage.job_id == job_id)) or 0
                )
            usage = AIUsage(
                provider=provider,
                project_id=cfg.project_id,
                model=model,
                kind=kind,
                job_id=job_id,
                attempt_no=attempt_no,
                day_key=self.day_key(provider, now),
                reserved_tokens=estimated_tokens,
                outcome="reserved",
                started_at=now,
            )
            db.add(usage)
            state.daily_reserved_requests += 1
            state.last_request_at = now
            db.commit()
            return Reservation(usage.id, provider, cfg.project_id, model, estimated_tokens)

    def _check(
        self, db: Session, cfg: ProviderSettings, state: QuotaState, model: str, estimated: int, now: datetime
    ) -> Denial | None:
        today = self.day_key(cfg.name, now)
        if state.day_key != today:
            state.day_key = today
            state.daily_spent_requests = 0
            state.daily_spent_tokens = 0
            state.daily_reserved_requests = int(
                db.scalar(
                    select(func.count(AIUsage.id)).where(
                        AIUsage.provider == cfg.name,
                        AIUsage.project_id == cfg.project_id,
                        AIUsage.model == model,
                        AIUsage.outcome == "reserved",
                    )
                )
                or 0
            )
            if state.block_reason == "daily_quota":
                state.blocked_until = None
                state.block_reason = None

        if state.available is False:
            return Denial(
                f"{cfg.name}/{model} marked unavailable: {state.availability_note or 'see sync-models'}",
                None,
                True,
            )
        if state.blocked_until and state.blocked_until > now:
            return Denial(f"{cfg.name}/{model} blocked ({state.block_reason})", state.blocked_until)
        if state.circuit_open_until and state.circuit_open_until > now:
            return Denial(f"{cfg.name}/{model} circuit breaker open", state.circuit_open_until)

        rpd = cfg.effective(cfg.rpd_budget)
        if not rpd:
            return Denial(f"{cfg.name.upper()}_RPD_BUDGET not configured", None, True)
        if state.daily_spent_requests + state.daily_reserved_requests >= rpd:
            return Denial(
                f"{cfg.name}/{model} daily request budget used ({rpd})", self.next_reset(cfg.name, now)
            )

        tpd = cfg.effective(cfg.tpd_budget)
        if tpd:
            outstanding = int(
                db.scalar(
                    select(func.coalesce(func.sum(AIUsage.reserved_tokens), 0)).where(
                        AIUsage.provider == cfg.name, AIUsage.model == model, AIUsage.outcome == "reserved"
                    )
                )
                or 0
            )
            if state.daily_spent_tokens + outstanding + estimated > tpd:
                return Denial(
                    f"{cfg.name}/{model} daily token budget used ({tpd})", self.next_reset(cfg.name, now)
                )

        window_rows = db.execute(
            select(AIUsage.started_at, AIUsage.total_tokens, AIUsage.reserved_tokens).where(
                AIUsage.provider == cfg.name,
                AIUsage.project_id == cfg.project_id,
                AIUsage.model == model,
                AIUsage.started_at > now - WINDOW,
                AIUsage.outcome != "cancelled",
            )
        ).all()
        oldest = min((r.started_at for r in window_rows), default=now)
        rpm = cfg.effective(cfg.rpm_budget)
        if rpm is not None and len(window_rows) >= rpm:
            return Denial(f"{cfg.name}/{model} RPM budget ({rpm}/min)", oldest + WINDOW)
        tpm = cfg.effective(cfg.tpm_budget)
        if tpm is not None:
            if estimated > tpm:
                return Denial(
                    f"request (~{estimated} tokens) exceeds {cfg.name} TPM budget ({tpm})", None, True
                )
            used = sum(
                r.total_tokens if r.total_tokens is not None else r.reserved_tokens for r in window_rows
            )
            if used + estimated > tpm:
                return Denial(f"{cfg.name}/{model} TPM budget ({tpm}/min)", oldest + WINDOW)

        last = db.scalar(
            select(func.max(AIUsage.started_at)).where(
                AIUsage.provider == cfg.name, AIUsage.project_id == cfg.project_id
            )
        )
        gap = timedelta(seconds=cfg.min_seconds_between_requests)
        if last is not None and now - last < gap:
            return Denial(f"{cfg.name} minimum gap {gap.total_seconds():.0f}s", last + gap)

        outstanding_provider = int(
            db.scalar(
                select(func.count(AIUsage.id)).where(
                    AIUsage.provider == cfg.name, AIUsage.outcome == "reserved"
                )
            )
            or 0
        )
        if outstanding_provider >= cfg.max_concurrent:
            return Denial(f"{cfg.name} concurrency limit ({cfg.max_concurrent})", now + timedelta(seconds=10))
        outstanding_global = int(
            db.scalar(select(func.count(AIUsage.id)).where(AIUsage.outcome == "reserved")) or 0
        )
        if outstanding_global >= max(1, self.settings.ai_global_max_concurrent):
            return Denial("global AI concurrency limit", now + timedelta(seconds=10))
        return None

    def reconcile(
        self,
        reservation: Reservation,
        outcome: str,
        *,
        usage: Usage | None = None,
        error: ProviderError | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        now = self.clock()
        with self.session_factory() as db:
            self._lock_row(db, *GLOBAL_KEY)
            state = self._lock_row(db, reservation.provider, reservation.project_id, reservation.model)
            row = db.get(AIUsage, reservation.usage_id, with_for_update=True)
            if row is None or row.outcome != "reserved":
                db.commit()
                return
            row.outcome = outcome
            row.ended_at = now
            if usage is not None:
                row.input_tokens = usage.input_tokens
                row.output_tokens = usage.output_tokens
                row.total_tokens = usage.total_tokens
            row.provider_error_class = error.error_class if error else None
            state.daily_reserved_requests = max(0, state.daily_reserved_requests - 1)
            if row.day_key == state.day_key and outcome != "cancelled":
                state.daily_spent_requests += 1
                if row.total_tokens is not None:
                    state.daily_spent_tokens += row.total_tokens
                elif outcome in TOKEN_SPENDING_OUTCOMES:
                    state.daily_spent_tokens += row.reserved_tokens
            self._apply_outcome(state, reservation.provider, outcome, error, now)
            self._apply_headers(state, headers or (error.headers if error else {}), now)
            db.commit()

    def _apply_outcome(
        self, state: QuotaState, provider: str, outcome: str, error: ProviderError | None, now: datetime
    ) -> None:
        if outcome in ("success", "invalid_output"):
            state.consecutive_failures = 0
            state.circuit_open_until = None
            if outcome == "success":
                state.last_success_at = now
        elif outcome == "rate_limited":
            wait = error.retry_after if error and error.retry_after else 60.0
            until = now + timedelta(seconds=wait)
            state.blocked_until = max(state.blocked_until or until, until)
            state.block_reason = "rate_limited"
        elif outcome == "quota_exhausted":
            until = None
            if error is not None and error.reset_at:
                until = error.reset_at
            elif error is not None and error.retry_after and provider != "gemini":
                until = now + timedelta(seconds=error.retry_after)
            state.blocked_until = until or self.next_reset(provider, now)
            state.block_reason = "daily_quota"
        elif outcome in ("server_error", "timeout"):
            state.consecutive_failures += 1
            if state.consecutive_failures >= CIRCUIT_THRESHOLD:
                cooldown = min(3600, 300 * 2 ** (state.consecutive_failures - CIRCUIT_THRESHOLD))
                state.circuit_open_until = now + timedelta(seconds=cooldown)
        elif outcome == "auth_error":
            state.consecutive_failures += 1
            state.blocked_until = now + timedelta(hours=6)
            state.block_reason = "auth_error"

    def _apply_headers(self, state: QuotaState, headers: dict[str, str], now: datetime) -> None:
        limits = {k: v for k, v in headers.items() if k.startswith("x-ratelimit-")}
        if not limits:
            return
        state.observed_limits = limits
        state.last_provider_limit_refresh_at = now
        for remaining_key, reset_key, reason in (
            (
                "x-ratelimit-remaining-requests",
                "x-ratelimit-reset-requests",
                "provider_reported_requests_exhausted",
            ),
            (
                "x-ratelimit-remaining-tokens",
                "x-ratelimit-reset-tokens",
                "provider_reported_tokens_exhausted",
            ),
        ):
            if limits.get(remaining_key) == "0":
                wait = parse_duration(limits.get(reset_key)) or 60.0
                until = now + timedelta(seconds=wait)
                if state.blocked_until is None or until > state.blocked_until:
                    state.blocked_until = until
                    state.block_reason = reason

    def set_availability(self, provider: str, model: str, available: bool, note: str | None = None) -> None:
        cfg = self.providers[provider]
        with self.session_factory() as db:
            state = self._lock_row(db, provider, cfg.project_id, model)
            state.available = available
            state.availability_note = note
            db.commit()

    def snapshot(self) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            return [
                {
                    "provider": s.provider,
                    "model": s.model,
                    "spent": s.daily_spent_requests,
                    "reserved": s.daily_reserved_requests,
                    "blocked_until": s.blocked_until,
                    "block_reason": s.block_reason,
                    "circuit_open_until": s.circuit_open_until,
                }
                for s in db.scalars(select(QuotaState).where(QuotaState.provider != "*")).all()
            ]

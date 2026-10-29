"""Durable job queue on the ai_jobs table with leases (FOR UPDATE SKIP LOCKED).

Expired leases are reclaimed, so a crashed worker never strands a job."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import AIJob, utcnow


class JobQueue:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        owner: str,
        lease_seconds: int = 600,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.session_factory = session_factory
        self.owner = owner
        self.lease = timedelta(seconds=lease_seconds)
        self.clock = clock

    def claim(self, exclude_kinds: Iterable[str] = ()) -> uuid.UUID | None:
        now = self.clock()
        excluded = list(exclude_kinds)
        with self.session_factory() as db:
            stmt = select(AIJob).where(
                or_(
                    and_(AIJob.status.in_(("queued", "deferred")), AIJob.next_run_at <= now),
                    and_(AIJob.status == "running", AIJob.lease_until < now),
                )
            )
            if excluded:
                stmt = stmt.where(AIJob.kind.not_in(excluded))
            job = db.scalars(
                stmt.order_by(AIJob.priority.desc(), AIJob.next_run_at, AIJob.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).first()
            if job is None:
                db.commit()
                return None
            job.status = "running"
            job.lease_owner = self.owner
            job.lease_until = now + self.lease
            db.commit()
            return job.id

    def record_attempt(self, job_id: uuid.UUID, provider: str, model: str, outcome: str) -> int:
        with self.session_factory() as db:
            job = db.get(AIJob, job_id, with_for_update=True)
            assert job is not None
            job.attempts += 1
            job.last_provider = provider
            job.last_model = model
            history = list(job.attempted_providers or [])
            history.append(
                {"provider": provider, "model": model, "outcome": outcome, "at": self.clock().isoformat()}
            )
            job.attempted_providers = history[-12:]
            db.commit()
            return job.attempts

    def update_last_attempt(self, job_id: uuid.UUID, outcome: str) -> None:
        with self.session_factory() as db:
            job = db.get(AIJob, job_id, with_for_update=True)
            if job is None or not job.attempted_providers:
                return
            history = list(job.attempted_providers)
            history[-1] = {**history[-1], "outcome": outcome}
            job.attempted_providers = history
            db.commit()

    def _finish(self, job_id: uuid.UUID, **values: object) -> None:
        with self.session_factory() as db:
            job = db.get(AIJob, job_id, with_for_update=True)
            if job is None:
                return
            for key, value in values.items():
                setattr(job, key, value)
            job.lease_owner = None
            job.lease_until = None
            db.commit()

    def complete(self, job_id: uuid.UUID, result_ref: str | None) -> None:
        self._finish(
            job_id,
            status="succeeded",
            result_ref=result_ref,
            error_code=None,
            error_detail=None,
            completed_at=self.clock(),
        )

    def defer(self, job_id: uuid.UUID, until: datetime, error_code: str, detail: str | None = None) -> None:
        self._finish(
            job_id,
            status="deferred",
            next_run_at=until,
            error_code=error_code,
            error_detail=(detail or "")[:1000],
        )

    def fail(
        self, job_id: uuid.UUID, error_code: str, detail: str | None = None, *, dead_letter: bool = True
    ) -> None:
        self._finish(
            job_id,
            status="dead_letter" if dead_letter else "failed",
            error_code=error_code,
            error_detail=(detail or "")[:1000],
            completed_at=self.clock(),
        )

    def cancel(self, job_id: uuid.UUID, reason: str) -> None:
        self._finish(
            job_id,
            status="cancelled",
            error_code="cancelled",
            error_detail=reason[:500],
            completed_at=self.clock(),
        )

    def waiting_counts(self) -> dict[str, int]:
        now = self.clock()
        with self.session_factory() as db:
            rows = db.execute(
                select(AIJob.kind, func.count())
                .where(AIJob.status.in_(("queued", "deferred")), AIJob.next_run_at <= now)
                .group_by(AIJob.kind)
            ).all()
            return {kind: int(n) for kind, n in rows}

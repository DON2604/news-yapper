from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.ai_config import provider_settings
from app.db import SessionLocal
from app.models import AIUsage, QuotaState
from pipeline.providers.base import QuotaExhausted, RateLimited, ServerError, Usage, parse_duration
from pipeline.quota_manager import Denial, QuotaManager, Reservation


def _manager(settings, clock) -> QuotaManager:
    return QuotaManager(SessionLocal, provider_settings(settings), settings, clock)


def _reserve(qm: QuotaManager, provider: str = "gemini", model: str = "gemini-test", tokens: int = 100):
    return qm.reserve(provider, model, kind="news_batch", job_id=None, estimated_tokens=tokens)


def test_safety_factor_and_daily_budget(ai_settings, clock):
    settings = ai_settings(gemini_rpd_budget=4, gemini_budget_safety_factor=0.5)
    qm = _manager(settings, clock)
    granted = []
    for _ in range(2):
        r = _reserve(qm)
        assert isinstance(r, Reservation)
        qm.reconcile(r, "success", usage=Usage(10, 10, 20))
        granted.append(r)
        clock.advance(seconds=61)
    denied = _reserve(qm)
    assert isinstance(denied, Denial) and "daily request budget" in denied.reason
    # 06:02 UTC is 22:02 PST on 14 Jan; the next America/Los_Angeles midnight is 08:00 UTC.
    assert denied.retry_at == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


def test_daily_reset_follows_pacific_midnight_not_utc(ai_settings, make_clock):
    clock = make_clock(datetime(2026, 1, 15, 0, 30, tzinfo=UTC))  # 14 Jan 16:30 PST
    settings = ai_settings(gemini_rpd_budget=1)
    qm = _manager(settings, clock)
    r = _reserve(qm)
    assert isinstance(r, Reservation)
    qm.reconcile(r, "success")
    clock.now = datetime(2026, 1, 15, 7, 30, tzinfo=UTC)  # UTC date changed, still 14 Jan in California
    assert isinstance(_reserve(qm), Denial)
    clock.now = datetime(2026, 1, 15, 8, 1, tzinfo=UTC)  # 15 Jan 00:01 PST
    assert isinstance(_reserve(qm), Reservation)


def test_rpm_window_and_min_gap(ai_settings, clock):
    settings = ai_settings(gemini_rpm_budget=2, gemini_min_seconds_between_requests=15)
    qm = _manager(settings, clock)
    first = _reserve(qm)
    assert isinstance(first, Reservation)
    qm.reconcile(first, "success")
    too_soon = _reserve(qm)
    assert isinstance(too_soon, Denial) and "minimum gap" in too_soon.reason
    assert too_soon.retry_at == clock.now + timedelta(seconds=15)
    clock.advance(seconds=16)
    second = _reserve(qm)
    assert isinstance(second, Reservation)
    qm.reconcile(second, "success")
    clock.advance(seconds=16)
    rpm = _reserve(qm)
    assert isinstance(rpm, Denial) and "RPM" in rpm.reason
    clock.advance(seconds=30)
    assert isinstance(_reserve(qm), Reservation)


def test_tpm_budget(ai_settings, clock):
    qm = _manager(ai_settings(gemini_tpm_budget=1000), clock)
    too_big = _reserve(qm, tokens=5000)
    assert isinstance(too_big, Denial) and too_big.permanent
    r = _reserve(qm, tokens=700)
    assert isinstance(r, Reservation)
    qm.reconcile(r, "success", usage=Usage(500, 300, 800))
    over = _reserve(qm, tokens=300)
    assert isinstance(over, Denial) and "TPM" in over.reason


def test_concurrency_limit_and_stale_sweep(ai_settings, clock):
    qm = _manager(ai_settings(), clock)
    held = _reserve(qm)
    assert isinstance(held, Reservation)
    blocked = _reserve(qm, provider="groq", model="groq-quality")
    assert isinstance(blocked, Denial) and "concurrency" in blocked.reason
    clock.advance(minutes=11)
    after_sweep = _reserve(qm, provider="groq", model="groq-quality")
    assert isinstance(after_sweep, Reservation)
    with SessionLocal() as db:
        assert db.get(AIUsage, held.usage_id).outcome == "abandoned"


def test_rate_limit_and_daily_quota_blocks(ai_settings, clock):
    qm = _manager(ai_settings(), clock)
    r = _reserve(qm)
    qm.reconcile(r, "rate_limited", error=RateLimited("slow down", retry_after=30))
    denial = _reserve(qm)
    assert isinstance(denial, Denial) and denial.retry_at == clock.now + timedelta(seconds=30)
    clock.advance(seconds=31)
    r2 = _reserve(qm)
    assert isinstance(r2, Reservation)
    qm.reconcile(r2, "quota_exhausted", error=QuotaExhausted("daily"))
    clock.advance(hours=1)
    blocked = _reserve(qm)
    assert isinstance(blocked, Denial) and blocked.retry_at == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


def test_circuit_breaker_after_repeated_server_errors(ai_settings, clock):
    qm = _manager(ai_settings(), clock)
    for _ in range(3):
        r = _reserve(qm)
        assert isinstance(r, Reservation)
        qm.reconcile(r, "server_error", error=ServerError("503"))
        clock.advance(seconds=1)
    denial = _reserve(qm)
    assert isinstance(denial, Denial) and "circuit" in denial.reason
    clock.advance(minutes=6)
    r = _reserve(qm)
    assert isinstance(r, Reservation)
    qm.reconcile(r, "success")
    with SessionLocal() as db:
        state = db.scalar(select(QuotaState).where(QuotaState.provider == "gemini"))
        assert state.consecutive_failures == 0 and state.circuit_open_until is None


def test_ledger_persists_across_restarts_and_unconfigured_budget(ai_settings, clock):
    settings = ai_settings(gemini_rpd_budget=1)
    r = _reserve(_manager(settings, clock))
    _manager(settings, clock).reconcile(r, "success")
    clock.advance(minutes=5)
    assert isinstance(_reserve(_manager(settings, clock)), Denial)
    unconfigured = _reserve(_manager(ai_settings(gemini_rpd_budget=None), clock))
    assert isinstance(unconfigured, Denial) and unconfigured.permanent


def test_groq_headers_block_proactively(ai_settings, clock):
    qm = _manager(ai_settings(), clock)
    r = _reserve(qm, provider="groq", model="groq-fast")
    qm.reconcile(
        r,
        "success",
        headers={"x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "2m30s"},
    )
    clock.advance(seconds=10)
    denial = _reserve(qm, provider="groq", model="groq-fast")
    assert isinstance(denial, Denial)
    assert denial.retry_at == clock.now - timedelta(seconds=10) + timedelta(seconds=150)


def test_parse_duration():
    assert parse_duration("31s") == 31
    assert parse_duration("2m59.5s") == 179.5
    assert parse_duration("1h2m") == 3720
    assert parse_duration("450ms") == 0.45
    assert parse_duration("12") == 12
    assert parse_duration("soon") is None

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import get_settings


def tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or get_settings().app_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Asia/Kolkata")


def local_date(now: datetime, tz_name: str | None = None) -> date:
    return now.astimezone(tz(tz_name)).date()


def app_today(now: datetime | None = None) -> date:
    return local_date(now or datetime.now(UTC))


def start_of_local_day(day: date, tz_name: str | None) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz(tz_name)).astimezone(UTC)


def next_local_midnight(now: datetime, tz_name: str) -> datetime:
    """Next midnight in the given zone (e.g. Gemini quota reset = America/Los_Angeles)."""
    zone = tz(tz_name)
    local = now.astimezone(zone)
    tomorrow = local.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=zone).astimezone(UTC)

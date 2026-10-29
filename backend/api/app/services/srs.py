"""SM-2-inspired spaced repetition (documented in docs/architecture.md).

  again: relearn - repetitions reset, due again in 10 minutes, ease -0.2
  hard : interval grows slowly (x0.5 of the "good" interval, min 1 day), ease -0.15 (SM-2 q=3: -0.14)
  good : SM-2 intervals 1 day -> 6 days -> previous x ease, ease unchanged (q=4)
  easy : "good" interval x1.3 (and at least +1 day), ease +0.1 (q=5)
Ease is clamped to [1.3, 3.0]; intervals are capped at 365 days.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_EASE = 1.3
MAX_EASE = 3.0
MAX_INTERVAL_DAYS = 365
RELEARN_DELAY = timedelta(minutes=10)
_EASE_DELTA = {"again": -0.2, "hard": -0.15, "good": 0.0, "easy": 0.1}


@dataclass(frozen=True)
class CardState:
    ease_factor: float
    interval_days: int
    repetitions: int
    lapses: int


@dataclass(frozen=True)
class ScheduleResult:
    state: CardState
    due_at: datetime


def schedule(state: CardState, outcome: str, now: datetime) -> ScheduleResult:
    if outcome not in _EASE_DELTA:
        raise ValueError(f"Unknown outcome: {outcome}")
    ease = min(MAX_EASE, max(MIN_EASE, state.ease_factor + _EASE_DELTA[outcome]))

    if outcome == "again":
        new = CardState(ease_factor=ease, interval_days=0, repetitions=0, lapses=state.lapses + 1)
        return ScheduleResult(state=new, due_at=now + RELEARN_DELAY)

    if state.repetitions == 0:
        good_interval = 1
    elif state.repetitions == 1:
        good_interval = 6
    else:
        good_interval = max(1, math.ceil(max(1, state.interval_days) * ease))

    if outcome == "hard":
        interval = max(1, round(good_interval * 0.5)) if state.repetitions > 0 else 1
    elif outcome == "easy":
        interval = max(good_interval + 1, round(good_interval * 1.3))
    else:
        interval = good_interval
    interval = min(interval, MAX_INTERVAL_DAYS)

    new = CardState(
        ease_factor=round(ease, 3),
        interval_days=interval,
        repetitions=state.repetitions + 1,
        lapses=state.lapses,
    )
    return ScheduleResult(state=new, due_at=now + timedelta(days=interval))

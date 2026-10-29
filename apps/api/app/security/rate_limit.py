"""In-process sliding-window rate limiter (per user, falling back to client IP).

Good enough for a single API instance; replace with a shared store before
running several replicas. Crunch also has persistent per-user daily limits.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.security.auth import decode_token


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> float | None:
        """Record a hit. Returns None if allowed, else seconds until a slot frees up."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return window_seconds - (now - hits[0])
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def _identity(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            return f"user:{decode_token(auth[7:].strip()).sub}"
        except HTTPException:
            pass
    return f"ip:{request.client.host if request.client else 'anon'}"


def rate_limit(bucket: str, limit: int, window_seconds: float = 60.0) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        retry_after = limiter.hit(f"{bucket}:{_identity(request)}", limit, window_seconds)
        if retry_after is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests - ektu dhire, bhai.",
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )

    return dependency

"""Outbound HTTP for ingestion with SSRF and politeness guards.

* Only http(s) on default ports, only hosts on an allowlist built from enabled sources.
* Every resolved address must be globally routable (no loopback/private/link-local/metadata IPs).
  The allowlist is the primary defence; the IP check narrows DNS-rebinding risk.
* Redirects are followed manually and every hop is re-validated.
* robots.txt is honoured per RFC 9309 (4xx -> allowed, 5xx/unreachable -> disallowed).
* Per-host minimum spacing, bounded retries with jittered backoff, response size cap.
"""

from __future__ import annotations

import ipaddress
import random
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
ROBOTS_AGENT = "AajkeKiSceneBot"
Resolver = Callable[[str], list[str]]


class FetchError(Exception):
    def __init__(
        self, message: str, *, status: int | None = None, kind: str = "fetch", retryable: bool = False
    ):
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.retryable = retryable


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes
    content_type: str
    headers: dict[str, str] = field(default_factory=dict)


def default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({str(info[4][0]) for info in infos})


def host_allowed(host: str, allowed: set[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == a or host.endswith("." + a) for a in allowed)


class SafeFetcher:
    def __init__(
        self,
        *,
        user_agent: str,
        allowed_hosts: set[str],
        timeout: float = 20.0,
        max_bytes: int = 3_000_000,
        min_interval: float = 2.0,
        host_intervals: dict[str, float] | None = None,
        max_retries: int = 2,
        respect_robots: bool = True,
        transport: httpx.BaseTransport | None = None,
        resolver: Resolver = default_resolver,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.max_bytes = max_bytes
        self.min_interval = min_interval
        self.host_intervals = host_intervals or {}
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self._resolver = resolver
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._last_hit: dict[str, float] = {}
        self._host_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._robots: dict[str, RobotFileParser | bool] = {}
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)),
            follow_redirects=False,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, "
                "application/json;q=0.9, */*;q=0.5",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SafeFetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- validation -------------------------------------------------------
    def validate_url(self, url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise FetchError(f"Blocked scheme: {parts.scheme or 'none'}", kind="blocked")
        host = (parts.hostname or "").lower()
        if not host:
            raise FetchError("URL has no host", kind="blocked")
        if parts.port not in (None, 80, 443):
            raise FetchError(f"Blocked port: {parts.port}", kind="blocked")
        if parts.username or parts.password:
            raise FetchError("Credentials in URL are not allowed", kind="blocked")
        if not host_allowed(host, self.allowed_hosts):
            raise FetchError(f"Host not on allowlist: {host}", kind="blocked")
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        addresses = [str(literal)] if literal else self._safe_resolve(host)
        for addr in addresses:
            ip = ipaddress.ip_address(addr)
            if not ip.is_global or ip.is_multicast:
                raise FetchError(f"Blocked non-public address for {host}", kind="blocked")
        return host

    def _safe_resolve(self, host: str) -> list[str]:
        try:
            addresses = self._resolver(host)
        except OSError as exc:
            raise FetchError(f"DNS resolution failed for {host}: {exc}", kind="dns", retryable=True) from exc
        if not addresses:
            raise FetchError(f"No addresses for {host}", kind="dns", retryable=True)
        return addresses

    # -- politeness ----------------------------------------------------------
    def _host_lock(self, host: str) -> threading.Lock:
        with self._locks_guard:
            return self._host_locks.setdefault(host, threading.Lock())

    def _pace(self, host: str) -> None:
        interval = self.host_intervals.get(host, self.min_interval)
        last = self._last_hit.get(host)
        if last is not None:
            wait = interval - (time.monotonic() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_hit[host] = time.monotonic()

    def robots_check(self, url: str) -> str | None:
        """None when fetching is allowed, otherwise the reason it is not."""
        if not self.respect_robots:
            return None
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(origin)
        if cached is None:
            cached = self._load_robots(origin)
            self._robots[origin] = cached
        if cached is True:
            return None
        if cached is False:
            return f"robots.txt for {origin} is unreachable (network error or 5xx) - treated as disallowed per RFC 9309"
        # robotparser matches only the first product token, which for our UA is "Mozilla".
        return None if cached.can_fetch(ROBOTS_AGENT, url) else f"Disallowed by robots.txt: {url}"

    def _load_robots(self, origin: str) -> RobotFileParser | bool:
        try:
            res = self._request(origin + "/robots.txt", check_robots=False, retries=0)
        except FetchError as exc:
            return exc.status is not None and 400 <= exc.status < 500
        parser = RobotFileParser()
        parser.parse(res.content.decode("utf-8", errors="replace").splitlines())
        return parser

    # -- requests ------------------------------------------------------------
    def get(self, url: str, params: dict[str, Any] | None = None) -> FetchResult:
        if params:
            url = str(httpx.URL(url, params=params))
        return self._request(url, check_robots=True, retries=self.max_retries)

    def _request(self, url: str, *, check_robots: bool, retries: int) -> FetchResult:
        current = url
        for _hop in range(4):
            host = self.validate_url(current)
            blocked = self.robots_check(current) if check_robots else None
            if blocked:
                raise FetchError(blocked, kind="robots")
            res = self._attempt_with_retries(current, host, retries)
            if res.status in (301, 302, 303, 307, 308):
                location = res.headers.get("location")
                if not location:
                    raise FetchError("Redirect without Location", status=res.status)
                current = urljoin(current, location)
                continue
            if res.status >= 400:
                raise FetchError(f"HTTP {res.status} from {host}", status=res.status, retryable=False)
            return res
        raise FetchError("Too many redirects", kind="redirect")

    def _attempt_with_retries(self, url: str, host: str, retries: int) -> FetchResult:
        attempt = 0
        while True:
            try:
                with self._host_lock(host):
                    self._pace(host)
                    res = self._once(url)
            except FetchError as exc:
                if not exc.retryable or attempt >= retries:
                    raise
                self._sleep(self._backoff(attempt, None))
                attempt += 1
                continue
            if res.status in RETRYABLE_STATUS and attempt < retries:
                self._sleep(self._backoff(attempt, res.headers.get("retry-after")))
                attempt += 1
                continue
            return res

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        cap = min(20.0, 2.0 * (3**attempt))
        return self._rng.uniform(cap / 2, cap)

    def _once(self, url: str) -> FetchResult:
        try:
            with self._client.stream("GET", url) as response:
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self.max_bytes:
                    raise FetchError(f"Response too large ({declared} bytes)", kind="size")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise FetchError(f"Response exceeded {self.max_bytes} bytes", kind="size")
                    chunks.append(chunk)
                return FetchResult(
                    url=str(response.url),
                    status=response.status_code,
                    content=b"".join(chunks),
                    content_type=response.headers.get("content-type", ""),
                    headers={k.lower(): v for k, v in response.headers.items()},
                )
        except httpx.TimeoutException as exc:
            raise FetchError(f"Timeout fetching {url}", kind="timeout", retryable=True) from exc
        except httpx.TransportError as exc:
            raise FetchError(
                f"Network error: {exc.__class__.__name__}: {exc}", kind="network", retryable=True
            ) from exc

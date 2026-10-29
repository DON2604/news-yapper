"""Provider-independent interface. Business logic only ever sees these types."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class GenerationRequest:
    model: str
    system_prompt: str
    user_prompt: str
    json_schema: dict[str, Any]
    schema_name: str
    max_output_tokens: int
    temperature: float = 0.3
    timeout_s: float = 90.0


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class GenerationResult:
    data: dict[str, Any]
    raw_text: str
    usage: Usage
    model: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInfo:
    id: str
    active: bool = True
    context_window: int | None = None
    supports_generation: bool = True


class ProviderError(Exception):
    outcome = "server_error"
    retryable = True
    permanent = False

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        reset_at: datetime | None = None,
        headers: dict[str, str] | None = None,
        error_class: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        self.reset_at = reset_at
        self.headers = headers or {}
        self.error_class = error_class or self.__class__.__name__


class RateLimited(ProviderError):
    """Minute-window limit (RPM/TPM). Respect Retry-After."""

    outcome = "rate_limited"


class QuotaExhausted(ProviderError):
    """Daily quota (RPD/TPD) used up - defer until the provider's reset."""

    outcome = "quota_exhausted"


class ServerError(ProviderError):
    outcome = "server_error"


class ProviderTimeout(ProviderError):
    outcome = "timeout"


class AuthError(ProviderError):
    outcome = "auth_error"
    retryable = False
    permanent = True


class BadRequest(ProviderError):
    outcome = "client_error"
    retryable = False
    permanent = True


class ModelUnavailable(BadRequest):
    pass


class InvalidOutput(ProviderError):
    outcome = "invalid_output"
    retryable = True


class AIProvider(Protocol):
    name: str

    def generate_json(self, request: GenerationRequest) -> GenerationResult: ...

    def list_models(self) -> list[ModelInfo]: ...


_DURATION = re.compile(
    r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?$"
)


def parse_duration(value: str | None) -> float | None:
    """'31s', '2m59.56s', '1h2m', '450ms', '12' -> seconds."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    match = _DURATION.match(value)
    if not match or not any(match.groups()):
        return None
    h, m, s, ms = (float(g) if g else 0.0 for g in match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.S)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InvalidOutput(f"Model did not return valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise InvalidOutput("Model JSON was not an object")
    return data


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local $refs and drop keys some providers reject (title/default)."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return walk(defs[name])
            return {k: walk(v) for k, v in node.items() if k not in ("$defs", "title", "default")}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)

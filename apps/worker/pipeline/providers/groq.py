"""Groq adapter via the OpenAI-compatible REST API (https://api.groq.com/openai/v1).

Groq limits are organisation-level (RPM/RPD/TPM/TPD); x-ratelimit-* headers are
returned to the quota manager. Raw httpx, no SDK auto-retries.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.ai_config import ProviderSettings
from pipeline.providers.base import (
    AuthError,
    BadRequest,
    GenerationRequest,
    GenerationResult,
    InvalidOutput,
    ModelInfo,
    ModelUnavailable,
    ProviderError,
    ProviderTimeout,
    QuotaExhausted,
    RateLimited,
    ServerError,
    Usage,
    parse_duration,
    parse_json_text,
)

DAILY_MARKERS = ("per day", "(rpd)", "(tpd)", "requests per day", "tokens per day")


def classify_error(response: httpx.Response) -> ProviderError:
    status = response.status_code
    headers = {k.lower(): v for k, v in response.headers.items()}
    try:
        error = response.json().get("error", {}) or {}
    except ValueError:
        error = {}
    message = str(error.get("message") or response.text[:200] or f"HTTP {status}")
    retry_after = parse_duration(headers.get("retry-after"))
    if status == 429:
        if any(marker in message.lower() for marker in DAILY_MARKERS):
            reset = parse_duration(headers.get("x-ratelimit-reset-requests")) or retry_after
            return QuotaExhausted(message, status=status, retry_after=reset, headers=headers)
        reset = retry_after or parse_duration(headers.get("x-ratelimit-reset-tokens"))
        return RateLimited(message, status=status, retry_after=reset, headers=headers)
    if status in (401, 403):
        return AuthError(message, status=status, headers=headers)
    if status == 404:
        return ModelUnavailable(message, status=status, headers=headers)
    if status == 498 or status >= 500:
        return ServerError(message, status=status, retry_after=retry_after, headers=headers)
    return BadRequest(message, status=status, headers=headers)


class GroqProvider:
    name = "groq"

    def __init__(self, cfg: ProviderSettings, client: httpx.Client | None = None) -> None:
        self.cfg = cfg
        self._client = client or httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0))

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.cfg.api_key}", "Content-Type": "application/json"}

    def generate_json(self, request: GenerationRequest) -> GenerationResult:
        system = request.system_prompt
        response_format: dict[str, Any]
        if self.cfg.json_mode == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": request.schema_name, "schema": request.json_schema, "strict": False},
            }
        else:
            response_format = {"type": "json_object"}
            system += "\n\nReturn ONLY a JSON object that validates against this JSON Schema:\n" + json.dumps(
                request.json_schema, separators=(",", ":")
            )
        body = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_completion_tokens": request.max_output_tokens,
            "response_format": response_format,
        }
        url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"
        try:
            response = self._client.post(url, json=body, headers=self._headers(), timeout=request.timeout_s)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("Groq request timed out") from exc
        except httpx.TransportError as exc:
            raise ServerError(f"Groq network error: {exc.__class__.__name__}") from exc
        if response.status_code != 200:
            raise classify_error(response)

        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise InvalidOutput("Groq returned no choices")
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise InvalidOutput("Groq output truncated at max tokens")
        text = str((choice.get("message") or {}).get("content") or "")
        usage_raw = payload.get("usage", {}) or {}
        return GenerationResult(
            data=parse_json_text(text),
            raw_text=text,
            usage=Usage(
                input_tokens=usage_raw.get("prompt_tokens"),
                output_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            ),
            model=str(payload.get("model") or request.model),
            headers={k.lower(): v for k, v in response.headers.items()},
        )

    def list_models(self) -> list[ModelInfo]:
        response = self._client.get(f"{self.cfg.base_url.rstrip('/')}/models", headers=self._headers())
        if response.status_code != 200:
            raise classify_error(response)
        return [
            ModelInfo(
                id=str(m.get("id")),
                active=bool(m.get("active", True)),
                context_window=m.get("context_window"),
            )
            for m in response.json().get("data", [])
        ]

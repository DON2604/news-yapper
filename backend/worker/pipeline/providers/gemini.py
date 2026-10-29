"""Google Gemini REST adapter (generateContent with structured JSON output).

Raw httpx without automatic retries, so retries are never multiplied: the
orchestrator owns every retry decision. The API key travels in a header, never in URLs.
"""

from __future__ import annotations

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
    inline_schema,
    parse_duration,
    parse_json_text,
)

# generateContent answers 400 INVALID_ARGUMENT when the response schema carries array-length
# bounds; pydantic still enforces them after parsing.
UNSUPPORTED_SCHEMA_KEYS = frozenset({"minItems", "maxItems"})
# Thinking tokens count toward maxOutputTokens, so long JSON answers truncate unless thinking is capped.
LOW_THINKING_PREFIXES = ("gemini-3",)


def gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items() if k not in UNSUPPORTED_SCHEMA_KEYS}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(inline_schema(schema))


def classify_error(response: httpx.Response) -> ProviderError:
    status = response.status_code
    headers = {k.lower(): v for k, v in response.headers.items()}
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    message = str(error.get("message") or response.text[:200] or f"HTTP {status}")
    retry_after = parse_duration(headers.get("retry-after"))
    quota_ids: list[str] = []
    for detail in error.get("details", []) or []:
        kind = str(detail.get("@type", ""))
        if kind.endswith("RetryInfo"):
            retry_after = parse_duration(detail.get("retryDelay")) or retry_after
        if kind.endswith("QuotaFailure"):
            quota_ids += [str(v.get("quotaId", "")) for v in detail.get("violations", [])]

    if status == 429:
        if any("PerDay" in q or "per_day" in q.lower() for q in quota_ids):
            return QuotaExhausted(message, status=status, retry_after=retry_after, headers=headers)
        return RateLimited(message, status=status, retry_after=retry_after, headers=headers)
    if status in (401, 403) or (status == 400 and "api key" in message.lower()):
        return AuthError(message, status=status, headers=headers)
    if status == 404:
        return ModelUnavailable(message, status=status, headers=headers)
    if status >= 500:
        return ServerError(message, status=status, retry_after=retry_after, headers=headers)
    return BadRequest(message, status=status, headers=headers)


class GeminiProvider:
    name = "gemini"

    def __init__(self, cfg: ProviderSettings, client: httpx.Client | None = None) -> None:
        self.cfg = cfg
        self._client = client or httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0))

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.cfg.api_key, "Content-Type": "application/json"}

    def generate_json(self, request: GenerationRequest) -> GenerationResult:
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": gemini_schema(request.json_schema),
                "maxOutputTokens": request.max_output_tokens,
                "temperature": request.temperature,
            },
        }
        if request.model.startswith(LOW_THINKING_PREFIXES):
            body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "low"}
        url = f"{self.cfg.base_url.rstrip('/')}/models/{request.model}:generateContent"
        try:
            response = self._client.post(url, json=body, headers=self._headers(), timeout=request.timeout_s)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("Gemini request timed out") from exc
        except httpx.TransportError as exc:
            raise ServerError(f"Gemini network error: {exc.__class__.__name__}") from exc
        if response.status_code != 200:
            raise classify_error(response)

        payload = response.json()
        usage_meta = payload.get("usageMetadata", {}) or {}
        usage = Usage(
            input_tokens=usage_meta.get("promptTokenCount"),
            output_tokens=usage_meta.get("candidatesTokenCount"),
            total_tokens=usage_meta.get("totalTokenCount"),
        )
        candidates = payload.get("candidates") or []
        if not candidates:
            reason = (payload.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise InvalidOutput(f"Gemini returned no candidates ({reason})")
        candidate = candidates[0]
        if candidate.get("finishReason") == "MAX_TOKENS":
            raise InvalidOutput("Gemini output truncated at max tokens")
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(str(p.get("text", "")) for p in parts)
        return GenerationResult(
            data=parse_json_text(text),
            raw_text=text,
            usage=usage,
            model=request.model,
            headers={k.lower(): v for k, v in response.headers.items()},
        )

    def list_models(self) -> list[ModelInfo]:
        url = f"{self.cfg.base_url.rstrip('/')}/models"
        response = self._client.get(url, params={"pageSize": 200}, headers=self._headers())
        if response.status_code != 200:
            raise classify_error(response)
        models = []
        for m in response.json().get("models", []):
            name = str(m.get("name", "")).removeprefix("models/")
            methods = m.get("supportedGenerationMethods") or []
            models.append(
                ModelInfo(
                    id=name,
                    context_window=m.get("inputTokenLimit"),
                    supports_generation="generateContent" in methods,
                )
            )
        return models

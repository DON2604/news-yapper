"""Provider configuration + task routing shared by the API (status/disclosure) and the worker.

No model IDs are hardcoded here: they come from env (GEMINI_MODEL, GROQ_MODEL_*) or
AI_TASK_ROUTING_JSON, and are verified against each provider's model listing by
`python -m worker sync-models`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings

TASKS = ("news_batch", "crunch", "quiz_prep", "classification")


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    enabled: bool
    api_key: str
    project_id: str
    base_url: str
    models: dict[str, str]
    rpm_budget: int | None
    tpm_budget: int | None
    rpd_budget: int | None
    tpd_budget: int | None
    safety_factor: float
    min_seconds_between_requests: float
    max_concurrent: int
    max_input_tokens: int
    max_output_tokens: int
    daily_reset_tz: str
    json_mode: str = "json_schema"

    def problems(self) -> list[str]:
        issues: list[str] = []
        if not self.enabled:
            issues.append(f"ENABLE_{self.name.upper()}=false")
        if not self.api_key:
            issues.append(f"{self.name.upper()}_API_KEY missing")
        if not any(self.models.values()):
            issues.append("no model configured")
        if not self.rpd_budget:
            issues.append(f"{self.name.upper()}_RPD_BUDGET not configured")
        if not self.rpm_budget:
            issues.append(f"{self.name.upper()}_RPM_BUDGET not configured")
        return issues

    @property
    def operational(self) -> bool:
        return not self.problems()

    def effective(self, budget: int | None) -> int | None:
        """Apply the safety factor; None means "no limit configured for this dimension"."""
        if budget is None:
            return None
        return max(1, math.floor(budget * self.safety_factor)) if budget > 0 else 0

    def public_view(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "operational": self.operational,
            "problems": self.problems(),
            "models": {k: v for k, v in self.models.items() if v},
            "budgets": {
                "rpm": self.rpm_budget,
                "tpm": self.tpm_budget,
                "rpd": self.rpd_budget,
                "tpd": self.tpd_budget,
                "safety_factor": self.safety_factor,
                "min_seconds_between_requests": self.min_seconds_between_requests,
                "max_concurrent": self.max_concurrent,
            },
            "daily_reset_tz": self.daily_reset_tz,
        }


def provider_settings(settings: Settings) -> dict[str, ProviderSettings]:
    gemini = ProviderSettings(
        name="gemini",
        enabled=settings.enable_gemini,
        api_key=settings.gemini_api_key,
        project_id=settings.gemini_project_id or "default",
        base_url=settings.gemini_base_url,
        models={"default": settings.gemini_model},
        rpm_budget=settings.gemini_rpm_budget,
        tpm_budget=settings.gemini_tpm_budget,
        rpd_budget=settings.gemini_rpd_budget,
        tpd_budget=None,
        safety_factor=settings.gemini_budget_safety_factor,
        min_seconds_between_requests=settings.gemini_min_seconds_between_requests,
        max_concurrent=max(1, settings.gemini_max_concurrent),
        max_input_tokens=settings.gemini_max_input_tokens_per_job,
        max_output_tokens=settings.gemini_max_output_tokens_per_job,
        daily_reset_tz=settings.gemini_daily_reset_tz,
    )
    groq = ProviderSettings(
        name="groq",
        enabled=settings.enable_groq,
        api_key=settings.groq_api_key,
        project_id=settings.groq_project_id or "default",
        base_url=settings.groq_base_url,
        models={
            "fast": settings.groq_model_fast,
            "quality": settings.groq_model_quality,
            "fallback": settings.groq_model_fallback,
        },
        rpm_budget=settings.groq_rpm_budget,
        tpm_budget=settings.groq_tpm_budget,
        rpd_budget=settings.groq_rpd_budget,
        tpd_budget=settings.groq_tpd_budget,
        safety_factor=settings.groq_budget_safety_factor,
        min_seconds_between_requests=settings.groq_min_seconds_between_requests,
        max_concurrent=max(1, settings.groq_max_concurrent),
        max_input_tokens=settings.groq_max_input_tokens_per_job,
        max_output_tokens=settings.groq_max_output_tokens_per_job,
        daily_reset_tz=settings.groq_daily_reset_tz,
        json_mode=settings.groq_json_mode,
    )
    return {"gemini": gemini, "groq": groq}


@dataclass(frozen=True)
class Candidate:
    provider: str
    model_role: str  # key into ProviderSettings.models, or "id:<literal model id>"
    paid: bool = False

    def resolve_model(self, providers: dict[str, ProviderSettings]) -> str:
        if self.model_role.startswith("id:"):
            return self.model_role[3:]
        cfg = providers.get(self.provider)
        return (cfg.models.get(self.model_role) or "") if cfg else ""


@dataclass(frozen=True)
class TaskRoute:
    task: str
    candidates: list[Candidate]
    max_input_tokens: int
    max_output_tokens: int
    requires_json: bool = True
    min_quality: str = "standard"
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# Intent (not a claim about free-tier availability): Gemini for nuanced Banglish
# rewriting; Groq quality model as provider fallback; Groq fast model for cheap
# classification and urgent Crunch fallback.
DEFAULT_ROUTING: dict[str, dict[str, Any]] = {
    "news_batch": {
        "candidates": [["gemini", "default"], ["groq", "quality"], ["groq", "fallback"]],
        "max_input_tokens": 6000,
        "max_output_tokens": 2048,
        "min_quality": "high",
    },
    "crunch": {
        "candidates": [["gemini", "default"], ["groq", "fast"], ["groq", "fallback"]],
        "max_input_tokens": 5000,
        "max_output_tokens": 2048,
    },
    "quiz_prep": {
        "candidates": [["gemini", "default"], ["groq", "quality"]],
        "max_input_tokens": 4000,
        "max_output_tokens": 1500,
        "min_quality": "high",
    },
    "classification": {
        "candidates": [["groq", "fast"], ["gemini", "default"]],
        "max_input_tokens": 3000,
        "max_output_tokens": 600,
        "min_quality": "basic",
    },
}


def load_routing(settings: Settings) -> dict[str, TaskRoute]:
    table: dict[str, dict[str, Any]] = {k: dict(v) for k, v in DEFAULT_ROUTING.items()}
    if settings.ai_task_routing_json.strip():
        override = json.loads(settings.ai_task_routing_json)
        if not isinstance(override, dict):
            raise ValueError("AI_TASK_ROUTING_JSON must be a JSON object keyed by task")
        for task, cfg in override.items():
            if task not in TASKS:
                raise ValueError(f"Unknown task in AI_TASK_ROUTING_JSON: {task}")
            table[task] = {**table.get(task, {}), **cfg}

    order = settings.provider_order
    routes: dict[str, TaskRoute] = {}
    for task, cfg in table.items():
        candidates = [
            Candidate(provider=str(spec[0]).lower(), model_role=str(spec[1]), paid="paid" in spec[2:])
            for spec in cfg["candidates"]
        ]
        if not settings.ai_allow_paid_fallback:
            candidates = [c for c in candidates if not c.paid]
        # AI_PROVIDER_ORDER re-sorts providers (stable within a provider) without
        # dropping any candidate; providers absent from the order go last.
        candidates.sort(key=lambda c: order.index(c.provider) if c.provider in order else len(order))
        routes[task] = TaskRoute(
            task=task,
            candidates=candidates,
            max_input_tokens=int(cfg.get("max_input_tokens", 4000)),
            max_output_tokens=int(cfg.get("max_output_tokens", 1500)),
            requires_json=bool(cfg.get("requires_json", True)),
            min_quality=str(cfg.get("min_quality", "standard")),
        )
    return routes


def crunch_disclosure(settings: Settings, consent: str) -> dict[str, Any]:
    """Which external provider(s) would receive a user's private notes during an AI Crunch."""
    providers = provider_settings(settings)
    route = load_routing(settings)["crunch"]
    ordered = [
        c.provider
        for c in route.candidates
        if providers.get(c.provider) and providers[c.provider].operational
    ]
    unique: list[str] = list(dict.fromkeys(ordered))
    primary = unique[0] if unique else None
    allow_fallback = consent == "allow_fallback" and settings.ai_allow_private_notes_provider_fallback
    recipients = unique if allow_fallback else unique[:1]
    if consent == "none":
        recipients = []
    return {
        "ai_available": bool(unique),
        "primary_provider": primary,
        "fallback_providers": unique[1:],
        "recipients_with_current_consent": recipients,
        "consent": consent,
        "private_fallback_allowed_by_server": settings.ai_allow_private_notes_provider_fallback,
    }

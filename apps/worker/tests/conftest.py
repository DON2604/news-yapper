from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from adapters.http import SafeFetcher
from app.config import Settings
from pipeline.providers.base import GenerationRequest, GenerationResult, ModelInfo, Usage

FIXTURES = Path(__file__).parent / "fixtures"
PUBLIC_IP = "93.184.216.34"


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class FakeProvider:
    """Scripted provider: each call pops the next item (dict -> success, Exception -> raised,
    callable(request) -> dict)."""

    def __init__(self, name: str, script: list[Any] | None = None) -> None:
        self.name = name
        self.script = list(script or [])
        self.calls: list[GenerationRequest] = []

    def generate_json(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if not self.script:
            raise AssertionError(f"{self.name} called more times than scripted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        data = item(request) if callable(item) else item
        return GenerationResult(
            data=data, raw_text=json.dumps(data), usage=Usage(800, 400, 1200), model=request.model
        )

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="gemini-test"), ModelInfo(id="groq-quality"), ModelInfo(id="groq-fast")]


@pytest.fixture
def clock() -> Clock:
    return Clock(datetime(2026, 1, 15, 6, 0, tzinfo=UTC))


@pytest.fixture
def make_clock() -> Callable[[datetime], Clock]:
    return Clock


@pytest.fixture
def fake_provider() -> type[FakeProvider]:
    return FakeProvider


@pytest.fixture
def ai_settings() -> Callable[..., Settings]:
    def build(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "database_url": os.environ["DATABASE_URL"],
            "api_jwt_secret": os.environ["API_JWT_SECRET"],
            "enable_gemini": True,
            "gemini_api_key": "test-key",
            "gemini_model": "gemini-test",
            "gemini_rpm_budget": 60,
            "gemini_rpd_budget": 100,
            "gemini_tpm_budget": None,
            "gemini_min_seconds_between_requests": 0,
            "gemini_budget_safety_factor": 1.0,
            "enable_groq": True,
            "groq_api_key": "test-key",
            "groq_model_fast": "groq-fast",
            "groq_model_quality": "groq-quality",
            "groq_model_fallback": "",
            "groq_rpm_budget": 60,
            "groq_rpd_budget": 100,
            "groq_tpm_budget": None,
            "groq_tpd_budget": None,
            "groq_min_seconds_between_requests": 0,
            "groq_budget_safety_factor": 1.0,
            "ai_global_max_concurrent": 1,
            "ai_task_routing_json": "",
            "ai_provider_order": "gemini,groq",
        }
        values.update(overrides)
        return Settings(**values)

    return build


@pytest.fixture
def fixture_bytes() -> Callable[[str], bytes]:
    return lambda name: (FIXTURES / name).read_bytes()


Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def make_fetcher() -> Callable[..., SafeFetcher]:
    def build(handler: Handler, hosts: set[str], **kw: Any) -> SafeFetcher:
        return SafeFetcher(
            user_agent="Mozilla/5.0 (compatible; AajkeKiSceneBot/0.1; test)",
            allowed_hosts=hosts,
            transport=httpx.MockTransport(handler),
            resolver=kw.pop("resolver", lambda host: [PUBLIC_IP]),
            sleep=kw.pop("sleep", lambda seconds: None),
            min_interval=kw.pop("min_interval", 0),
            **kw,
        )

    return build


def news_output(event_id: str, item_id: str, **changes: Any) -> dict[str, Any]:
    article = {
        "event_id": event_id,
        "headline_banglish": "Cabinet notun Fixture Mission approve korlo, 1500 crore budget!",
        "neutral_summary": "The Union Cabinet approved the National Fixture Mission with an outlay of 1500 crore for 2026-27.",
        "banglish_summary": "Bhai, Cabinet notun mission-e 1500 crore dilo - exam-e kaje lagbe.",
        "category": "polity",
        "published_event_date": None,
        "key_facts": [
            {
                "claim": "The Union Cabinet approved the National Fixture Mission with an outlay of 1500 crore.",
                "source_item_ids": [item_id],
            },
            {
                "claim": "The National Fixture Mission was approved by the Union Cabinet.",
                "source_item_ids": [item_id],
            },
        ],
        "why_it_matters": "Government schemes and their outlays are frequently asked in exams.",
        "exam_tags": ["SSC", "UPSC"],
        "importance_score": 70,
        "quiz": [
            {
                "question": "What outlay was approved for the National Fixture Mission?",
                "options": ["1500 crore", "500 crore", "2500 crore", "1000 crore"],
                "correct_index": 0,
                "explanation": "The Cabinet approved an outlay of 1500 crore.",
                "evidence_source_item_ids": [item_id],
            }
        ],
        "uncertainties": [],
        "sensitive_story": False,
    }
    article.update(changes)
    return {"articles": [article]}


@pytest.fixture
def news_payload() -> Callable[..., dict[str, Any]]:
    return news_output


@pytest.fixture
def new_id() -> Callable[[], str]:
    return lambda: str(uuid.uuid4())

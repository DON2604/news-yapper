from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models import AIJob
from pipeline.providers.base import GenerationResult


class ResourceGone(Exception):
    """The job's underlying resource no longer exists or can't be processed - never retry."""


@dataclass
class Prepared:
    system: str = ""
    user: str = ""
    schema: dict[str, Any] = field(default_factory=dict)
    schema_name: str = ""
    estimated_tokens: int = 0
    max_output_tokens: int = 1024
    offline: bool = False
    context: dict[str, Any] = field(default_factory=dict)


class JobHandler(Protocol):
    kind: str

    def prepare(self, db: Session, job: AIJob) -> Prepared: ...

    def accept(
        self, db: Session, job: AIJob, prepared: Prepared, result: GenerationResult, provider: str, model: str
    ) -> str: ...

    def run_offline(self, db: Session, job: AIJob, prepared: Prepared) -> str: ...

    def on_deferred(self, db: Session, job: AIJob, message: str) -> None: ...

    def on_failed(self, db: Session, job: AIJob, code: str, message: str) -> None: ...

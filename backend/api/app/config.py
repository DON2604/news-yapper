from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = REPO_ROOT / ".env"

_OPTIONAL_NUMBERS = (
    "gemini_rpm_budget",
    "gemini_rpd_budget",
    "gemini_tpm_budget",
    "groq_rpm_budget",
    "groq_rpd_budget",
    "groq_tpm_budget",
    "groq_tpd_budget",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = ""
    direct_url: str = ""
    test_database_url: str = ""

    # Auth
    api_jwt_secret: str = ""
    admin_emails: str = ""
    demo_grant_admin: bool = True

    # Application
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    app_timezone: str = "Asia/Kolkata"
    demo_mode: bool = True
    enable_live_ingestion: bool = False
    ingestion_contact: str = ""
    nightly_prep_enabled: bool = True
    nightly_prep_hour: int = Field(default=2, ge=0, le=23)

    # Gemini
    enable_gemini: bool = False
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_project_id: str = "default"
    gemini_max_concurrent: int = 1
    gemini_min_seconds_between_requests: float = 15.0
    gemini_rpm_budget: int | None = 2
    gemini_rpd_budget: int | None = None
    gemini_tpm_budget: int | None = None
    gemini_budget_safety_factor: float = 0.65
    gemini_max_input_tokens_per_job: int = 6000
    gemini_max_output_tokens_per_job: int = 2048
    gemini_daily_reset_tz: str = "America/Los_Angeles"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Groq
    enable_groq: bool = False
    groq_api_key: str = ""
    groq_project_id: str = "default"
    groq_model_fast: str = ""
    groq_model_quality: str = ""
    groq_model_fallback: str = ""
    groq_rpm_budget: int | None = None
    groq_rpd_budget: int | None = None
    groq_tpm_budget: int | None = None
    groq_tpd_budget: int | None = None
    groq_max_concurrent: int = 1
    groq_min_seconds_between_requests: float = 5.0
    groq_budget_safety_factor: float = 0.65
    groq_max_input_tokens_per_job: int = 6000
    groq_max_output_tokens_per_job: int = 2048
    groq_json_mode: str = "json_object"
    groq_daily_reset_tz: str = "UTC"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # AI orchestration
    ai_provider_order: str = "gemini,groq"
    ai_global_max_concurrent: int = 1
    ai_allow_paid_fallback: bool = False
    ai_allow_private_notes_provider_fallback: bool = False
    ai_task_routing_json: str = ""
    ai_max_provider_attempts_per_cycle: int = 2
    ai_max_job_attempts: int = 4
    ai_auto_publish_validated: bool = True
    ai_daily_news_job_limit: int = 8
    ai_crunch_daily_share: float = 0.3

    # Crunch limits
    crunch_max_items: int = 40
    crunch_max_input_chars: int = 12000
    crunch_daily_limit_per_user: int = 10
    crunch_cooldown_seconds: int = 20

    @field_validator(*_OPTIONAL_NUMBERS, mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def provider_order(self) -> list[str]:
        return [p.strip().lower() for p in self.ai_provider_order.split(",") if p.strip()]

    @property
    def ingestion_user_agent(self) -> str:
        contact = f"; +{self.ingestion_contact}" if self.ingestion_contact else ""
        return f"Mozilla/5.0 (compatible; AajkeKiSceneBot/0.1{contact})"


@lru_cache
def get_settings() -> Settings:
    return Settings()

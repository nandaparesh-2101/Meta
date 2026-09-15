"""Central application configuration.

Single source of truth for environment-driven settings. Nothing in this
module requires Meta API credentials or an LLM API key — the system must be
fully runnable in mock/development mode with an empty `.env`.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class DataMode(str, Enum):
    MOCK = "mock"
    LIVE = "live"  # NOT IMPLEMENTED — reserved for future Meta API integration


class ExecutionMode(str, Enum):
    """Controls whether the execution layer is allowed to do anything at all.

    Safety default is DISABLED. Nothing in this codebase may modify a real
    Meta Ads account regardless of this setting in the current build — the
    Meta integration is mock-only — but the executor still honors this flag
    so the safety gate exists before the real adapter ever lands.
    """

    DISABLED = "disabled"
    RECOMMENDATION_ONLY = "recommendation_only"
    APPROVAL_REQUIRED = "approval_required"
    CONTROLLED_AUTOMATION = "controlled_automation"


class LLMProviderKind(str, Enum):
    MOCK = "mock"
    ANTHROPIC = "anthropic"  # NOT IMPLEMENTED — reserved for future use


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    data_mode: DataMode = DataMode.MOCK
    execution_mode: ExecutionMode = ExecutionMode.DISABLED

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'runtime' / 'meta_ads_ai.db').as_posix()}"

    llm_provider: LLMProviderKind = LLMProviderKind.MOCK
    anthropic_api_key: str | None = None

    meta_access_token: str | None = None
    meta_ad_account_id: str | None = None
    meta_app_id: str | None = None
    meta_app_secret: str | None = None

    @property
    def sqlite_path(self) -> str:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            return self.database_url[len(prefix) :]
        return self.database_url

    @property
    def has_meta_credentials(self) -> bool:
        return bool(self.meta_access_token and self.meta_ad_account_id)

    @property
    def has_llm_credentials(self) -> bool:
        return self.llm_provider != LLMProviderKind.MOCK and bool(self.anthropic_api_key)


settings = Settings()

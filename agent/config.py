"""Environment-backed application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    auto_approve_tools: bool = False

    ms_client_id: str | None = None
    ms_tenant_id: str = "common"
    ms_scopes: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["User.Read", "Mail.ReadWrite", "Mail.Send"]
    )
    ms_token_keyring_service: str = "mona-ai-assistant"

    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    graph_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    graph_max_retries: int = Field(default=3, ge=0, le=8)

    llm_provider: Literal["disabled", "openai"] = "disabled"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-sol"
    openai_base_url: str | None = None
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "low"
    llm_max_tool_steps: int = Field(default=4, ge=1, le=10)

    @field_validator("ms_scopes", mode="before")
    @classmethod
    def parse_scopes(cls, value: object) -> object:
        if isinstance(value, str):
            return [scope.strip() for scope in value.split(",") if scope.strip()]
        return value

    @field_validator("ms_client_id", "openai_api_key", "openai_base_url", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def ms_authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.ms_tenant_id}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

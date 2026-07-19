"""Настройки приложения, читаемые из переменных окружения."""

import re
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime-настройки первого прототипа приложения."""

    app_name: str = "Project M4 AI Telegram News Bot"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = True
    api_prefix: str = "/api"

    database_url: str = "postgresql+asyncpg://m4:m4@localhost:5432/m4"
    redis_url: str = "redis://localhost:6379/0"

    pipeline_interval_seconds: int = Field(default=30 * 60, ge=1)
    pipeline_parse_limit: int = Field(default=10, ge=1)
    pipeline_generation_limit: int = Field(default=10, ge=1)
    pipeline_publishing_limit: int = Field(default=10, ge=1)

    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-5.6-terra"
    openai_timeout_seconds: float = 60.0

    http_timeout_seconds: float = 15.0
    http_max_response_bytes: int = 2_000_000
    http_user_agent: str = "Project-M4-RSS/0.1"

    news_allowed_languages: str = "ru,en"

    telegram_api_id: int | None = None
    telegram_api_hash: str | None = Field(default=None, repr=False)
    telegram_session_name: str = "m4_aibot"
    telegram_target_channel: str | None = None
    telegram_dry_run: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    @field_validator("news_allowed_languages")
    @classmethod
    def normalize_news_allowed_languages(cls, value: str) -> str:
        """Проверить и канонизировать comma-separated ISO language codes."""

        languages = [item.strip().lower().replace("_", "-") for item in value.split(",")]
        languages = list(dict.fromkeys(item for item in languages if item))
        if not languages:
            raise ValueError("NEWS_ALLOWED_LANGUAGES must contain at least one language")
        if any(
            re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2})?", language) is None
            for language in languages
        ):
            raise ValueError("NEWS_ALLOWED_LANGUAGES contains an invalid language code")
        return ",".join(languages)

    @property
    def allowed_news_languages(self) -> frozenset[str]:
        """Вернуть разрешённые языки как неизменяемое множество."""

        return frozenset(self.news_allowed_languages.split(","))


@lru_cache
def get_settings() -> Settings:
    """Вернуть закэшированный объект настроек приложения."""

    return Settings()

"""Настройки приложения, читаемые из переменных окружения."""

from functools import lru_cache

from pydantic import Field
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

    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-4o-mini"
    ai_fake_mode: bool = True

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


@lru_cache
def get_settings() -> Settings:
    """Вернуть закэшированный объект настроек приложения."""

    return Settings()

"""Настройки приложения, читаемые из переменных окружения."""

import re
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime-настройки первого прототипа приложения."""

    app_name: str = "Project M4 AI Telegram News Bot"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = True
    api_prefix: str = "/api"
    cabinet_enabled: bool = False
    cabinet_mount_path: str = "/cabinet"
    docs_enabled: bool = True
    cabinet_username: str | None = None
    cabinet_password_hash: str | None = Field(default=None, repr=False)
    cabinet_session_secret: str | None = Field(default=None, repr=False)
    cabinet_session_ttl_seconds: int = Field(default=8 * 60 * 60, ge=300)
    cabinet_login_max_attempts: int = Field(default=5, ge=1)
    cabinet_login_window_seconds: int = Field(default=15 * 60, ge=60)
    cabinet_timezone: str = "Europe/Berlin"

    database_url: str = "postgresql+asyncpg://m4:m4@localhost:5432/m4"
    redis_url: str = "redis://localhost:6379/0"

    pipeline_interval_seconds: int = Field(default=30 * 60, ge=1)
    pipeline_parse_limit: int = Field(default=10, ge=1)
    pipeline_generation_limit: int = Field(default=10, ge=1)
    pipeline_publishing_limit: int = Field(default=10, ge=1)
    pipeline_reconciliation_interval_seconds: int = Field(default=10 * 60, ge=60)
    pipeline_run_stale_after_seconds: int = Field(default=2 * 60 * 60, ge=60)

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
    telegram_publisher: Literal["telethon", "bot_api"] = "telethon"
    telegram_bot_token: str | None = Field(default=None, repr=False)
    telegram_target_channel: str | None = None
    telegram_dry_run: bool = True
    telegram_timeout_seconds: float = Field(default=15.0, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def apply_environment_defaults(cls, values: object) -> object:
        """Отключить Swagger по умолчанию в production без отмены явной настройки."""

        if not isinstance(values, dict) or "docs_enabled" in values:
            return values
        normalized_values = dict(values)
        environment = str(normalized_values.get("environment", "local")).strip().lower()
        normalized_values["docs_enabled"] = environment not in {"production", "prod"}
        return normalized_values

    @field_validator("cabinet_mount_path")
    @classmethod
    def normalize_cabinet_mount_path(cls, value: str) -> str:
        """Проверить абсолютный непересекающийся mount path кабинета."""

        normalized = f"/{value.strip().strip('/')}"
        if normalized in {"/", "/api", "/docs", "/openapi.json", "/redoc"}:
            raise ValueError("CABINET_MOUNT_PATH conflicts with an application route")
        return normalized

    @model_validator(mode="after")
    def validate_enabled_cabinet_security(self) -> "Settings":
        """Запретить включение кабинета без полного single-admin security config."""

        if not self.cabinet_enabled:
            return self
        if not self.cabinet_username:
            raise ValueError("CABINET_USERNAME is required when cabinet is enabled")
        if not self.cabinet_password_hash or not self.cabinet_password_hash.startswith("$argon2"):
            raise ValueError("CABINET_PASSWORD_HASH must contain an Argon2 hash")
        if not self.cabinet_session_secret or len(self.cabinet_session_secret) < 32:
            raise ValueError("CABINET_SESSION_SECRET must contain at least 32 characters")
        return self

    @field_validator("news_allowed_languages")
    @classmethod
    def normalize_news_allowed_languages(cls, value: str) -> str:
        """Проверить и канонизировать comma-separated ISO language codes."""

        languages = [item.strip().lower().replace("_", "-") for item in value.split(",")]
        languages = list(dict.fromkeys(item for item in languages if item))
        if not languages:
            raise ValueError("NEWS_ALLOWED_LANGUAGES must contain at least one language")
        if any(
            re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2})?", language) is None for language in languages
        ):
            raise ValueError("NEWS_ALLOWED_LANGUAGES contains an invalid language code")
        return ",".join(languages)

    @field_validator("cabinet_timezone")
    @classmethod
    def validate_cabinet_timezone(cls, value: str) -> str:
        """Проверить IANA timezone для календарных dashboard-метрик."""

        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("CABINET_TIMEZONE must be a valid IANA timezone") from exc
        return normalized

    @property
    def allowed_news_languages(self) -> frozenset[str]:
        """Вернуть разрешённые языки как неизменяемое множество."""

        return frozenset(self.news_allowed_languages.split(","))

    @property
    def cabinet_cookie_secure(self) -> bool:
        """Включать Secure cookie во всех production-подобных окружениях."""

        return self.environment.strip().lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    """Вернуть закэшированный объект настроек приложения."""

    return Settings()

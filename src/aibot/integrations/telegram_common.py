"""Общие безопасные типы Telegram integration adapters."""

import hashlib
from dataclasses import dataclass
from datetime import datetime


class TelegramClientError(RuntimeError):
    """Безопасная базовая ошибка Telegram adapter."""


class TelegramConfigurationError(TelegramClientError):
    """Telegram real-mode не имеет обязательных настроек."""


class TelegramAuthorizationError(TelegramClientError):
    """Telegram credentials или session не авторизованы."""


class TelegramTemporaryError(TelegramClientError):
    """Временный Telegram-сбой до подтверждённой отправки."""


class TelegramPublicationUncertainError(TelegramClientError):
    """Telegram мог принять сообщение, но результат нельзя подтвердить."""


class TelegramRateLimitError(TelegramTemporaryError):
    """Telegram отклонил запрос с безопасным retry-after."""

    def __init__(self, *, retry_after_seconds: int | None = None) -> None:
        super().__init__("Telegram rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class TelegramChannelMessage:
    """Нормализованное сообщение Telegram-канала до parser слоя."""

    message_id: int
    text: str
    published_at: datetime
    url: str | None = None


def build_dry_run_message_id(text: str) -> str:
    """Построить детерминированный ID без внешнего Telegram-вызова."""

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"dry-run-{digest}"

"""Безопасная orchestration реальных OpenAI и Telegram проверок."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from aibot.config import Settings
from aibot.integrations.ai_client import (
    AIClient,
    AIClientAuthenticationError,
    AIClientError,
    AIClientRateLimitError,
)
from aibot.integrations.telegram_common import (
    TelegramAuthorizationError,
    TelegramChannelMessage,
    TelegramClientError,
    TelegramConfigurationError,
)
from aibot.integrations.telegram_publisher_factory import build_telegram_publisher
from aibot.integrations.telethon_reader import TelethonChannelReader
from aibot.ports.ai import AIClientPort
from aibot.ports.telegram import TelegramPublisherPort, TelegramSourceReaderPort

OPENAI_VERIFICATION_INPUT = (
    "Python получил небольшое обновление производительности. "
    "Сформируй короткий тестовый Telegram-пост."
)
TELEGRAM_VERIFICATION_MESSAGE = (
    "Project M4: проверка реальной Telegram-публикации. Сообщение можно удалить."
)


class IntegrationCheckStatus(StrEnum):
    """Итог отдельной проверки внешнего сервиса."""

    PASSED = "passed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class IntegrationCheckResult:
    """Безопасные метаданные проверки без provider payload и секретов."""

    service: str
    status: IntegrationCheckStatus
    error_type: str | None = None
    response_length: int | None = None
    messages_read: int | None = None
    test_message_id: str | None = None


class TelegramClientPort(Protocol):
    """Минимальный Telegram port для operational verification."""

    async def verify_connection(self) -> None:
        """Проверить credentials и session."""

    async def read_channel_messages(
        self,
        channel: str,
        *,
        limit: int = 10,
    ) -> list[TelegramChannelMessage]:
        """Прочитать сообщения источника."""

    async def publish_message(self, text: str) -> str:
        """Опубликовать сообщение."""


class IntegrationVerificationService:
    """Проверить production adapters и вернуть только безопасный результат."""

    def __init__(
        self,
        settings: Settings,
        *,
        ai_client: AIClientPort | None = None,
        telegram_client: TelegramClientPort | None = None,
        telegram_reader: TelegramSourceReaderPort | None = None,
        telegram_publisher: TelegramPublisherPort | None = None,
    ) -> None:
        if telegram_client is not None and (
            telegram_reader is not None or telegram_publisher is not None
        ):
            raise ValueError("Provide telegram_client or separate reader/publisher, not both")
        self.settings = settings
        self.ai_client = ai_client or AIClient(settings)
        self.telegram_reader = telegram_reader or telegram_client or TelethonChannelReader(settings)
        self.telegram_publisher = (
            telegram_publisher or telegram_client or build_telegram_publisher(settings)
        )

    async def verify_openai(self) -> IntegrationCheckResult:
        """Выполнить один минимальный реальный запрос через production AI adapter."""

        try:
            response = await self.ai_client.generate_telegram_post(OPENAI_VERIFICATION_INPUT)
        except (AIClientAuthenticationError, AIClientRateLimitError) as exc:
            return self._blocked("openai", exc)
        except AIClientError as exc:
            return self._failed("openai", exc)
        except Exception as exc:
            return self._failed("openai", exc)

        if len(response) > 900:
            return IntegrationCheckResult(
                service="openai",
                status=IntegrationCheckStatus.FAILED,
                error_type="AIResponseTooLong",
                response_length=len(response),
            )
        return IntegrationCheckResult(
            service="openai",
            status=IntegrationCheckStatus.PASSED,
            response_length=len(response),
        )

    async def verify_telegram(
        self,
        *,
        source: str | None = None,
        publish_test: bool = False,
    ) -> IntegrationCheckResult:
        """Проверить session, опциональное чтение и явно разрешённую test-публикацию."""

        if self.settings.telegram_dry_run:
            return IntegrationCheckResult(
                service="telegram",
                status=IntegrationCheckStatus.BLOCKED,
                error_type="TelegramDryRunEnabled",
            )

        try:
            await self.telegram_publisher.verify_connection()
            messages_read = None
            if source:
                await self.telegram_reader.verify_connection()
                messages = await self.telegram_reader.read_channel_messages(source, limit=1)
                messages_read = len(messages)
            test_message_id = None
            if publish_test:
                test_message_id = await self.telegram_publisher.publish_message(
                    TELEGRAM_VERIFICATION_MESSAGE
                )
        except (TelegramConfigurationError, TelegramAuthorizationError) as exc:
            return self._blocked("telegram", exc)
        except TelegramClientError as exc:
            return self._failed("telegram", exc)
        except Exception as exc:
            return self._failed("telegram", exc)

        return IntegrationCheckResult(
            service="telegram",
            status=IntegrationCheckStatus.PASSED,
            messages_read=messages_read,
            test_message_id=test_message_id,
        )

    def _blocked(self, service: str, exc: Exception) -> IntegrationCheckResult:
        """Вернуть внешний blocker без текста provider exception."""

        return IntegrationCheckResult(
            service=service,
            status=IntegrationCheckStatus.BLOCKED,
            error_type=exc.__class__.__name__,
        )

    def _failed(self, service: str, exc: Exception) -> IntegrationCheckResult:
        """Вернуть технический сбой без traceback и provider payload."""

        return IntegrationCheckResult(
            service=service,
            status=IntegrationCheckStatus.FAILED,
            error_type=exc.__class__.__name__,
        )

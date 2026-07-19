"""Контракты безопасной live-проверки внешних интеграций."""

from datetime import UTC, datetime

import pytest

from aibot.config import Settings
from aibot.integrations.ai_client import AIClientRateLimitError
from aibot.integrations.telegram_client import TelegramChannelMessage
from aibot.services.integration_verification import (
    IntegrationCheckStatus,
    IntegrationVerificationService,
)


class FakeAIClient:
    """Управляемый AI adapter для verification service."""

    def __init__(self, *, response: str = "Generated", exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc

    async def generate_telegram_post(self, _: str) -> str:
        """Вернуть ответ или внешнюю ошибку."""

        if self.exc is not None:
            raise self.exc
        return self.response


class FakeTelegramClient:
    """Управляемый Telegram adapter для verification service."""

    async def verify_connection(self) -> None:
        """Успешно проверить авторизованную session."""

    async def read_channel_messages(
        self,
        _: str,
        *,
        limit: int = 10,
    ) -> list[TelegramChannelMessage]:
        """Вернуть заданное количество fake-сообщений."""

        return [
            TelegramChannelMessage(
                message_id=1,
                text="Verification message",
                published_at=datetime(2026, 7, 19, tzinfo=UTC),
            )
        ][:limit]

    async def publish_message(self, _: str) -> str:
        """Вернуть fake ID явно запрошенной test-публикации."""

        return "42"


@pytest.mark.asyncio
async def test_openai_live_check_returns_only_safe_success_metadata() -> None:
    """Успех не раскрывает prompt или provider response."""

    service = IntegrationVerificationService(
        Settings(openai_api_key="test-key"),
        ai_client=FakeAIClient(response="Generated post"),
        telegram_client=FakeTelegramClient(),
    )

    result = await service.verify_openai()

    assert result.status == IntegrationCheckStatus.PASSED
    assert result.response_length == len("Generated post")
    assert result.error_type is None


@pytest.mark.asyncio
async def test_openai_quota_error_is_reported_without_provider_message() -> None:
    """Quota blocker возвращает только безопасное имя класса."""

    service = IntegrationVerificationService(
        Settings(openai_api_key="test-key"),
        ai_client=FakeAIClient(
            exc=AIClientRateLimitError("provider payload with request id")
        ),
        telegram_client=FakeTelegramClient(),
    )

    result = await service.verify_openai()

    assert result.status == IntegrationCheckStatus.BLOCKED
    assert result.error_type == "AIClientRateLimitError"
    assert "provider" not in str(result)


@pytest.mark.asyncio
async def test_telegram_live_check_reports_dry_run_as_external_blocker() -> None:
    """Dry-run не выдаётся за успешную real-mode проверку."""

    service = IntegrationVerificationService(
        Settings(telegram_dry_run=True),
        ai_client=FakeAIClient(),
        telegram_client=FakeTelegramClient(),
    )

    result = await service.verify_telegram()

    assert result.status == IntegrationCheckStatus.BLOCKED
    assert result.error_type == "TelegramDryRunEnabled"


@pytest.mark.asyncio
async def test_telegram_live_check_can_read_and_explicitly_publish() -> None:
    """Real-mode проверяет session, чтение и публикацию только по явному флагу."""

    service = IntegrationVerificationService(
        Settings(telegram_dry_run=False),
        ai_client=FakeAIClient(),
        telegram_client=FakeTelegramClient(),
    )

    result = await service.verify_telegram(
        source="@public_channel",
        publish_test=True,
    )

    assert result.status == IntegrationCheckStatus.PASSED
    assert result.messages_read == 1
    assert result.test_message_id == "42"

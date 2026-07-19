"""Контракты выбираемых Telegram publisher adapters."""

import json

import httpx
import pytest

from aibot.config import Settings
from aibot.integrations.telegram_bot_publisher import TelegramBotPublisher
from aibot.integrations.telegram_common import (
    TelegramAuthorizationError,
    TelegramConfigurationError,
    TelegramRateLimitError,
)
from aibot.integrations.telegram_publisher_factory import build_telegram_publisher
from aibot.integrations.telethon_publisher import TelethonPublisher


def test_telegram_publisher_defaults_to_required_telethon_contract() -> None:
    """Default сохраняет Telethon-публикацию из Project M4."""

    settings = Settings()

    assert settings.telegram_publisher == "telethon"
    assert isinstance(build_telegram_publisher(settings), TelethonPublisher)


def test_telegram_publisher_selects_bot_api_without_telethon_fallback() -> None:
    """Явный bot_api mode выбирает только Bot API adapter."""

    settings = Settings(telegram_publisher="bot_api")

    assert isinstance(build_telegram_publisher(settings), TelegramBotPublisher)


@pytest.mark.asyncio
async def test_bot_api_dry_run_does_not_require_token_or_make_request() -> None:
    """Dry-run безопасен до создания BotFather credentials."""

    async def fail_if_called(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Bot API must not be called in dry-run mode")

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail_if_called)) as client:
        publisher = TelegramBotPublisher(
            Settings(telegram_publisher="bot_api", telegram_dry_run=True),
            http_client=client,
        )

        message_id = await publisher.publish_message("Generated text")

    assert message_id.startswith("dry-run-")


@pytest.mark.asyncio
async def test_bot_api_publisher_sends_message_and_returns_message_id() -> None:
    """Bot API adapter использует sendMessage и общий target channel."""

    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 321}},
        )

    settings = Settings(
        telegram_publisher="bot_api",
        telegram_bot_token="123456:test-token",
        telegram_target_channel="@project_m4_test",
        telegram_dry_run=False,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = TelegramBotPublisher(settings, http_client=client)

        message_id = await publisher.publish_message("Generated text")

    assert message_id == "321"
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path.endswith("/sendMessage")
    assert json.loads(requests[0].content) == {
        "chat_id": "@project_m4_test",
        "text": "Generated text",
    }


@pytest.mark.asyncio
async def test_bot_api_requires_token_and_target_only_in_real_mode() -> None:
    """Real Bot API mode отклоняет неполную конфигурацию до HTTP."""

    publisher = TelegramBotPublisher(Settings(telegram_publisher="bot_api", telegram_dry_run=False))

    with pytest.raises(TelegramConfigurationError):
        await publisher.publish_message("Generated text")


@pytest.mark.asyncio
async def test_bot_api_auth_error_never_exposes_token_or_provider_description() -> None:
    """Ошибки Bot API остаются безопасными для Post и ErrorLog."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"ok": False, "description": "secret provider payload"},
        )

    token = "123456:must-not-leak"
    settings = Settings(
        telegram_publisher="bot_api",
        telegram_bot_token=token,
        telegram_target_channel="@project_m4_test",
        telegram_dry_run=False,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = TelegramBotPublisher(settings, http_client=client)

        with pytest.raises(TelegramAuthorizationError) as captured:
            await publisher.publish_message("Generated text")

    error_text = str(captured.value)
    assert token not in error_text
    assert "secret provider payload" not in error_text


@pytest.mark.asyncio
async def test_bot_api_rate_limit_preserves_only_safe_retry_after() -> None:
    """429 классифицируется отдельно без копирования provider payload."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "ok": False,
                "description": "provider payload",
                "parameters": {"retry_after": 7},
            },
        )

    settings = Settings(
        telegram_publisher="bot_api",
        telegram_bot_token="123456:test-token",
        telegram_target_channel="@project_m4_test",
        telegram_dry_run=False,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = TelegramBotPublisher(settings, http_client=client)

        with pytest.raises(TelegramRateLimitError) as captured:
            await publisher.publish_message("Generated text")

    assert captured.value.retry_after_seconds == 7
    assert "provider payload" not in str(captured.value)

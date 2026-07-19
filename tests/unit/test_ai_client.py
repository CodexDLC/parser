"""Тесты AIClient на границе с codex-ai без внешней сети."""

from typing import Any

import pytest
from codex_ai import LLMProviderError, PromptResult
from codex_ai.providers import openai as openai_provider_module

from aibot.config import Settings
from aibot.integrations.ai_client import (
    AIClient,
    AIClientAuthenticationError,
    AIClientInvalidResponseError,
    AIClientRateLimitError,
    AIClientTimeoutError,
)


class FakeTextProvider:
    """Тестовый text provider с контрактом codex-ai."""

    def __init__(self, *, content: str = "Generated post", exc: Exception | None = None) -> None:
        self.content = content
        self.exc = exc
        self.prompts: list[PromptResult] = []

    async def generate_text(
        self,
        prompt: PromptResult | str,
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        assert model is None
        assert kwargs == {}
        assert isinstance(prompt, PromptResult)
        self.prompts.append(prompt)
        if self.exc is not None:
            raise self.exc
        return self.content


class RateLimitError(Exception):
    """Имитировать исходную OpenAI rate-limit ошибку."""


class APITimeoutError(Exception):
    """Имитировать исходную OpenAI timeout ошибку."""


def provider_error(cause: Exception) -> LLMProviderError:
    """Создать ошибку codex-ai с сохранённой исходной причиной."""

    error = LLMProviderError("OpenAI Responses API error")
    error.__cause__ = cause
    return error


@pytest.mark.asyncio
async def test_ai_client_uses_codex_ai_prompt_contract() -> None:
    """AIClient передаёт system/user prompt через codex-ai PromptResult."""

    provider = FakeTextProvider()
    client = AIClient(Settings(openai_api_key="test-key"), provider=provider)

    generated_text = await client.generate_telegram_post("  Python   release  ")

    assert generated_text == "Generated post"
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert prompt.messages[0].role == "user"
    assert prompt.messages[0].content == "Python release"
    assert "Telegram-канала" in prompt.system
    assert prompt.max_tokens == 450


@pytest.mark.asyncio
async def test_ai_client_configures_terra_provider_without_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M4 явно передаёт Terra и оставляет retries Celery."""

    captured: dict[str, Any] = {}

    class CapturingOpenAIProvider(FakeTextProvider):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            captured.update(kwargs)

    monkeypatch.setattr(
        openai_provider_module,
        "OpenAIProvider",
        CapturingOpenAIProvider,
    )

    client = AIClient(
        Settings(
            openai_api_key="test-key",
            openai_model="gpt-5.6-terra",
            openai_timeout_seconds=42,
        )
    )
    await client.generate_telegram_post("Python release")

    assert captured == {
        "api_key": "test-key",
        "model": "gpt-5.6-terra",
        "reasoning_effort": "none",
        "store": False,
        "timeout": 42.0,
        "max_retries": 0,
    }


@pytest.mark.asyncio
async def test_ai_client_requires_openai_key_without_fake_fallback() -> None:
    """Отсутствующий OPENAI_API_KEY не включает скрытый fake-режим."""

    client = AIClient(Settings(openai_api_key=None))

    with pytest.raises(AIClientAuthenticationError, match="OPENAI_API_KEY"):
        await client.generate_telegram_post("Python release")


@pytest.mark.asyncio
async def test_ai_client_maps_rate_limit_error_from_codex_ai_cause() -> None:
    """AIClient мапит исходную rate limit ошибку, обёрнутую codex-ai."""

    client = AIClient(
        Settings(openai_api_key="test-key"),
        provider=FakeTextProvider(exc=provider_error(RateLimitError("too many requests"))),
    )

    with pytest.raises(AIClientRateLimitError):
        await client.generate_telegram_post("Python release")


@pytest.mark.asyncio
async def test_ai_client_maps_timeout_error_from_codex_ai_cause() -> None:
    """AIClient мапит исходную timeout ошибку, обёрнутую codex-ai."""

    client = AIClient(
        Settings(openai_api_key="test-key"),
        provider=FakeTextProvider(exc=provider_error(APITimeoutError("timeout"))),
    )

    with pytest.raises(AIClientTimeoutError):
        await client.generate_telegram_post("Python release")


@pytest.mark.asyncio
async def test_ai_client_rejects_empty_response() -> None:
    """AIClient отвергает пустой ответ provider-а."""

    client = AIClient(
        Settings(openai_api_key="test-key"),
        provider=FakeTextProvider(content=""),
    )

    with pytest.raises(AIClientInvalidResponseError):
        await client.generate_telegram_post("Python release")

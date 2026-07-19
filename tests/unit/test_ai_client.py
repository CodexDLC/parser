"""Тесты AIClient на границе с codex-ai без внешней сети."""

from typing import Any

import pytest
from codex_ai import LLMProviderError, PromptResult
from codex_ai.providers import gemini as gemini_provider_module
from codex_ai.providers import openai as openai_provider_module

from aibot.config import Settings
from aibot.integrations.ai_client import (
    AIClient,
    AIClientAuthenticationError,
    AIClientInvalidResponseError,
    AIClientRateLimitError,
    AIClientTimeoutError,
)

VALID_POST = (
    "🚀 Astra Studio помогает командам работать с несколькими ИИ-моделями "
    "через единый интерфейс. Платформа поддерживает совместную работу, управление "
    "диалогами и развёртывание в собственной инфраструктуре. "
    "Изучите возможности проекта и оцените, подходит ли он вашей команде."
)


class FakeTextProvider:
    """Тестовый text provider с контрактом codex-ai."""

    def __init__(self, *, content: str = VALID_POST, exc: Exception | None = None) -> None:
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

    assert generated_text == VALID_POST
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert prompt.messages[0].role == "user"
    assert prompt.messages[0].content == "Python release"
    assert "Telegram-канала" in prompt.system
    assert prompt.max_tokens == 2048
    assert "Markdown" in prompt.system


@pytest.mark.asyncio
async def test_ai_client_uses_gemini_fallback_after_primary_provider_error() -> None:
    """Ошибка primary provider-а переключает генерацию на Gemini fallback."""

    primary_provider = FakeTextProvider(
        exc=provider_error(RateLimitError("primary quota exhausted"))
    )
    fallback_provider = FakeTextProvider(content=VALID_POST)
    client = AIClient(
        Settings(
            openai_api_key="openai-test-key",
            gemini_api_key="gemini-test-key",
        ),
        provider=primary_provider,
        fallback_provider=fallback_provider,
    )

    generated_text = await client.generate_telegram_post("Python release")

    assert generated_text == VALID_POST
    assert len(primary_provider.prompts) == 1
    assert len(fallback_provider.prompts) == 1


@pytest.mark.asyncio
async def test_ai_client_does_not_call_gemini_after_primary_success() -> None:
    """Успешный primary provider не создаёт лишний Gemini-запрос."""

    primary_provider = FakeTextProvider(content=VALID_POST)
    fallback_provider = FakeTextProvider(content="Must not be used")
    client = AIClient(
        Settings(
            openai_api_key="openai-test-key",
            gemini_api_key="gemini-test-key",
        ),
        provider=primary_provider,
        fallback_provider=fallback_provider,
    )

    generated_text = await client.generate_telegram_post("Python release")

    assert generated_text == VALID_POST
    assert len(primary_provider.prompts) == 1
    assert fallback_provider.prompts == []


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
async def test_ai_client_builds_openai_to_gemini_runtime_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime factory создаёт Gemini с отдельным ключом и моделью после OpenAI."""

    captured_openai: dict[str, Any] = {}
    captured_gemini: dict[str, Any] = {}

    class FailingOpenAIProvider(FakeTextProvider):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(exc=provider_error(RateLimitError("quota exhausted")))
            captured_openai.update(kwargs)

    class CapturingGeminiProvider(FakeTextProvider):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(content=VALID_POST)
            captured_gemini.update(kwargs)

    monkeypatch.setattr(openai_provider_module, "OpenAIProvider", FailingOpenAIProvider)
    monkeypatch.setattr(gemini_provider_module, "GeminiProvider", CapturingGeminiProvider)

    client = AIClient(
        Settings(
            ai_provider="openai",
            ai_fallback_provider="gemini",
            openai_api_key="openai-test-key",
            openai_model="gpt-5.6-terra",
            gemini_api_key="gemini-test-key",
            gemini_model="gemini-3.5-flash",
        )
    )

    generated_text = await client.generate_telegram_post("Python release")

    assert generated_text == VALID_POST
    assert captured_openai["api_key"] == "openai-test-key"
    assert captured_openai["model"] == "gpt-5.6-terra"
    assert captured_gemini == {
        "api_key": "gemini-test-key",
        "model": "gemini-3.5-flash",
    }


@pytest.mark.asyncio
async def test_ai_client_requires_openai_key_without_fake_fallback() -> None:
    """Отсутствующие AI credentials не включают скрытый fake-режим."""

    client = AIClient(Settings(openai_api_key=None, gemini_api_key=None))

    with pytest.raises(AIClientAuthenticationError, match="AI provider credentials"):
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


@pytest.mark.asyncio
async def test_ai_client_rejects_truncated_markdown_response() -> None:
    """Оборванный Gemini-ответ не может попасть в Post и Telegram."""

    client = AIClient(
        Settings(openai_api_key="test-key"),
        provider=FakeTextProvider(
            content="🚀 **Astra Studio: мощная open-source платформа для работы с ИИ без"
        ),
    )

    with pytest.raises(AIClientInvalidResponseError, match="incomplete"):
        await client.generate_telegram_post("Python release")

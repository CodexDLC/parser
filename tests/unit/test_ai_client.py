"""Тесты OpenAI-compatible AIClient без внешней сети."""

import pytest

from aibot.config import Settings
from aibot.integrations.ai_client import (
    AIClient,
    AIClientInvalidResponseError,
    AIClientRateLimitError,
    AIClientTimeoutError,
)


class RateLimitError(Exception):
    """Fake SDK rate limit error."""


class APITimeoutError(Exception):
    """Fake SDK timeout error."""


class FakeMessage:
    """Fake OpenAI message."""

    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeChoice:
    """Fake OpenAI choice."""

    def __init__(self, content: str | None) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    """Fake OpenAI response."""

    def __init__(self, content: str | None) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    """Fake completions endpoint."""

    def __init__(self, *, content: str | None = "Generated post", exc: Exception | None = None):
        self.content = content
        self.exc = exc

    async def create(self, **_: object) -> FakeResponse:
        if self.exc is not None:
            raise self.exc
        return FakeResponse(self.content)


class FakeChat:
    """Fake chat API."""

    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeOpenAIClient:
    """Fake AsyncOpenAI-compatible client."""

    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = FakeChat(completions)


def real_mode_settings() -> Settings:
    """Вернуть Settings, которые включают real-mode AI без настоящего SDK вызова."""

    return Settings(ai_fake_mode=False, openai_api_key="test-key")


@pytest.mark.asyncio
async def test_ai_client_real_mode_uses_openai_compatible_client() -> None:
    """AIClient получает текст через OpenAI-compatible client."""

    client = AIClient(real_mode_settings(), FakeOpenAIClient(FakeCompletions()))

    generated_text = await client.generate_telegram_post("Python release")

    assert generated_text == "Generated post"


@pytest.mark.asyncio
async def test_ai_client_maps_rate_limit_error() -> None:
    """AIClient мапит rate limit SDK-ошибку в доменную ошибку."""

    client = AIClient(
        real_mode_settings(),
        FakeOpenAIClient(FakeCompletions(exc=RateLimitError("too many requests"))),
    )

    with pytest.raises(AIClientRateLimitError):
        await client.generate_telegram_post("Python release")


@pytest.mark.asyncio
async def test_ai_client_maps_timeout_error() -> None:
    """AIClient мапит timeout SDK-ошибку в доменную ошибку."""

    client = AIClient(
        real_mode_settings(),
        FakeOpenAIClient(FakeCompletions(exc=APITimeoutError("timeout"))),
    )

    with pytest.raises(AIClientTimeoutError):
        await client.generate_telegram_post("Python release")


@pytest.mark.asyncio
async def test_ai_client_rejects_empty_response() -> None:
    """AIClient отвергает пустой ответ provider-а."""

    client = AIClient(real_mode_settings(), FakeOpenAIClient(FakeCompletions(content="")))

    with pytest.raises(AIClientInvalidResponseError):
        await client.generate_telegram_post("Python release")

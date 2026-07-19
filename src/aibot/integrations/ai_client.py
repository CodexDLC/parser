"""Адаптер codex-ai для генерации Telegram-постов через OpenAI Responses API."""

from typing import NoReturn

from codex_ai import (
    LLMMessage,
    LLMProviderError,
    PromptResult,
    TextGenerationProvider,
)

from aibot.config import Settings

SYSTEM_PROMPT = (
    "Сделай краткое, интересное описание новости для Telegram-канала. "
    "Добавь 1-3 emoji, сохрани факты, не выдумывай подробности. "
    "В конце добавь короткий call to action. "
    "Текст должен быть на русском языке и не длиннее 900 символов."
)


class AIClientError(Exception):
    """Базовая ошибка AI-интеграции."""


class AIClientRateLimitError(AIClientError):
    """AI provider вернул rate limit."""


class AIClientTimeoutError(AIClientError):
    """AI provider не ответил за ожидаемое время."""


class AIClientAuthenticationError(AIClientError):
    """AI provider отклонил credentials."""


class AIClientInvalidResponseError(AIClientError):
    """AI provider вернул пустой или неподходящий ответ."""


class AIClient:
    """Антикоррупционный адаптер между M4 и codex-ai."""

    def __init__(
        self,
        settings: Settings,
        *,
        provider: TextGenerationProvider | None = None,
    ) -> None:
        self.settings = settings
        self._provider = provider

    async def generate_telegram_post(self, input_text: str) -> str:
        """Сгенерировать Telegram-пост через настроенный codex-ai provider."""

        compact_text = " ".join(input_text.split())
        if not compact_text:
            raise AIClientInvalidResponseError("Input text is empty")
        if self._provider is None and not self.settings.openai_api_key:
            raise AIClientAuthenticationError("OPENAI_API_KEY is not configured")

        provider = self._provider or self._build_provider()
        prompt = PromptResult(
            messages=[LLMMessage(role="user", content=compact_text)],
            system=SYSTEM_PROMPT,
            max_tokens=450,
        )
        try:
            generated_text = await provider.generate_text(prompt)
        except LLMProviderError as exc:
            self._raise_mapped_error(exc)

        if not generated_text or not generated_text.strip():
            raise AIClientInvalidResponseError("AI provider returned empty response")
        return generated_text.strip()

    def _build_provider(self) -> TextGenerationProvider:
        """Лениво создать OpenAI provider с retry-политикой, принадлежащей Celery."""

        from codex_ai.providers.openai import OpenAIProvider

        return OpenAIProvider(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            reasoning_effort="none",
            store=False,
            timeout=self.settings.openai_timeout_seconds,
            max_retries=0,
        )

    @staticmethod
    def _raise_mapped_error(exc: LLMProviderError) -> NoReturn:
        """Преобразовать ошибку codex-ai в стабильный контракт M4."""

        cause = exc.__cause__
        error_name = cause.__class__.__name__ if cause is not None else exc.__class__.__name__
        message = str(exc) or error_name
        if error_name == "RateLimitError":
            raise AIClientRateLimitError(message) from exc
        if error_name in {"APITimeoutError", "ConnectTimeout", "ReadTimeout"}:
            raise AIClientTimeoutError(message) from exc
        if error_name in {"AuthenticationError", "OpenAIError"} and "api key" in message.lower():
            raise AIClientAuthenticationError(message) from exc
        raise AIClientError(message) from exc

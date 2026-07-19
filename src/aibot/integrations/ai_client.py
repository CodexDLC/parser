"""Стабильный M4-адаптер поверх выбранной codex-ai provider chain."""

from typing import NoReturn

from codex_ai import (
    LLMMessage,
    LLMProviderError,
    PromptResult,
    TextGenerationProvider,
)

from aibot.config import Settings
from aibot.integrations.ai_response_validator import (
    AIResponseValidationError,
    PlainTextTelegramPostValidator,
)

SYSTEM_PROMPT = (
    "Подготовь законченный информационный пост для русскоязычного Telegram-канала. "
    "Сохрани факты исходной новости и не выдумывай подробности. Добавь 1-3 уместных "
    "emoji, короткий заголовок, 2-3 небольших абзаца и короткий призыв ознакомиться "
    "с темой. Объём готового текста — 350-700 символов, абсолютный максимум — "
    "900 символов. Верни только обычный текст без Markdown, HTML, звёздочек, "
    "обратных кавычек и служебных пояснений. Обязательно закончи последнее "
    "предложение знаком точки, вопроса, восклицания или многоточием."
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
        fallback_provider: TextGenerationProvider | None = None,
        response_validator: PlainTextTelegramPostValidator | None = None,
    ) -> None:
        self.settings = settings
        if provider is None and fallback_provider is not None:
            raise ValueError("fallback_provider requires provider")
        if provider is not None and fallback_provider is not None:
            from aibot.integrations.ai_fallback_provider import FallbackTextProvider

            provider = FallbackTextProvider(
                primary=provider,
                fallback=fallback_provider,
                primary_name=settings.ai_provider,
                fallback_name=settings.ai_fallback_provider or "fallback",
            )
        self._provider = provider
        self._response_validator = response_validator or PlainTextTelegramPostValidator()

    async def generate_telegram_post(self, input_text: str) -> str:
        """Сгенерировать Telegram-пост через настроенный codex-ai provider."""

        compact_text = " ".join(input_text.split())
        if not compact_text:
            raise AIClientInvalidResponseError("Input text is empty")
        try:
            provider = self._provider or self._build_provider()
        except Exception as exc:
            from aibot.integrations.ai_provider_factory import AIProviderConfigurationError

            if isinstance(exc, AIProviderConfigurationError):
                raise AIClientAuthenticationError(str(exc)) from exc
            raise
        prompt = PromptResult(
            messages=[LLMMessage(role="user", content=compact_text)],
            system=SYSTEM_PROMPT,
            max_tokens=self.settings.ai_max_output_tokens,
        )
        try:
            generated_text = await provider.generate_text(prompt)
        except LLMProviderError as exc:
            self._raise_mapped_error(exc)

        try:
            return self._response_validator.validate(generated_text)
        except AIResponseValidationError as exc:
            raise AIClientInvalidResponseError(str(exc)) from exc

    def _build_provider(self) -> TextGenerationProvider:
        """Лениво создать primary/fallback provider chain из runtime settings."""

        from aibot.integrations.ai_provider_factory import build_text_provider

        return build_text_provider(self.settings)

    @staticmethod
    def _raise_mapped_error(exc: LLMProviderError) -> NoReturn:
        """Преобразовать ошибку codex-ai в стабильный контракт M4."""

        cause = exc.__cause__
        error_name = cause.__class__.__name__ if cause is not None else exc.__class__.__name__
        message = str(exc) or error_name
        status_code = getattr(cause, "status_code", None)
        normalized_message = message.lower()
        if (
            error_name == "RateLimitError"
            or status_code == 429
            or "resource_exhausted" in normalized_message
        ):
            raise AIClientRateLimitError(message) from exc
        if error_name in {
            "APITimeoutError",
            "ConnectTimeout",
            "ReadTimeout",
            "TimeoutError",
            "TimeoutException",
        }:
            raise AIClientTimeoutError(message) from exc
        if (
            status_code in {401, 403}
            or "api_key_invalid" in normalized_message
            or "api key not valid" in normalized_message
            or (
                error_name in {"AuthenticationError", "OpenAIError"}
                and "api key" in normalized_message
            )
        ):
            raise AIClientAuthenticationError(message) from exc
        raise AIClientError(message) from exc

"""Клиент OpenAI-compatible API для генерации текста постов."""

from typing import Any

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
    """Клиент генерации текста с безопасным fake-режимом для прототипа."""

    def __init__(self, settings: Settings, openai_client: Any | None = None) -> None:
        self.settings = settings
        self.openai_client = openai_client

    async def generate_telegram_post(self, input_text: str) -> str:
        """Сгенерировать Telegram-пост или вернуть fake-текст без внешнего API."""

        compact_text = " ".join(input_text.split())
        if not compact_text:
            raise AIClientInvalidResponseError("Input text is empty")

        if self.settings.ai_fake_mode or not self.settings.openai_api_key:
            preview = compact_text[:220]
            return (
                f"📰 {preview}\n\n"
                "Коротко и по делу: следим за развитием темы. "
                "Что думаете об этой новости?"
            )

        client = self.openai_client or self._build_openai_client()
        try:
            response = await client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": compact_text},
                ],
                max_tokens=450,
                temperature=0.4,
            )
        except Exception as exc:
            self._raise_mapped_error(exc)

        generated_text = response.choices[0].message.content if response.choices else None
        if not generated_text or not generated_text.strip():
            raise AIClientInvalidResponseError("AI provider returned empty response")
        return generated_text.strip()

    def _build_openai_client(self) -> Any:
        """Создать OpenAI-compatible async client лениво, только для real-mode."""

        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.settings.openai_api_key)

    def _raise_mapped_error(self, exc: Exception) -> None:
        """Преобразовать SDK-ошибку в доменную ошибку AI-интеграции."""

        error_name = exc.__class__.__name__
        message = str(exc) or error_name
        if error_name == "RateLimitError":
            raise AIClientRateLimitError(message) from exc
        if error_name == "APITimeoutError":
            raise AIClientTimeoutError(message) from exc
        if error_name == "AuthenticationError":
            raise AIClientAuthenticationError(message) from exc
        raise AIClientError(message) from exc

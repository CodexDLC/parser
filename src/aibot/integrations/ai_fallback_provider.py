"""Последовательный fallback между двумя codex-ai text provider-ами."""

import logging
from typing import Any

from codex_ai import LLMProviderError, PromptResult, TextGenerationProvider

logger = logging.getLogger(__name__)


class FallbackTextProvider:
    """Вызвать secondary provider только после ошибки primary provider-а."""

    def __init__(
        self,
        *,
        primary: TextGenerationProvider,
        fallback: TextGenerationProvider,
        primary_name: str,
        fallback_name: str,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_name
        self._fallback_name = fallback_name

    async def generate_text(
        self,
        prompt: PromptResult | str,
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Вернуть primary-ответ либо один раз обратиться к fallback provider-у."""

        try:
            return await self._primary.generate_text(prompt, model=model, **kwargs)
        except LLMProviderError as primary_exc:
            logger.warning(
                "AI provider fallback activated: primary=%s fallback=%s",
                self._primary_name,
                self._fallback_name,
            )
            try:
                return await self._fallback.generate_text(prompt, model=model, **kwargs)
            except LLMProviderError as fallback_exc:
                raise fallback_exc from primary_exc

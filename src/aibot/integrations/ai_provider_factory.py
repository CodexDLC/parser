"""Factory codex-ai provider-ов с конфигурируемым primary/fallback порядком."""

from typing import Literal

from codex_ai import TextGenerationProvider

from aibot.config import Settings
from aibot.integrations.ai_fallback_provider import FallbackTextProvider

AIProviderName = Literal["openai", "gemini"]


class AIProviderConfigurationError(Exception):
    """Ни один выбранный AI provider не имеет credentials."""


def build_text_provider(settings: Settings) -> TextGenerationProvider:
    """Построить один provider или primary/fallback chain без скрытого fake-режима."""

    provider_names = _ordered_provider_names(settings)
    configured = [
        (name, _build_named_provider(name, settings))
        for name in provider_names
        if settings.ai_provider_configured(name)
    ]
    if not configured:
        raise AIProviderConfigurationError(
            f"AI provider credentials are not configured for primary={settings.ai_provider}"
        )
    if len(configured) == 1:
        return configured[0][1]

    primary_name, primary = configured[0]
    fallback_name, fallback = configured[1]
    return FallbackTextProvider(
        primary=primary,
        fallback=fallback,
        primary_name=primary_name,
        fallback_name=fallback_name,
    )


def _ordered_provider_names(settings: Settings) -> tuple[AIProviderName, ...]:
    """Вернуть уникальный порядок primary/fallback из runtime settings."""

    if (
        settings.ai_fallback_provider is None
        or settings.ai_fallback_provider == settings.ai_provider
    ):
        return (settings.ai_provider,)
    return (settings.ai_provider, settings.ai_fallback_provider)


def _build_named_provider(
    provider_name: AIProviderName,
    settings: Settings,
) -> TextGenerationProvider:
    """Создать конкретный codex-ai adapter только для настроенного provider-а."""

    if provider_name == "openai":
        from codex_ai.providers.openai import OpenAIProvider

        assert settings.openai_api_key is not None
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            reasoning_effort="none",
            store=False,
            timeout=settings.openai_timeout_seconds,
            max_retries=0,
        )

    from codex_ai.providers.gemini import GeminiProvider

    assert settings.gemini_api_key is not None
    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )

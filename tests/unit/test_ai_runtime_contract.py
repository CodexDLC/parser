"""Защитные тесты нового AI runtime-контракта."""

from pathlib import Path

from aibot.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_terra_is_the_default_ai_model() -> None:
    """Новая конфигурация по умолчанию выбирает GPT-5.6 Terra."""

    assert Settings().openai_model == "gpt-5.6-terra"


def test_openai_primary_and_gemini_fallback_are_default_ai_chain() -> None:
    """Runtime по умолчанию сохраняет OpenAI и объявляет Gemini fallback."""

    settings = Settings()

    assert settings.ai_provider == "openai"
    assert settings.ai_fallback_provider == "gemini"
    assert settings.gemini_model == "gemini-3.5-flash"


def test_example_env_declares_switchable_ai_provider_chain() -> None:
    """Публичный env-контракт содержит provider selection и оба набора credentials."""

    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    for expected in (
        'AI_PROVIDER="openai"',
        'AI_FALLBACK_PROVIDER="gemini"',
        'OPENAI_API_KEY=""',
        'OPENAI_MODEL="gpt-5.6-terra"',
        'GEMINI_API_KEY=""',
        'GEMINI_MODEL="gemini-3.5-flash"',
    ):
        assert expected in env_example


def test_codex_ai_installs_openai_and_gemini_extras() -> None:
    """Runtime dependency включает оба поддерживаемых codex-ai adapter-а."""

    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"codex-ai[openai,gemini]==0.2.5"' in pyproject


def test_legacy_ai_fake_and_direct_sdk_are_removed() -> None:
    """Production-код больше не содержит fake AI или прямой AsyncOpenAI."""

    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (PROJECT_ROOT / "src" / "aibot").rglob("*.py")
    )

    assert "AI_FAKE_MODE" not in source_text
    assert "ai_fake_mode" not in source_text
    assert "AsyncOpenAI" not in source_text

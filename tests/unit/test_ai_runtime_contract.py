"""Защитные тесты нового AI runtime-контракта."""

from pathlib import Path

from aibot.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_terra_is_the_default_ai_model() -> None:
    """Новая конфигурация по умолчанию выбирает GPT-5.6 Terra."""

    assert Settings().openai_model == "gpt-5.6-terra"


def test_legacy_ai_fake_and_direct_sdk_are_removed() -> None:
    """Production-код больше не содержит fake AI или прямой AsyncOpenAI."""

    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "src" / "aibot").rglob("*.py")
    )

    assert "AI_FAKE_MODE" not in source_text
    assert "ai_fake_mode" not in source_text
    assert "AsyncOpenAI" not in source_text

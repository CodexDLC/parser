"""Тесты определения языка и language-first фильтрации."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aibot.config import Settings
from aibot.parsers.base import ParsedNewsItem
from aibot.services.filtering import KeywordFilterService
from aibot.services.language_detection import LanguageDetector


@dataclass(frozen=True)
class FakeKeyword:
    """Минимальное ключевое слово для filter contract."""

    word: str
    enabled: bool = True


class FixedLanguageDetector:
    """Детерминированный language detector для filter unit-тестов."""

    def __init__(self, language: str | None) -> None:
        self.language = language
        self.received_texts: list[str] = []

    def detect(self, text: str) -> str | None:
        self.received_texts.append(text)
        return self.language


def make_news_item(
    text: str = "Python received an important performance update.",
) -> ParsedNewsItem:
    """Создать нормализованную новость для language filter."""

    return ParsedNewsItem(
        title=text,
        url="https://news.example/item",
        summary="Developers published detailed release notes for the community.",
        source="Example",
        published_at=datetime(2026, 7, 19, tzinfo=UTC),
        raw_text="The new runtime is faster in common workloads.",
    )


@pytest.mark.parametrize(
    ("text", "expected_language"),
    [
        (
            "Разработчики выпустили обновление языка программирования "
            "и подробно описали улучшения производительности.",
            "ru",
        ),
        (
            "Developers released a programming language update "
            "with several important runtime performance improvements.",
            "en",
        ),
        ("12345 !!!", None),
    ],
)
def test_language_detector_returns_normalized_language_or_none(
    text: str,
    expected_language: str | None,
) -> None:
    """LanguageDetector стабильно определяет ru/en и обрабатывает неизвестный язык."""

    assert LanguageDetector().detect(text) == expected_language


def test_filter_rejects_disallowed_language_before_keyword_matching() -> None:
    """Совпавшее ключевое слово не пропускает запрещённый язык."""

    detector = FixedLanguageDetector("de")
    item = make_news_item("Python wurde schneller")
    service = KeywordFilterService(
        allowed_languages={"ru", "en"},
        language_detector=detector,
    )

    decision = service.evaluate(item, [FakeKeyword("python")])

    assert decision.accepted is False
    assert decision.reason == "language_not_allowed"
    assert decision.detected_language == "de"
    assert decision.matched_keywords == []
    assert detector.received_texts == [item.text_for_filtering]


def test_filter_rejects_unknown_language() -> None:
    """Неопределённый язык получает отдельную причину filtered_out."""

    service = KeywordFilterService(
        allowed_languages={"ru", "en"},
        language_detector=FixedLanguageDetector(None),
    )

    decision = service.evaluate(make_news_item("12345"), [FakeKeyword("12345")])

    assert decision.accepted is False
    assert decision.reason == "language_unknown"
    assert decision.detected_language is None
    assert decision.matched_keywords == []


def test_filter_checks_keywords_after_allowed_language() -> None:
    """Для разрешённого языка сохраняется существующая keyword-фильтрация."""

    service = KeywordFilterService(
        allowed_languages={"ru", "en"},
        language_detector=FixedLanguageDetector("en"),
    )

    decision = service.evaluate(make_news_item(), [FakeKeyword("python")])

    assert decision.accepted is True
    assert decision.reason == "matched_keywords"
    assert decision.detected_language == "en"
    assert decision.matched_keywords == ["python"]


def test_settings_normalize_allowed_language_codes() -> None:
    """Comma-separated env setting преобразуется в уникальные lowercase codes."""

    settings = Settings(news_allowed_languages=" RU, en, ru ")

    assert settings.news_allowed_languages == "ru,en"
    assert settings.allowed_news_languages == frozenset({"ru", "en"})


@pytest.mark.parametrize("value", ["", "russian", "ru,english", "ru,*"])
def test_settings_reject_invalid_allowed_languages(value: str) -> None:
    """Пустая или невалидная language-конфигурация останавливает startup."""

    with pytest.raises(ValidationError):
        Settings(news_allowed_languages=value)

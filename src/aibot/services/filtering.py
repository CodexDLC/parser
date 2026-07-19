"""Единая фильтрация новостей по языку и ключевым словам."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

from aibot.parsers.base import ParsedNewsItem
from aibot.services.language_detection import LanguageDetector


class KeywordLike(Protocol):
    """Минимальный контракт объекта ключевого слова для фильтрации."""

    @property
    def word(self) -> str:
        """Вернуть текст ключевого слова."""

    @property
    def enabled(self) -> bool:
        """Вернуть признак активности ключевого слова."""


class LanguageDetectorPort(Protocol):
    """Минимальный контракт определения языка."""

    def detect(self, text: str) -> str | None:
        """Вернуть ISO language code или None."""


@dataclass(frozen=True)
class FilterDecision:
    """Результат фильтрации одной новости."""

    accepted: bool
    reason: str
    matched_keywords: list[str]
    detected_language: str | None


class KeywordFilterService:
    """Сначала проверить язык новости, затем включенные ключевые слова."""

    def __init__(
        self,
        *,
        allowed_languages: Collection[str] = ("ru", "en"),
        language_detector: LanguageDetectorPort | None = None,
    ) -> None:
        normalized_languages = {
            language.strip().lower().replace("_", "-")
            for language in allowed_languages
            if language.strip()
        }
        if not normalized_languages:
            raise ValueError("allowed_languages must not be empty")
        self.allowed_languages = frozenset(normalized_languages)
        self.language_detector = language_detector or LanguageDetector()

    def evaluate(
        self,
        news_item: ParsedNewsItem,
        keywords: Sequence[KeywordLike],
    ) -> FilterDecision:
        """Проверить язык, а затем соответствие ключевым словам."""

        detected_language = self.language_detector.detect(news_item.text_for_filtering)
        if detected_language is None:
            return FilterDecision(
                accepted=False,
                reason="language_unknown",
                matched_keywords=[],
                detected_language=None,
            )
        if detected_language not in self.allowed_languages:
            return FilterDecision(
                accepted=False,
                reason="language_not_allowed",
                matched_keywords=[],
                detected_language=detected_language,
            )

        enabled_words = [keyword.word.strip() for keyword in keywords if keyword.enabled]
        enabled_words = [word for word in enabled_words if word]
        if not enabled_words:
            return FilterDecision(
                accepted=True,
                reason="no_keywords_configured",
                matched_keywords=[],
                detected_language=detected_language,
            )

        searchable_text = news_item.text_for_filtering.lower()
        matched_keywords = [word for word in enabled_words if word.lower() in searchable_text]
        if matched_keywords:
            return FilterDecision(
                accepted=True,
                reason="matched_keywords",
                matched_keywords=matched_keywords,
                detected_language=detected_language,
            )

        return FilterDecision(
            accepted=False,
            reason="no_keyword_match",
            matched_keywords=[],
            detected_language=detected_language,
        )

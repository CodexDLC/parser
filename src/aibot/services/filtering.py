"""Фильтрация новостей по ключевым словам, языку и источнику."""

from dataclasses import dataclass
from typing import Protocol

from aibot.parsers.base import ParsedNewsItem


class KeywordLike(Protocol):
    """Минимальный контракт объекта ключевого слова для фильтрации."""

    word: str
    enabled: bool


@dataclass(frozen=True)
class FilterDecision:
    """Результат фильтрации одной новости."""

    accepted: bool
    reason: str
    matched_keywords: list[str]


class KeywordFilterService:
    """Фильтрация новостей по включенным ключевым словам."""

    def evaluate(self, news_item: ParsedNewsItem, keywords: list[KeywordLike]) -> FilterDecision:
        """Проверить, подходит ли новость под список ключевых слов."""

        enabled_words = [keyword.word.strip() for keyword in keywords if keyword.enabled]
        enabled_words = [word for word in enabled_words if word]
        if not enabled_words:
            return FilterDecision(
                accepted=True,
                reason="no_keywords_configured",
                matched_keywords=[],
            )

        searchable_text = news_item.text_for_filtering.lower()
        matched_keywords = [word for word in enabled_words if word.lower() in searchable_text]
        if matched_keywords:
            return FilterDecision(
                accepted=True,
                reason="matched_keywords",
                matched_keywords=matched_keywords,
            )

        return FilterDecision(
            accepted=False,
            reason="no_keyword_match",
            matched_keywords=[],
        )

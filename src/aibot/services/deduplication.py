"""Дедупликация новостей по URL, заголовку и hash контента."""

import hashlib
import re

from aibot.parsers.base import ParsedNewsItem

WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_for_hash(value: str) -> str:
    """Нормализовать текст перед вычислением hash."""

    return WHITESPACE_PATTERN.sub(" ", value).strip().lower()


def build_content_hash(news_item: ParsedNewsItem) -> str:
    """Построить стабильный hash новости для дедупликации."""

    identity = news_item.url or news_item.text_for_filtering
    normalized_identity = normalize_for_hash(identity)
    return hashlib.sha256(normalized_identity.encode("utf-8")).hexdigest()


class DeduplicationService:
    """Сервис проверки дублей среди нормализованных новостей."""

    def is_duplicate(
        self,
        news_item: ParsedNewsItem,
        *,
        existing_urls: set[str],
        existing_hashes: set[str],
    ) -> bool:
        """Проверить, является ли новость дублем по URL или content hash."""

        if news_item.url and news_item.url in existing_urls:
            return True
        return build_content_hash(news_item) in existing_hashes

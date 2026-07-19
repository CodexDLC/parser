"""Фильтрация уже сохраненных NewsItem по текущим ключевым словам."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.config import Settings, get_settings
from aibot.models.enums import NewsStatus
from aibot.models.news_item import NewsItem
from aibot.parsers.base import ParsedNewsItem
from aibot.repositories.keyword_repository import KeywordRepository
from aibot.repositories.news_repository import NewsRepository
from aibot.services.exceptions import EntityNotFoundError, InvalidNewsStateError
from aibot.services.filtering import KeywordFilterService


@dataclass(frozen=True)
class NewsFilteringResult:
    """Результат фильтрации сохраненной новости."""

    news_id: uuid.UUID
    status: NewsStatus
    reason: str
    matched_keywords: list[str]
    detected_language: str | None


class SavedNewsFilteringService:
    """Сервис повторной фильтрации сохраненных новостей."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        news_repository: NewsRepository | None = None,
        keyword_repository: KeywordRepository | None = None,
        settings: Settings | None = None,
        keyword_filter_service: KeywordFilterService | None = None,
    ) -> None:
        runtime_settings = settings or get_settings()
        self.session = session
        self.news_repository = news_repository or NewsRepository(session)
        self.keyword_repository = keyword_repository or KeywordRepository(session)
        self.keyword_filter_service = keyword_filter_service or KeywordFilterService(
            allowed_languages=runtime_settings.allowed_news_languages
        )

    async def filter_news(self, news_id: uuid.UUID) -> NewsFilteringResult:
        """Проверить сохраненную новость и обновить ее статус."""

        news_item = await self.news_repository.get(news_id)
        if news_item is None:
            raise EntityNotFoundError("News item not found")
        if news_item.status not in {NewsStatus.NEW, NewsStatus.READY_FOR_GENERATION}:
            raise InvalidNewsStateError("Only new or ready_for_generation news can be filtered")

        enabled_keywords = await self.keyword_repository.list_enabled()
        decision = self.keyword_filter_service.evaluate(
            self._to_parsed_news_item(news_item),
            enabled_keywords,
        )
        news_item.status = (
            NewsStatus.READY_FOR_GENERATION if decision.accepted else NewsStatus.FILTERED_OUT
        )
        await self.session.commit()
        await self.session.refresh(news_item)

        return NewsFilteringResult(
            news_id=news_item.id,
            status=news_item.status,
            reason=decision.reason,
            matched_keywords=decision.matched_keywords,
            detected_language=decision.detected_language,
        )

    def _to_parsed_news_item(self, news_item: NewsItem) -> ParsedNewsItem:
        """Преобразовать ORM NewsItem в объект, понятный KeywordFilterService."""

        return ParsedNewsItem(
            title=news_item.title,
            url=news_item.url,
            summary=news_item.summary,
            source=news_item.source.name if news_item.source is not None else "",
            published_at=news_item.published_at,
            raw_text=news_item.raw_text,
        )

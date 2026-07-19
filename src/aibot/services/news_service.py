"""Бизнес-логика сохранения, отбора и просмотра новостей."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.models.enums import NewsStatus
from aibot.models.news_item import NewsItem
from aibot.repositories.news_repository import NewsRepository
from aibot.services.exceptions import EntityNotFoundError


class NewsService:
    """Бизнес-логика просмотра новостей."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = NewsRepository(session)

    async def list_news(
        self,
        *,
        source_id: uuid.UUID | None = None,
        status: NewsStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NewsItem]:
        """Вернуть список новостей."""

        return await self.repository.list_filtered(
            source_id=source_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_news_item(self, news_id: uuid.UUID) -> NewsItem:
        """Вернуть новость по ID или поднять ошибку."""

        news_item = await self.repository.get(news_id)
        if news_item is None:
            raise EntityNotFoundError("News item not found")
        return news_item

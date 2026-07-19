"""Repository для чтения, сохранения и дедупликации новостей."""

import uuid

from sqlalchemy import select

from aibot.models.enums import NewsStatus
from aibot.models.news_item import NewsItem
from aibot.repositories.base_repository import BaseRepository


class NewsRepository(BaseRepository[NewsItem]):
    """Repository для чтения, сохранения и дедупликации новостей."""

    model = NewsItem

    async def get_by_url(self, url: str) -> NewsItem | None:
        """Найти новость по URL."""

        return await self.session.scalar(select(NewsItem).where(NewsItem.url == url))

    async def get_by_content_hash(self, content_hash: str) -> NewsItem | None:
        """Найти новость по hash содержимого."""

        return await self.session.scalar(
            select(NewsItem).where(NewsItem.content_hash == content_hash)
        )

    async def get_for_generation(self, news_id: uuid.UUID) -> NewsItem | None:
        """Получить news с row lock или вернуть None, если lock уже занят."""

        statement = (
            select(NewsItem)
            .where(NewsItem.id == news_id)
            .with_for_update(skip_locked=True)
        )
        return await self.session.scalar(statement)

    async def list_filtered(
        self,
        *,
        source_id: uuid.UUID | None = None,
        status: NewsStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NewsItem]:
        """Вернуть новости с опциональными фильтрами."""

        statement = select(NewsItem).limit(limit).offset(offset)
        if source_id is not None:
            statement = statement.where(NewsItem.source_id == source_id)
        if status is not None:
            statement = statement.where(NewsItem.status == status)
        result = await self.session.scalars(statement)
        return list(result)

    async def list_by_status(self, status: NewsStatus, *, limit: int = 100) -> list[NewsItem]:
        """Вернуть новости с указанным статусом."""

        result = await self.session.scalars(
            select(NewsItem).where(NewsItem.status == status).limit(limit)
        )
        return list(result)

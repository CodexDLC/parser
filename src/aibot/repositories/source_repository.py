"""Repository для чтения и изменения источников новостей."""

import uuid

from sqlalchemy import select

from aibot.models.enums import SourceType
from aibot.models.source import Source
from aibot.repositories.base_repository import BaseRepository


class SourceRepository(BaseRepository[Source]):
    """Repository для чтения и изменения источников новостей."""

    model = Source

    async def get_by_type_and_url(self, source_type: SourceType, url: str) -> Source | None:
        """Найти источник по типу и URL/username."""

        statement = select(Source).where(Source.type == source_type, Source.url == url)
        return await self.session.scalar(statement)

    async def get_for_update(self, source_id: uuid.UUID) -> Source | None:
        """Заблокировать Source для optimistic version check кабинета."""

        return await self.session.scalar(
            select(Source).where(Source.id == source_id).with_for_update()
        )

    async def list_enabled(self) -> list[Source]:
        """Вернуть все включенные источники."""

        result = await self.session.scalars(select(Source).where(Source.enabled.is_(True)))
        return list(result)

    async def list_filtered(
        self,
        *,
        enabled: bool | None = None,
        source_type: SourceType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Source]:
        """Вернуть источники с опциональной фильтрацией."""

        statement = select(Source).limit(limit).offset(offset)
        if enabled is not None:
            statement = statement.where(Source.enabled.is_(enabled))
        if source_type is not None:
            statement = statement.where(Source.type == source_type)
        result = await self.session.scalars(statement)
        return list(result)

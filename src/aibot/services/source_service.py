"""Бизнес-логика управления источниками новостей."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.models.enums import SourceType
from aibot.models.source import Source
from aibot.repositories.source_repository import SourceRepository
from aibot.services.exceptions import EntityAlreadyExistsError, EntityNotFoundError


class SourceService:
    """Бизнес-логика управления источниками новостей."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SourceRepository(session)

    async def list_sources(
        self,
        *,
        enabled: bool | None = None,
        source_type: SourceType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Source]:
        """Вернуть список источников с фильтрами."""

        return await self.repository.list_filtered(
            enabled=enabled,
            source_type=source_type,
            limit=limit,
            offset=offset,
        )

    async def get_source(self, source_id: uuid.UUID) -> Source:
        """Вернуть источник по ID или поднять ошибку."""

        source = await self.repository.get(source_id)
        if source is None:
            raise EntityNotFoundError("Source not found")
        return source

    async def create_source(
        self,
        *,
        source_type: SourceType,
        name: str,
        url: str,
        enabled: bool,
    ) -> Source:
        """Создать источник новостей."""

        existing = await self.repository.get_by_type_and_url(source_type, url)
        if existing is not None:
            raise EntityAlreadyExistsError("Source with this type and url already exists")

        source = Source(type=source_type, name=name, url=url, enabled=enabled)
        await self.repository.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def update_source(
        self,
        source_id: uuid.UUID,
        *,
        source_type: SourceType | None = None,
        name: str | None = None,
        url: str | None = None,
        enabled: bool | None = None,
    ) -> Source:
        """Частично обновить источник новостей."""

        source = await self.get_source(source_id)
        next_type = source_type if source_type is not None else source.type
        next_url = url if url is not None else source.url

        duplicate = await self.repository.get_by_type_and_url(next_type, next_url)
        if duplicate is not None and duplicate.id != source.id:
            raise EntityAlreadyExistsError("Source with this type and url already exists")

        if source_type is not None:
            source.type = source_type
        if name is not None:
            source.name = name
        if url is not None:
            source.url = url
        if enabled is not None:
            source.enabled = enabled

        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def disable_source(self, source_id: uuid.UUID) -> Source:
        """Мягко удалить источник через enabled=false."""

        source = await self.get_source(source_id)
        source.enabled = False
        await self.session.commit()
        await self.session.refresh(source)
        return source

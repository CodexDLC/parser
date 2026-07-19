"""Базовый repository с общими CRUD-операциями SQLAlchemy."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from aibot.db.base import Base


class BaseRepository[ModelT: Base]:
    """Общий repository для простых операций с одной ORM-моделью."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def select_all(self) -> Select[tuple[ModelT]]:
        """Собрать запрос на выборку всех записей модели."""

        return select(self.model)

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        """Получить запись по UUID primary key."""

        return await self.session.get(self.model, entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """Вернуть страницу записей модели."""

        result = await self.session.scalars(self.select_all().limit(limit).offset(offset))
        return list(result)

    async def add(self, entity: ModelT) -> ModelT:
        """Добавить ORM-объект в текущую session."""

        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Удалить ORM-объект из текущей session."""

        await self.session.delete(entity)

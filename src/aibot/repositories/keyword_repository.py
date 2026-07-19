"""Repository для чтения и изменения ключевых слов."""

import uuid

from sqlalchemy import func, select

from aibot.models.keyword import Keyword
from aibot.repositories.base_repository import BaseRepository


class KeywordRepository(BaseRepository[Keyword]):
    """Repository для чтения и изменения ключевых слов."""

    model = Keyword

    async def get_by_word(self, word: str) -> Keyword | None:
        """Найти ключевое слово без учета регистра."""

        statement = select(Keyword).where(func.lower(Keyword.word) == word.lower())
        return await self.session.scalar(statement)

    async def get_for_update(self, keyword_id: uuid.UUID) -> Keyword | None:
        """Заблокировать Keyword для optimistic version check кабинета."""

        return await self.session.scalar(
            select(Keyword).where(Keyword.id == keyword_id).with_for_update()
        )

    async def list_enabled(self) -> list[Keyword]:
        """Вернуть все включенные ключевые слова."""

        result = await self.session.scalars(select(Keyword).where(Keyword.enabled.is_(True)))
        return list(result)

    async def list_filtered(
        self,
        *,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Keyword]:
        """Вернуть ключевые слова с опциональной фильтрацией."""

        statement = select(Keyword).limit(limit).offset(offset)
        if enabled is not None:
            statement = statement.where(Keyword.enabled.is_(enabled))
        result = await self.session.scalars(statement)
        return list(result)

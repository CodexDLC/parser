"""Бизнес-логика управления ключевыми словами."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.models.keyword import Keyword
from aibot.repositories.keyword_repository import KeywordRepository
from aibot.services.exceptions import EntityAlreadyExistsError, EntityNotFoundError


class KeywordService:
    """Бизнес-логика управления ключевыми словами."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = KeywordRepository(session)

    async def list_keywords(
        self,
        *,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Keyword]:
        """Вернуть список ключевых слов."""

        return await self.repository.list_filtered(enabled=enabled, limit=limit, offset=offset)

    async def get_keyword(self, keyword_id: uuid.UUID) -> Keyword:
        """Вернуть ключевое слово по ID или поднять ошибку."""

        keyword = await self.repository.get(keyword_id)
        if keyword is None:
            raise EntityNotFoundError("Keyword not found")
        return keyword

    async def create_keyword(self, *, word: str, enabled: bool) -> Keyword:
        """Создать ключевое слово."""

        existing = await self.repository.get_by_word(word)
        if existing is not None:
            raise EntityAlreadyExistsError("Keyword already exists")

        keyword = Keyword(word=word, enabled=enabled)
        await self.repository.add(keyword)
        await self.session.commit()
        await self.session.refresh(keyword)
        return keyword

    async def update_keyword(
        self,
        keyword_id: uuid.UUID,
        *,
        word: str | None = None,
        enabled: bool | None = None,
    ) -> Keyword:
        """Частично обновить ключевое слово."""

        keyword = await self.get_keyword(keyword_id)
        if word is not None:
            duplicate = await self.repository.get_by_word(word)
            if duplicate is not None and duplicate.id != keyword.id:
                raise EntityAlreadyExistsError("Keyword already exists")
            keyword.word = word
        if enabled is not None:
            keyword.enabled = enabled

        await self.session.commit()
        await self.session.refresh(keyword)
        return keyword

    async def delete_keyword(self, keyword_id: uuid.UUID) -> None:
        """Удалить ключевое слово."""

        keyword = await self.get_keyword(keyword_id)
        await self.repository.delete(keyword)
        await self.session.commit()

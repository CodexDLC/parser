"""Repository для чтения и изменения AI-сгенерированных постов."""

import uuid

from sqlalchemy import select

from aibot.models.enums import PostStatus
from aibot.models.post import Post
from aibot.repositories.base_repository import BaseRepository


class PostRepository(BaseRepository[Post]):
    """Repository для чтения и изменения AI-сгенерированных постов."""

    model = Post

    async def list_filtered(
        self,
        *,
        status: PostStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Post]:
        """Вернуть посты с опциональным фильтром по статусу."""

        statement = select(Post).limit(limit).offset(offset)
        if status is not None:
            statement = statement.where(Post.status == status)
        result = await self.session.scalars(statement)
        return list(result)

    async def list_by_status(self, status: PostStatus, *, limit: int = 100) -> list[Post]:
        """Вернуть посты с указанным статусом."""

        result = await self.session.scalars(select(Post).where(Post.status == status).limit(limit))
        return list(result)

    async def get_published_for_news(self, news_id: uuid.UUID) -> Post | None:
        """Найти опубликованный пост для новости."""

        statement = select(Post).where(
            Post.news_id == news_id,
            Post.status == PostStatus.PUBLISHED,
        )
        return await self.session.scalar(statement)

    async def get_for_publication(self, post_id: uuid.UUID) -> Post | None:
        """Получить Post с row lock или None, если lock уже занят."""

        return await self.session.scalar(
            select(Post)
            .where(Post.id == post_id)
            .with_for_update(skip_locked=True)
        )

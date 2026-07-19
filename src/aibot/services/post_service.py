"""Бизнес-логика управления жизненным циклом постов."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.models.enums import PostStatus
from aibot.models.post import Post
from aibot.repositories.post_repository import PostRepository
from aibot.services.exceptions import EntityNotFoundError


class PostService:
    """Бизнес-логика просмотра и публикации постов."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = PostRepository(session)

    async def list_posts(
        self,
        *,
        status: PostStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Post]:
        """Вернуть список постов."""

        return await self.repository.list_filtered(status=status, limit=limit, offset=offset)

    async def get_post(self, post_id: uuid.UUID) -> Post:
        """Вернуть пост по ID или поднять ошибку."""

        post = await self.repository.get(post_id)
        if post is None:
            raise EntityNotFoundError("Post not found")
        return post

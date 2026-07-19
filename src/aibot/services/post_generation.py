"""Подготовка prompt и генерация текста Telegram-поста через AI."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.config import Settings, get_settings
from aibot.integrations.ai_client import AIClient
from aibot.models.enums import NewsStatus, PostStatus
from aibot.models.post import Post
from aibot.repositories.news_repository import NewsRepository
from aibot.repositories.post_repository import PostRepository
from aibot.services.exceptions import EntityNotFoundError, InvalidNewsStateError


class PostGenerationService:
    """Сервис ручной и фоновой генерации текста постов."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        settings: Settings | None = None,
        ai_client: AIClient | None = None,
        news_repository: NewsRepository | None = None,
        post_repository: PostRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.ai_client = ai_client or AIClient(self.settings)
        self.news_repository = news_repository or (
            NewsRepository(session) if session is not None else None
        )
        self.post_repository = post_repository or (
            PostRepository(session) if session is not None else None
        )

    async def generate_manual_post(self, text: str) -> str:
        """Сгенерировать пост из произвольного текста."""

        return await self.ai_client.generate_telegram_post(text)

    async def generate_post_from_news(self, news_id: uuid.UUID) -> Post:
        """Сгенерировать и сохранить Post для новости, готовой к генерации."""

        if self.session is None or self.news_repository is None or self.post_repository is None:
            raise RuntimeError("Database session is required to generate a post from news")

        news_item = await self.news_repository.get(news_id)
        if news_item is None:
            raise EntityNotFoundError("News item not found")
        if news_item.status != NewsStatus.READY_FOR_GENERATION:
            raise InvalidNewsStateError("Only ready_for_generation news can be generated")

        generated_text = await self.generate_manual_post(news_item.text_for_generation)
        post = await self.post_repository.add(
            Post(
                news_id=news_item.id,
                generated_text=generated_text,
                status=PostStatus.GENERATED,
            )
        )
        news_item.status = NewsStatus.GENERATED
        await self.session.commit()
        await self.session.refresh(post)
        return post

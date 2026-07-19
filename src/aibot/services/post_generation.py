"""Подготовка prompt и генерация текста Telegram-поста через AI."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.config import Settings, get_settings
from aibot.integrations.ai_client import AIClient, AIClientError
from aibot.models.enums import ErrorScope, NewsStatus, PostStatus
from aibot.models.error_log import ErrorLog
from aibot.models.news_item import NewsItem
from aibot.models.post import Post
from aibot.ports.ai import AIClientPort
from aibot.repositories.error_log_repository import ErrorLogRepository
from aibot.repositories.news_repository import NewsRepository
from aibot.repositories.post_repository import PostRepository
from aibot.services.exceptions import (
    ConcurrentGenerationError,
    EntityNotFoundError,
    InvalidNewsStateError,
)
from aibot.services.telegram_post_composer import TelegramPostComposer


class PostGenerationService:
    """Сервис ручной и фоновой генерации текста постов."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        settings: Settings | None = None,
        ai_client: AIClientPort | None = None,
        news_repository: NewsRepository | None = None,
        post_repository: PostRepository | None = None,
        error_log_repository: ErrorLogRepository | None = None,
        post_composer: TelegramPostComposer | None = None,
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
        self.error_log_repository = error_log_repository or (
            ErrorLogRepository(session) if session is not None else None
        )
        self.post_composer = post_composer or TelegramPostComposer()

    async def generate_manual_post(
        self,
        text: str,
        *,
        news_id: uuid.UUID | None = None,
    ) -> str:
        """Сгенерировать пост из произвольного текста."""

        try:
            return await self.ai_client.generate_telegram_post(text)
        except AIClientError as exc:
            await self._log_ai_failure(exc, news_id=news_id)
            raise

    async def generate_post_from_news(self, news_id: uuid.UUID) -> Post:
        """Сгенерировать и сохранить Post для новости, готовой к генерации."""

        if self.session is None or self.post_repository is None:
            raise RuntimeError("Database session is required to generate a post from news")

        news_item = await self._get_locked_generation_candidate(news_id)
        generated_body = await self.generate_manual_post(
            news_item.text_for_generation,
            news_id=news_item.id,
        )
        generated_text = self.post_composer.compose(
            generated_body,
            source_url=news_item.url,
        )
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

    async def get_generation_candidate(self, news_id: uuid.UUID) -> NewsItem:
        """Быстро проверить существование и статус новости до постановки задачи."""

        if self.news_repository is None:
            raise RuntimeError("Database session is required to validate news generation")

        news_item = await self.news_repository.get(news_id)
        return self._validate_generation_candidate(news_item)

    async def _get_locked_generation_candidate(self, news_id: uuid.UUID) -> NewsItem:
        """Захватить row lock и отличить занятый lock от неверного состояния."""

        if self.news_repository is None:
            raise RuntimeError("Database session is required to generate a post from news")

        news_item = await self.news_repository.get_for_generation(news_id)
        if news_item is not None:
            return self._validate_generation_candidate(news_item)

        current_news_item = await self.news_repository.get(news_id)
        if current_news_item is None:
            raise EntityNotFoundError("News item not found")
        if current_news_item.status != NewsStatus.READY_FOR_GENERATION:
            raise InvalidNewsStateError("Only ready_for_generation news can be generated")
        raise ConcurrentGenerationError("Post generation is already in progress")

    @staticmethod
    def _validate_generation_candidate(news_item: NewsItem | None) -> NewsItem:
        """Проверить существование и статус news независимо от способа чтения."""

        if news_item is None:
            raise EntityNotFoundError("News item not found")
        if news_item.status != NewsStatus.READY_FOR_GENERATION:
            raise InvalidNewsStateError("Only ready_for_generation news can be generated")
        return news_item

    async def _log_ai_failure(
        self,
        exc: AIClientError,
        *,
        news_id: uuid.UUID | None,
    ) -> None:
        """Сохранить безопасный AI ErrorLog, если сервис работает с БД."""

        if self.session is None or self.error_log_repository is None:
            return
        await self.error_log_repository.add(
            ErrorLog(
                scope=ErrorScope.AI,
                message="AI generation failed",
                details=exc.__class__.__name__,
                news_id=news_id,
            )
        )
        await self.session.commit()

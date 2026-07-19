"""Проверка и публикация готовых постов в Telegram."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from aibot.config import Settings, get_settings
from aibot.integrations.telegram_client import TelegramClient
from aibot.models.enums import ErrorScope, PostStatus
from aibot.models.error_log import ErrorLog
from aibot.models.post import Post
from aibot.repositories.error_log_repository import ErrorLogRepository
from aibot.repositories.post_repository import PostRepository
from aibot.services.exceptions import (
    EntityNotFoundError,
    InvalidPostStateError,
    PublishingFailedError,
)


@dataclass(frozen=True)
class PublishResult:
    """Результат dry-run или реальной публикации поста."""

    post_id: uuid.UUID
    status: PostStatus
    telegram_message_id: str
    dry_run: bool


class PublishingService:
    """Сервис проверки и публикации готовых постов."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        repository: PostRepository | None = None,
        error_log_repository: ErrorLogRepository | None = None,
        telegram_client: TelegramClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = repository or PostRepository(session)
        self.error_log_repository = error_log_repository or ErrorLogRepository(session)
        self.telegram_client = telegram_client or TelegramClient(self.settings)

    async def publish_post(self, post_id: uuid.UUID) -> PublishResult:
        """Опубликовать пост или выполнить dry-run публикацию."""

        post = await self.repository.get(post_id)
        if post is None:
            raise EntityNotFoundError("Post not found")
        self._ensure_publishable(post)

        post.status = PostStatus.PUBLISHING
        await self.session.flush()

        try:
            message_id = await self.telegram_client.publish_message(post.generated_text)
        except Exception as exc:
            await self._mark_failed(post, exc)
            raise PublishingFailedError("Telegram publication failed") from exc

        post.status = PostStatus.PUBLISHED
        post.telegram_message_id = message_id
        post.published_at = datetime.now(tz=UTC)
        await self.session.commit()
        await self.session.refresh(post)

        return PublishResult(
            post_id=post.id,
            status=post.status,
            telegram_message_id=message_id,
            dry_run=self.settings.telegram_dry_run,
        )

    def _ensure_publishable(self, post: Post) -> None:
        """Проверить, что пост можно публиковать."""

        if post.status == PostStatus.PUBLISHED:
            raise InvalidPostStateError("Post is already published")
        if post.status != PostStatus.GENERATED:
            raise InvalidPostStateError("Only generated posts can be published")
        if not post.generated_text.strip():
            raise InvalidPostStateError("Post generated_text is empty")

    async def _mark_failed(self, post: Post, exc: Exception) -> None:
        """Зафиксировать ошибку публикации в Post и ErrorLog."""

        message = str(exc) or exc.__class__.__name__
        post.status = PostStatus.FAILED
        post.error_message = message
        await self.error_log_repository.add(
            ErrorLog(
                scope=ErrorScope.TELEGRAM,
                message="Telegram publication failed",
                details=message,
                post_id=post.id,
            )
        )
        await self.session.commit()
        await self.session.refresh(post)

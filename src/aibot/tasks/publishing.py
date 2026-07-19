"""Celery-задачи для публикации постов в Telegram."""

import asyncio
import uuid

from aibot.db.session import AsyncSessionFactory
from aibot.services.publishing import PublishingService
from aibot.tasks.celery_app import celery_app


@celery_app.task(name="aibot.tasks.publishing.publish_post")
def publish_post(post_id: str) -> dict[str, object]:
    """Запустить dry-run или реальную публикацию поста."""

    return asyncio.run(_publish_post(uuid.UUID(post_id)))


async def _publish_post(post_id: uuid.UUID) -> dict[str, object]:
    """Async-реализация задачи публикации поста."""

    async with AsyncSessionFactory() as session:
        result = await PublishingService(session).publish_post(post_id)
        return {
            "post_id": str(result.post_id),
            "status": result.status.value,
            "telegram_message_id": result.telegram_message_id,
            "dry_run": result.dry_run,
        }

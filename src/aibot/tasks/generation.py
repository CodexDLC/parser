"""Celery-задачи для AI-генерации постов."""

import asyncio
import uuid

from aibot.db.session import AsyncSessionFactory
from aibot.integrations.ai_client import (
    AIClientRateLimitError,
    AIClientTimeoutError,
)
from aibot.services.post_generation import PostGenerationService
from aibot.tasks.base import LoggedTask
from aibot.tasks.celery_app import celery_app

AI_RETRY_ERRORS = (AIClientRateLimitError, AIClientTimeoutError)


@celery_app.task(
    base=LoggedTask,
    name="aibot.tasks.generation.generate_text",
    autoretry_for=AI_RETRY_ERRORS,
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def generate_text(text: str) -> dict[str, object]:
    """Сгенерировать текст поста через AI generation service."""

    return asyncio.run(_generate_text(text))


@celery_app.task(
    base=LoggedTask,
    name="aibot.tasks.generation.generate_post",
    autoretry_for=AI_RETRY_ERRORS,
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def generate_post(
    news_id: str,
    pipeline_run_id: str | None = None,
) -> dict[str, object]:
    """Сгенерировать и сохранить Post для новости."""

    del pipeline_run_id
    return asyncio.run(_generate_post(uuid.UUID(news_id)))


async def _generate_text(text: str) -> dict[str, object]:
    """Async-реализация генерации текста."""

    async with AsyncSessionFactory() as session:
        service = PostGenerationService(session)
        generated_text = await service.generate_manual_post(text)
        return {"generated_text": generated_text}


async def _generate_post(news_id: uuid.UUID) -> dict[str, object]:
    """Async-реализация генерации Post из NewsItem."""

    async with AsyncSessionFactory() as session:
        service = PostGenerationService(session)
        post = await service.generate_post_from_news(news_id)
        return {
            "post_id": str(post.id),
            "news_id": str(post.news_id),
            "status": post.status.value,
        }

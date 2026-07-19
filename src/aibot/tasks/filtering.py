"""Celery-задачи для фильтрации уже сохраненных новостей."""

import asyncio
import uuid

from aibot.db.session import AsyncSessionFactory
from aibot.services.news_filtering import SavedNewsFilteringService
from aibot.tasks.base import LoggedTask
from aibot.tasks.celery_app import celery_app


@celery_app.task(base=LoggedTask, name="aibot.tasks.filtering.filter_news")
def filter_news(news_id: str) -> dict[str, object]:
    """Отфильтровать сохраненную новость по текущим ключевым словам."""

    return asyncio.run(_filter_news(uuid.UUID(news_id)))


async def _filter_news(news_id: uuid.UUID) -> dict[str, object]:
    """Async-реализация задачи фильтрации одной новости."""

    async with AsyncSessionFactory() as session:
        result = await SavedNewsFilteringService(session).filter_news(news_id)
        return {
            "news_id": str(result.news_id),
            "status": result.status.value,
            "reason": result.reason,
            "matched_keywords": result.matched_keywords,
            "detected_language": result.detected_language,
        }

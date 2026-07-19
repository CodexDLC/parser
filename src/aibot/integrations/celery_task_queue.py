"""Celery adapter для application task queue port."""

import uuid
from typing import Any

from aibot.tasks.generation import generate_post, generate_text
from aibot.tasks.parsing import parse_source
from aibot.tasks.publishing import publish_post


class CeleryTaskQueue:
    """Поставить тяжёлую операцию в Celery и вернуть её идентификатор."""

    def enqueue_source_parsing(self, source_id: uuid.UUID, *, limit: int) -> str:
        """Поставить парсинг источника."""

        return self._task_id(parse_source.delay(str(source_id), limit=limit))

    def enqueue_news_generation(self, news_id: uuid.UUID) -> str:
        """Поставить генерацию поста по новости."""

        return self._task_id(generate_post.delay(str(news_id)))

    def enqueue_post_publication(self, post_id: uuid.UUID) -> str:
        """Поставить публикацию поста."""

        return self._task_id(publish_post.delay(str(post_id)))

    def enqueue_manual_generation(self, text: str) -> str:
        """Поставить ручную генерацию текста."""

        return self._task_id(generate_text.delay(text))

    @staticmethod
    def _task_id(async_result: Any) -> str:
        """Извлечь стабильный строковый Celery task ID."""

        return str(async_result.id)

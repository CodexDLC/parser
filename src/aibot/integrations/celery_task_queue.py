"""Celery adapter для application task queue port."""

import uuid
from typing import Any

from aibot.tasks.generation import generate_post, generate_text
from aibot.tasks.parsing import parse_source
from aibot.tasks.pipeline import run_pipeline
from aibot.tasks.publishing import publish_post


class CeleryTaskQueue:
    """Поставить тяжёлую операцию в Celery и вернуть её идентификатор."""

    def enqueue_source_parsing(
        self,
        source_id: uuid.UUID,
        *,
        limit: int,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить парсинг источника."""

        kwargs: dict[str, object] = {"limit": limit}
        if pipeline_run_id is not None:
            kwargs["pipeline_run_id"] = str(pipeline_run_id)
        return self._task_id(parse_source.delay(str(source_id), **kwargs))

    def enqueue_news_generation(
        self,
        news_id: uuid.UUID,
        *,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить генерацию поста по новости."""

        kwargs = {}
        if pipeline_run_id is not None:
            kwargs["pipeline_run_id"] = str(pipeline_run_id)
        return self._task_id(generate_post.delay(str(news_id), **kwargs))

    def enqueue_post_publication(
        self,
        post_id: uuid.UUID,
        *,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить публикацию поста."""

        kwargs = {}
        if pipeline_run_id is not None:
            kwargs["pipeline_run_id"] = str(pipeline_run_id)
        return self._task_id(publish_post.delay(str(post_id), **kwargs))

    def enqueue_manual_generation(self, text: str) -> str:
        """Поставить ручную генерацию текста."""

        return self._task_id(generate_text.delay(text))

    def enqueue_full_pipeline(
        self,
        *,
        parse_limit: int,
        generation_limit: int,
        publishing_limit: int,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить полный pipeline."""

        kwargs: dict[str, object] = {
            "parse_limit": parse_limit,
            "generation_limit": generation_limit,
            "publishing_limit": publishing_limit,
        }
        if pipeline_run_id is not None:
            kwargs["pipeline_run_id"] = str(pipeline_run_id)
        return self._task_id(run_pipeline.delay(**kwargs))

    @staticmethod
    def _task_id(async_result: Any) -> str:
        """Извлечь стабильный строковый Celery task ID."""

        return str(async_result.id)

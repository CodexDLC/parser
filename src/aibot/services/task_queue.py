"""Application port для постановки тяжёлых операций в очередь."""

import uuid
from typing import Protocol


class TaskQueue(Protocol):
    """Порт фоновой очереди, используемый HTTP adapter-ом."""

    def enqueue_source_parsing(
        self,
        source_id: uuid.UUID,
        *,
        limit: int,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить парсинг одного источника и вернуть task ID."""

    def enqueue_news_generation(
        self,
        news_id: uuid.UUID,
        *,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить генерацию поста по новости и вернуть task ID."""

    def enqueue_post_publication(
        self,
        post_id: uuid.UUID,
        *,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить публикацию поста и вернуть task ID."""

    def enqueue_manual_generation(self, text: str) -> str:
        """Поставить генерацию произвольного текста и вернуть task ID."""

    def enqueue_full_pipeline(
        self,
        *,
        parse_limit: int,
        generation_limit: int,
        publishing_limit: int,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> str:
        """Поставить полный pipeline и вернуть task ID."""

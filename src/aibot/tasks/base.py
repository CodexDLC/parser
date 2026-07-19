"""Общий Celery Task base с безопасным ErrorLog финальных сбоев."""

import asyncio
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from celery import Task

from aibot.db.session import AsyncSessionFactory
from aibot.services.celery_failure_logging import CeleryFailureLoggingService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskFailureContext:
    """Связанные entity IDs, извлечённые из JSON-аргументов task."""

    source_id: uuid.UUID | None = None
    news_id: uuid.UUID | None = None
    post_id: uuid.UUID | None = None


class LoggedTask(Task):
    """Celery Task, записывающая окончательный failure в PostgreSQL."""

    abstract = True

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
        einfo: Any,
    ) -> None:
        """Записать безопасный ErrorLog, не подменяя исходную task-ошибку."""

        task_name = self.name or self.__class__.__name__
        context = self.failure_context(task_name, args, kwargs)
        try:
            asyncio.run(self._record_failure(task_name, exc, context))
        except Exception:
            logger.exception("Could not persist Celery task failure")
        super().on_failure(exc, task_id, args, kwargs, einfo)

    async def _record_failure(
        self,
        task_name: str,
        exc: BaseException,
        context: TaskFailureContext,
    ) -> None:
        """Открыть отдельную session для failure hook."""

        async with AsyncSessionFactory() as session:
            await CeleryFailureLoggingService(session).record_failure(
                task_name=task_name,
                exc=exc,
                source_id=context.source_id,
                news_id=context.news_id,
                post_id=context.post_id,
            )

    @classmethod
    def failure_context(
        cls,
        task_name: str,
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
    ) -> TaskFailureContext:
        """Безопасно извлечь UUID связанной сущности по имени task."""

        if task_name == "aibot.tasks.parsing.parse_source":
            return TaskFailureContext(
                source_id=cls._uuid_argument(args, kwargs, "source_id")
            )
        if task_name in {
            "aibot.tasks.filtering.filter_news",
            "aibot.tasks.generation.generate_post",
        }:
            return TaskFailureContext(
                news_id=cls._uuid_argument(args, kwargs, "news_id")
            )
        if task_name == "aibot.tasks.publishing.publish_post":
            return TaskFailureContext(
                post_id=cls._uuid_argument(args, kwargs, "post_id")
            )
        return TaskFailureContext()

    @staticmethod
    def _uuid_argument(
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
        name: str,
    ) -> uuid.UUID | None:
        raw_value = kwargs.get(name)
        if raw_value is None and args:
            raw_value = args[0]
        try:
            return uuid.UUID(str(raw_value))
        except (TypeError, ValueError, AttributeError):
            return None

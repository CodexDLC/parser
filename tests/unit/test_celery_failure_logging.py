"""Тесты безопасного ErrorLog для финальных сбоев Celery."""

import uuid

import pytest

from aibot.models.enums import ErrorScope
from aibot.models.error_log import ErrorLog
from aibot.services.celery_failure_logging import CeleryFailureLoggingService
from aibot.tasks.base import LoggedTask, TaskFailureContext
from aibot.tasks.filtering import filter_news
from aibot.tasks.generation import generate_post, generate_text
from aibot.tasks.parsing import parse_enabled_sources, parse_source
from aibot.tasks.pipeline import run_pipeline
from aibot.tasks.publishing import publish_post


class FakeErrorLogRepository:
    """Fake ErrorLog repository."""

    def __init__(self) -> None:
        self.saved: list[ErrorLog] = []

    async def add(self, error_log: ErrorLog) -> ErrorLog:
        self.saved.append(error_log)
        return error_log


class FakeSession:
    """Fake session with commit counter."""

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_celery_failure_logger_stores_safe_context() -> None:
    """Celery ErrorLog содержит task name и тип ошибки, но не secret message."""

    news_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    session = FakeSession()
    repository = FakeErrorLogRepository()
    service = CeleryFailureLoggingService(
        session,  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
    )

    await service.record_failure(
        task_name="aibot.tasks.generation.generate_post",
        exc=RuntimeError("token=super-secret"),
        news_id=news_id,
    )

    assert session.commits == 1
    assert len(repository.saved) == 1
    error_log = repository.saved[0]
    assert error_log.scope == ErrorScope.CELERY
    assert error_log.news_id == news_id
    assert error_log.message == "Celery task failed: aibot.tasks.generation.generate_post"
    assert error_log.details == "RuntimeError"
    assert "secret" not in error_log.details


def test_all_background_tasks_use_logged_task_base() -> None:
    """Финальный сбой каждой project task проходит общий failure hook."""

    tasks = [
        parse_source,
        parse_enabled_sources,
        filter_news,
        generate_text,
        generate_post,
        publish_post,
        run_pipeline,
    ]

    assert all(isinstance(task, LoggedTask) for task in tasks)


def test_logged_task_extracts_related_entity_ids() -> None:
    """Task base связывает ErrorLog с source/news/post по JSON-аргументу."""

    source_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    news_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    post_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

    assert LoggedTask.failure_context(
        "aibot.tasks.parsing.parse_source",
        (str(source_id),),
        {},
    ).source_id == source_id
    assert LoggedTask.failure_context(
        "aibot.tasks.generation.generate_post",
        (),
        {"news_id": str(news_id)},
    ).news_id == news_id
    assert LoggedTask.failure_context(
        "aibot.tasks.publishing.publish_post",
        (str(post_id),),
        {},
    ).post_id == post_id


def test_logged_task_on_failure_invokes_async_logger() -> None:
    """Celery on_failure действительно вызывает persistence hook."""

    captured: list[tuple[str, str, TaskFailureContext]] = []

    class RecordingTask(LoggedTask):
        abstract = False
        name = "aibot.tasks.generation.generate_post"

        async def _record_failure(
            self,
            task_name: str,
            exc: BaseException,
            context: TaskFailureContext,
        ) -> None:
            captured.append((task_name, exc.__class__.__name__, context))

    news_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    RecordingTask().on_failure(
        RuntimeError("secret"),
        "task-id",
        (str(news_id),),
        {},
        None,
    )

    assert captured == [
        (
            "aibot.tasks.generation.generate_post",
            "RuntimeError",
            TaskFailureContext(news_id=news_id),
        )
    ]

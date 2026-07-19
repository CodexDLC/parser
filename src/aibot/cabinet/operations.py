"""Idempotent orchestration cabinet → Celery → PipelineRun."""

import uuid
from collections.abc import Awaitable
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aibot.models.enums import (
    AdminAuditOutcome,
    PipelineInitiator,
    PipelineOperation,
)
from aibot.models.pipeline_run import PipelineRun
from aibot.repositories.admin_audit_log_repository import AdminAuditLogRepository
from aibot.repositories.pipeline_run_repository import PipelineRunRepository
from aibot.services.admin_audit import AdminAuditService
from aibot.services.pipeline_run_service import PipelineRunService
from aibot.services.post_generation import PostGenerationService
from aibot.services.publishing import PublishingService
from aibot.services.source_service import SourceService
from aibot.services.task_queue import TaskQueue


class PipelineRunStore(Protocol):
    async def create_queued(
        self,
        *,
        initiator: PipelineInitiator,
        operation: PipelineOperation,
        idempotency_key: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        parameters: dict[str, object] | None = None,
    ) -> tuple[PipelineRun, bool]: ...

    async def attach_task(self, run_id: uuid.UUID, task_id: str) -> None: ...
    async def mark_failed(self, run_id: uuid.UUID, category: str) -> None: ...


class OperationValidator(Protocol):
    async def validate_source(self, source_id: uuid.UUID) -> None: ...
    async def validate_news(self, news_id: uuid.UUID) -> None: ...
    async def validate_post(self, post_id: uuid.UUID) -> None: ...


class OperationAudit(Protocol):
    async def record(
        self,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        outcome: str,
        detail: str | None = None,
    ) -> None: ...


class CabinetOperationPort(Protocol):
    async def enqueue_source_parse(
        self,
        *,
        actor: str,
        source_id: uuid.UUID,
        limit: int,
        idempotency_key: str,
    ) -> PipelineRun: ...

    async def enqueue_news_generation(
        self,
        *,
        actor: str,
        news_id: uuid.UUID,
        idempotency_key: str,
    ) -> PipelineRun: ...

    async def enqueue_post_publication(
        self,
        *,
        actor: str,
        post_id: uuid.UUID,
        idempotency_key: str,
    ) -> PipelineRun: ...

    async def enqueue_full_pipeline(
        self,
        *,
        actor: str,
        parse_limit: int,
        generation_limit: int,
        publishing_limit: int,
        idempotency_key: str,
    ) -> PipelineRun: ...


class CabinetOperationService:
    """Валидировать entity, создать run и ровно один раз вызвать queue adapter."""

    def __init__(
        self,
        *,
        run_store: PipelineRunStore,
        validator: OperationValidator,
        task_queue: TaskQueue,
        audit: OperationAudit,
    ) -> None:
        self._run_store = run_store
        self._validator = validator
        self._task_queue = task_queue
        self._audit = audit

    async def enqueue_source_parse(
        self,
        *,
        actor: str,
        source_id: uuid.UUID,
        limit: int,
        idempotency_key: str,
    ) -> PipelineRun:
        await self._validate(
            self._validator.validate_source(source_id),
            actor=actor,
            action="source.parse",
            entity_type="source",
            entity_id=source_id,
        )
        run, created = await self._run_store.create_queued(
            initiator=PipelineInitiator.CABINET,
            operation=PipelineOperation.PARSE_SOURCE,
            idempotency_key=_key(idempotency_key),
            entity_type="source",
            entity_id=source_id,
            parameters={"limit": limit},
        )
        if not created:
            return run
        try:
            task_id = self._task_queue.enqueue_source_parsing(
                source_id,
                limit=limit,
                pipeline_run_id=run.id,
            )
            await self._run_store.attach_task(run.id, task_id)
        except Exception as exc:
            await self._dispatch_failed(run.id, actor, "source.parse", "source", source_id, exc)
            raise
        await self._audit.record(
            actor=actor,
            action="source.parse",
            entity_type="source",
            entity_id=source_id,
            outcome=AdminAuditOutcome.SUCCEEDED.value,
        )
        return run

    async def enqueue_news_generation(
        self,
        *,
        actor: str,
        news_id: uuid.UUID,
        idempotency_key: str,
    ) -> PipelineRun:
        await self._validate(
            self._validator.validate_news(news_id),
            actor=actor,
            action="news.generate",
            entity_type="news",
            entity_id=news_id,
        )
        run, created = await self._run_store.create_queued(
            initiator=PipelineInitiator.CABINET,
            operation=PipelineOperation.GENERATE_NEWS,
            idempotency_key=_key(idempotency_key),
            entity_type="news",
            entity_id=news_id,
        )
        if not created:
            return run
        try:
            task_id = self._task_queue.enqueue_news_generation(
                news_id,
                pipeline_run_id=run.id,
            )
            await self._run_store.attach_task(run.id, task_id)
        except Exception as exc:
            await self._dispatch_failed(
                run.id,
                actor,
                "news.generate",
                "news",
                news_id,
                exc,
            )
            raise
        await self._audit.record(
            actor=actor,
            action="news.generate",
            entity_type="news",
            entity_id=news_id,
            outcome=AdminAuditOutcome.SUCCEEDED.value,
        )
        return run

    async def enqueue_post_publication(
        self,
        *,
        actor: str,
        post_id: uuid.UUID,
        idempotency_key: str,
    ) -> PipelineRun:
        await self._validate(
            self._validator.validate_post(post_id),
            actor=actor,
            action="post.publish",
            entity_type="post",
            entity_id=post_id,
        )
        run, created = await self._run_store.create_queued(
            initiator=PipelineInitiator.CABINET,
            operation=PipelineOperation.PUBLISH_POST,
            idempotency_key=_key(idempotency_key),
            entity_type="post",
            entity_id=post_id,
        )
        if not created:
            return run
        try:
            task_id = self._task_queue.enqueue_post_publication(
                post_id,
                pipeline_run_id=run.id,
            )
            await self._run_store.attach_task(run.id, task_id)
        except Exception as exc:
            await self._dispatch_failed(
                run.id,
                actor,
                "post.publish",
                "post",
                post_id,
                exc,
            )
            raise
        await self._audit.record(
            actor=actor,
            action="post.publish",
            entity_type="post",
            entity_id=post_id,
            outcome=AdminAuditOutcome.SUCCEEDED.value,
        )
        return run

    async def enqueue_full_pipeline(
        self,
        *,
        actor: str,
        parse_limit: int,
        generation_limit: int,
        publishing_limit: int,
        idempotency_key: str,
    ) -> PipelineRun:
        run, created = await self._run_store.create_queued(
            initiator=PipelineInitiator.CABINET,
            operation=PipelineOperation.RUN_PIPELINE,
            idempotency_key=_key(idempotency_key),
            parameters={
                "parse_limit": parse_limit,
                "generation_limit": generation_limit,
                "publishing_limit": publishing_limit,
            },
        )
        if not created:
            return run
        try:
            task_id = self._task_queue.enqueue_full_pipeline(
                parse_limit=parse_limit,
                generation_limit=generation_limit,
                publishing_limit=publishing_limit,
                pipeline_run_id=run.id,
            )
            await self._run_store.attach_task(run.id, task_id)
        except Exception as exc:
            await self._dispatch_failed(
                run.id,
                actor,
                "pipeline.run",
                "pipeline",
                None,
                exc,
            )
            raise
        await self._audit.record(
            actor=actor,
            action="pipeline.run",
            entity_type="pipeline",
            entity_id=None,
            outcome=AdminAuditOutcome.SUCCEEDED.value,
        )
        return run

    async def _dispatch_failed(
        self,
        run_id: uuid.UUID,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        exc: Exception,
    ) -> None:
        category = exc.__class__.__name__
        await self._run_store.mark_failed(run_id, category)
        await self._audit.record(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            outcome=AdminAuditOutcome.FAILED.value,
            detail=category,
        )

    async def _validate(
        self,
        validation: Awaitable[None],
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> None:
        try:
            await validation
        except Exception as exc:
            await self._audit.record(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                outcome=AdminAuditOutcome.REJECTED.value,
                detail=exc.__class__.__name__,
            )
            raise


class SqlPipelineRunStore:
    """Session-per-call adapter для HTTP и Celery hooks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_queued(self, **values: object) -> tuple[PipelineRun, bool]:
        async with self._session_factory() as session:
            service = PipelineRunService(repository=PipelineRunRepository(session))
            try:
                return await service.create_queued(**values)  # type: ignore[arg-type]
            except IntegrityError:
                await session.rollback()
                existing = await PipelineRunRepository(session).get_by_idempotency_key(
                    str(values["idempotency_key"])
                )
                if existing is None:
                    raise
                return existing, False

    async def attach_task(self, run_id: uuid.UUID, task_id: str) -> None:
        async with self._session_factory() as session:
            await PipelineRunService(
                repository=PipelineRunRepository(session)
            ).attach_task(run_id, task_id=task_id)

    async def mark_failed(self, run_id: uuid.UUID, category: str) -> None:
        async with self._session_factory() as session:
            await PipelineRunService(
                repository=PipelineRunRepository(session)
            ).mark_failed(run_id, category=category)


class SqlOperationValidator:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def validate_source(self, source_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            await SourceService(session).get_source(source_id)

    async def validate_news(self, news_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            await PostGenerationService(session).get_generation_candidate(news_id)

    async def validate_post(self, post_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            await PublishingService(session).get_publishable_post(post_id)


class SqlOperationAudit:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(
        self,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            await AdminAuditService(AdminAuditLogRepository(session)).record(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                outcome=AdminAuditOutcome(outcome),
                detail=detail,
            )


def _key(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Idempotency key is required")
    return normalized[:128]

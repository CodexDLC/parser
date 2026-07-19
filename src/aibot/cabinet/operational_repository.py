"""PostgreSQL read adapter operational журналов."""

import uuid
from contextlib import suppress

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aibot.cabinet.entity_read import EntityPage
from aibot.cabinet.operational_read import AdminAuditView, PipelineRunView
from aibot.models.admin_audit_log import AdminAuditLog
from aibot.models.enums import (
    AdminAuditOutcome,
    PipelineOperation,
    PipelineRunStatus,
)
from aibot.models.pipeline_run import PipelineRun


class SqlAlchemyCabinetOperationalReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_pipeline_runs(
        self,
        *,
        offset: int,
        limit: int,
        status: str,
        operation: str,
    ) -> EntityPage[PipelineRunView]:
        statement = select(PipelineRun)
        with suppress(ValueError):
            statement = statement.where(PipelineRun.status == PipelineRunStatus(status))
        with suppress(ValueError):
            statement = statement.where(PipelineRun.operation == PipelineOperation(operation))
        async with self._session_factory() as session:
            total = int(
                (
                    await session.scalar(
                        select(func.count()).select_from(statement.order_by(None).subquery())
                    )
                )
                or 0
            )
            rows = list(
                await session.scalars(
                    statement.order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
        return EntityPage(tuple(_pipeline_view(row) for row in rows), total)

    async def get_pipeline_run(self, entity_id: uuid.UUID) -> PipelineRunView | None:
        async with self._session_factory() as session:
            row = await session.get(PipelineRun, entity_id)
        return None if row is None else _pipeline_view(row)

    async def list_audit_logs(
        self,
        *,
        offset: int,
        limit: int,
        outcome: str,
        action: str,
    ) -> EntityPage[AdminAuditView]:
        statement = select(AdminAuditLog)
        with suppress(ValueError):
            statement = statement.where(
                AdminAuditLog.outcome == AdminAuditOutcome(outcome)
            )
        if action:
            statement = statement.where(AdminAuditLog.action.ilike(f"%{action}%"))
        async with self._session_factory() as session:
            total = int(
                (
                    await session.scalar(
                        select(func.count()).select_from(statement.order_by(None).subquery())
                    )
                )
                or 0
            )
            rows = list(
                await session.scalars(
                    statement.order_by(
                        AdminAuditLog.created_at.desc(),
                        AdminAuditLog.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            )
        return EntityPage(tuple(_audit_view(row) for row in rows), total)

    async def get_audit_log(self, entity_id: uuid.UUID) -> AdminAuditView | None:
        async with self._session_factory() as session:
            row = await session.get(AdminAuditLog, entity_id)
        return None if row is None else _audit_view(row)


def _pipeline_view(row: PipelineRun) -> PipelineRunView:
    return PipelineRunView(
        row.id,
        row.initiator.value,
        row.operation.value,
        row.status.value,
        row.entity_type,
        row.entity_id,
        row.task_id,
        row.parameters,
        row.result_counts,
        row.error_category,
        row.started_at,
        row.finished_at,
        row.created_at,
        row.updated_at,
    )


def _audit_view(row: AdminAuditLog) -> AdminAuditView:
    return AdminAuditView(
        row.id,
        row.actor,
        row.action,
        row.entity_type,
        row.entity_id,
        row.outcome.value,
        row.detail,
        row.created_at,
    )

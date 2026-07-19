"""PostgreSQL-контракты PipelineRun, reconciliation и AdminAuditLog."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import NoReturn

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError, OperationalError

from aibot.cabinet.mutations import (
    CabinetMutationService,
    ConcurrentEntityUpdateError,
)
from aibot.db.base import Base
from aibot.db.session import AsyncSessionFactory, engine
from aibot.models.admin_audit_log import AdminAuditLog
from aibot.models.enums import (
    AdminAuditOutcome,
    PipelineInitiator,
    PipelineOperation,
    PipelineRunStatus,
    SourceType,
)
from aibot.models.pipeline_run import PipelineRun
from aibot.repositories.admin_audit_log_repository import AdminAuditLogRepository
from aibot.repositories.pipeline_run_repository import PipelineRunRepository
from aibot.services.admin_audit import AdminAuditService
from aibot.services.pipeline_reconciliation import PipelineReconciliationService
from aibot.services.pipeline_run_service import PipelineRunService
from aibot.services.source_service import SourceService

pytestmark = pytest.mark.integration


@pytest.fixture()
async def prepared_operations_database(
    unavailable_infrastructure: Callable[[str, BaseException], NoReturn],
) -> AsyncIterator[None]:
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    except (ConnectionRefusedError, DBAPIError, OSError, OperationalError) as exc:
        unavailable_infrastructure("PostgreSQL", exc)
    await engine.dispose()
    yield
    await engine.dispose()


async def test_pipeline_reconciliation_and_audit_are_persisted(
    prepared_operations_database: None,
) -> None:
    assert prepared_operations_database is None
    async with AsyncSessionFactory() as session:
        run, created = await PipelineRunService(
            repository=PipelineRunRepository(session)
        ).create_queued(
            initiator=PipelineInitiator.CABINET,
            operation=PipelineOperation.RUN_PIPELINE,
            idempotency_key="integration:full-pipeline",
            parameters={"parse_limit": 10},
        )
        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == run.id)
            .values(updated_at=datetime.now(UTC) - timedelta(hours=2))
        )
        await session.commit()
        stale_count = await PipelineReconciliationService(
            PipelineRunRepository(session)
        ).reconcile(stale_after_seconds=60)
        await AdminAuditService(AdminAuditLogRepository(session)).record(
            actor="admin",
            action="pipeline.reconcile",
            entity_type="pipeline_run",
            entity_id=run.id,
            outcome=AdminAuditOutcome.SUCCEEDED,
            detail="stale",
        )
        await session.refresh(run)
        stored_run = await session.get(PipelineRun, run.id)
        audit_rows = list(await session.scalars(select(AdminAuditLog)))

    await engine.dispose()
    assert created is True
    assert stale_count == 1
    assert stored_run is not None
    assert stored_run.status == PipelineRunStatus.STALE
    assert stored_run.finished_at is not None
    assert len(audit_rows) == 1
    assert audit_rows[0].detail == "stale"


async def test_cabinet_crud_uses_optimistic_version_and_audit(
    prepared_operations_database: None,
) -> None:
    assert prepared_operations_database is None
    mutations = CabinetMutationService(AsyncSessionFactory)
    source_id = await mutations.create_source(
        actor="admin",
        source_type="site",
        name="Versioned feed",
        url="https://example.test/versioned.xml",
        enabled=True,
    )
    keyword_id = await mutations.create_keyword(
        actor="admin",
        word="python",
        enabled=True,
    )
    async with AsyncSessionFactory() as session:
        source = await SourceService(session).get_source(source_id)
        original_version = source.updated_at

    await mutations.update_source(
        actor="admin",
        source_id=source_id,
        expected_updated_at=original_version,
        source_type=SourceType.SITE.value,
        name="Updated feed",
        url="https://example.test/versioned.xml",
        enabled=True,
    )
    with pytest.raises(ConcurrentEntityUpdateError):
        await mutations.update_source(
            actor="admin",
            source_id=source_id,
            expected_updated_at=original_version,
            source_type=SourceType.SITE.value,
            name="Stale update",
            url="https://example.test/versioned.xml",
            enabled=True,
        )

    async with AsyncSessionFactory() as session:
        audits = list(
            await session.scalars(
                select(AdminAuditLog).order_by(AdminAuditLog.created_at)
            )
        )

    await engine.dispose()
    assert keyword_id is not None
    assert [entry.outcome for entry in audits] == [
        AdminAuditOutcome.SUCCEEDED,
        AdminAuditOutcome.SUCCEEDED,
        AdminAuditOutcome.SUCCEEDED,
        AdminAuditOutcome.REJECTED,
    ]
    assert audits[-1].detail == "stale_version"

"""Persisted lifecycle ручного или автоматического pipeline-запуска."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from aibot.db.base import Base
from aibot.models.enums import (
    PipelineInitiator,
    PipelineOperation,
    PipelineRunStatus,
)
from aibot.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PipelineRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Источник истины о постановке и завершении Celery operation."""

    __tablename__ = "pipeline_runs"

    initiator: Mapped[PipelineInitiator] = mapped_column(
        Enum(PipelineInitiator, name="pipeline_initiator", native_enum=False),
        nullable=False,
    )
    operation: Mapped[PipelineOperation] = mapped_column(
        Enum(PipelineOperation, name="pipeline_operation", native_enum=False),
        nullable=False,
        index=True,
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        Enum(PipelineRunStatus, name="pipeline_run_status", native_enum=False),
        default=PipelineRunStatus.QUEUED,
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    result_counts: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_pipeline_runs_status_updated", PipelineRun.status, PipelineRun.updated_at)

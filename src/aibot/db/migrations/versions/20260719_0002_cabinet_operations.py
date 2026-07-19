"""Добавить lifecycle pipeline и административный аудит.

Revision ID: 20260719_0002
Revises: 20260719_0001
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0002"
down_revision: str | None = "20260719_0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Создать operational tables кабинета."""

    op.add_column(
        "keywords",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column(
            "initiator",
            sa.Enum("BEAT", "CABINET", "API", name="pipeline_initiator", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "operation",
            sa.Enum(
                "PARSE_SOURCE",
                "GENERATE_NEWS",
                "PUBLISH_POST",
                "RUN_PIPELINE",
                name="pipeline_operation",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "REVOKED",
                "STALE",
                name="pipeline_run_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("result_counts", sa.JSON(), nullable=True),
        sa.Column("error_category", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("ix_pipeline_runs_entity_id", "pipeline_runs", ["entity_id"])
    op.create_index("ix_pipeline_runs_operation", "pipeline_runs", ["operation"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])
    op.create_index(
        "ix_pipeline_runs_status_updated",
        "pipeline_runs",
        ["status", "updated_at"],
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum(
                "SUCCEEDED",
                "REJECTED",
                "FAILED",
                name="admin_audit_outcome",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("detail", sa.String(length=512), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_entity_id", "admin_audit_logs", ["entity_id"])
    op.create_index("ix_admin_audit_logs_outcome", "admin_audit_logs", ["outcome"])


def downgrade() -> None:
    """Удалить operational tables в обратном порядке."""

    op.drop_index("ix_admin_audit_logs_outcome", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_entity_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")

    op.drop_index("ix_pipeline_runs_status_updated", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_operation", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_entity_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_column("keywords", "updated_at")

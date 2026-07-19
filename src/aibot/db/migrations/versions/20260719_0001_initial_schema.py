"""Создать начальную схему приложения.

Revision ID: 20260719_0001
Revises:
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Создать таблицы, ограничения и индексы приложения."""

    op.create_table(
        "sources",
        sa.Column(
            "type",
            sa.Enum("SITE", "TELEGRAM", name="source_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("type", "url", name="uq_sources_type_url"),
    )
    op.create_index("ix_sources_type", "sources", ["type"], unique=False)

    op.create_table(
        "keywords",
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_keywords_word_lower",
        "keywords",
        [sa.text("lower(word)")],
        unique=True,
    )

    op.create_table(
        "news_items",
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "FILTERED_OUT",
                "READY_FOR_GENERATION",
                "GENERATED",
                "FAILED",
                name="news_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
        sa.UniqueConstraint("url"),
    )
    op.create_index(
        "ix_news_items_source_id",
        "news_items",
        ["source_id"],
        unique=False,
    )
    op.create_index("ix_news_items_status", "news_items", ["status"], unique=False)

    op.create_table(
        "posts",
        sa.Column("news_id", sa.Uuid(), nullable=False),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "GENERATED",
                "PUBLISHING",
                "PUBLISHED",
                "FAILED",
                name="post_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["news_id"], ["news_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_posts_news_id", "posts", ["news_id"], unique=False)
    op.create_index("ix_posts_status", "posts", ["status"], unique=False)
    op.create_index(
        "uq_posts_one_published_per_news",
        "posts",
        ["news_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )

    op.create_table(
        "error_logs",
        sa.Column(
            "scope",
            sa.Enum(
                "PARSER",
                "AI",
                "TELEGRAM",
                "CELERY",
                "API",
                name="error_scope",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("news_id", sa.Uuid(), nullable=True),
        sa.Column("post_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["news_id"], ["news_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_logs_news_id", "error_logs", ["news_id"], unique=False)
    op.create_index("ix_error_logs_post_id", "error_logs", ["post_id"], unique=False)
    op.create_index("ix_error_logs_scope", "error_logs", ["scope"], unique=False)
    op.create_index(
        "ix_error_logs_source_id",
        "error_logs",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удалить схему приложения в порядке, обратном зависимостям."""

    op.drop_index("ix_error_logs_source_id", table_name="error_logs")
    op.drop_index("ix_error_logs_scope", table_name="error_logs")
    op.drop_index("ix_error_logs_post_id", table_name="error_logs")
    op.drop_index("ix_error_logs_news_id", table_name="error_logs")
    op.drop_table("error_logs")

    op.drop_index(
        "uq_posts_one_published_per_news",
        table_name="posts",
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )
    op.drop_index("ix_posts_status", table_name="posts")
    op.drop_index("ix_posts_news_id", table_name="posts")
    op.drop_table("posts")

    op.drop_index("ix_news_items_status", table_name="news_items")
    op.drop_index("ix_news_items_source_id", table_name="news_items")
    op.drop_table("news_items")

    op.drop_index("uq_keywords_word_lower", table_name="keywords")
    op.drop_table("keywords")

    op.drop_index("ix_sources_type", table_name="sources")
    op.drop_table("sources")

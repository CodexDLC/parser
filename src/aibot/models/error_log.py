"""ORM-модель записи об ошибке API, парсинга, AI или Telegram."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aibot.db.base import Base
from aibot.models.enums import ErrorScope
from aibot.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from aibot.models.news_item import NewsItem
    from aibot.models.post import Post
    from aibot.models.source import Source


class ErrorLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Запись об ошибке API, парсинга, AI, Telegram или Celery."""

    __tablename__ = "error_logs"

    scope: Mapped[ErrorScope] = mapped_column(
        Enum(ErrorScope, name="error_scope", native_enum=False),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    news_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("news_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source: Mapped["Source | None"] = relationship(back_populates="error_logs")
    news_item: Mapped["NewsItem | None"] = relationship(back_populates="error_logs")
    post: Mapped["Post | None"] = relationship(back_populates="error_logs")

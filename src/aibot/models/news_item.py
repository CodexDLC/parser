"""ORM-модель нормализованной новости, полученной из источника."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aibot.db.base import Base
from aibot.models.enums import NewsStatus
from aibot.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from aibot.models.error_log import ErrorLog
    from aibot.models.post import Post
    from aibot.models.source import Source


class NewsItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Нормализованная новость, полученная из сайта или Telegram-канала."""

    __tablename__ = "news_items"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), unique=True, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[NewsStatus] = mapped_column(
        Enum(NewsStatus, name="news_status", native_enum=False),
        default=NewsStatus.NEW,
        nullable=False,
        index=True,
    )

    source: Mapped["Source"] = relationship(back_populates="news_items")
    posts: Mapped[list["Post"]] = relationship(
        back_populates="news_item",
        cascade="all, delete-orphan",
    )
    error_logs: Mapped[list["ErrorLog"]] = relationship(back_populates="news_item")

    @property
    def text_for_generation(self) -> str:
        """Вернуть текст новости для AI-генерации поста."""

        parts = [self.title, self.summary, self.raw_text or ""]
        return " ".join(part for part in parts if part).strip()

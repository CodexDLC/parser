"""ORM-модель источника новостей: сайт или Telegram-канал."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aibot.db.base import Base
from aibot.models.enums import SourceType
from aibot.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from aibot.models.error_log import ErrorLog
    from aibot.models.news_item import NewsItem


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Источник новостей: сайт или публичный Telegram-канал."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("type", "url", name="uq_sources_type_url"),)

    type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=False),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    news_items: Mapped[list["NewsItem"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    error_logs: Mapped[list["ErrorLog"]] = relationship(back_populates="source")

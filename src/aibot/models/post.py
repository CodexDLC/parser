"""ORM-модель AI-сгенерированного Telegram-поста."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aibot.db.base import Base
from aibot.models.enums import PostStatus
from aibot.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from aibot.models.error_log import ErrorLog
    from aibot.models.news_item import NewsItem


class Post(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """AI-сгенерированный Telegram-пост для одной новости."""

    __tablename__ = "posts"

    news_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("news_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status", native_enum=False),
        default=PostStatus.NEW,
        nullable=False,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    news_item: Mapped["NewsItem"] = relationship(back_populates="posts")
    error_logs: Mapped[list["ErrorLog"]] = relationship(back_populates="post")


Index(
    "uq_posts_one_published_per_news",
    Post.news_id,
    unique=True,
    postgresql_where=(Post.status == PostStatus.PUBLISHED),
)

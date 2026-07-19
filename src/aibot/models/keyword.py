"""ORM-модель ключевого слова для фильтрации новостей."""

from sqlalchemy import Boolean, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from aibot.db.base import Base
from aibot.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class Keyword(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Ключевое слово для фильтрации новостей."""

    __tablename__ = "keywords"

    word: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


Index("uq_keywords_word_lower", func.lower(Keyword.word), unique=True)

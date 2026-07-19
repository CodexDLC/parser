"""Pydantic-схемы для ключевых слов."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KeywordBase(BaseModel):
    """Общие поля ключевого слова."""

    word: str = Field(min_length=1, max_length=255, description="Ключевое слово.")
    enabled: bool = Field(default=True, description="Включено ли ключевое слово.")


class KeywordCreate(KeywordBase):
    """Тело запроса создания ключевого слова."""


class KeywordUpdate(BaseModel):
    """Тело запроса частичного обновления ключевого слова."""

    word: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None


class KeywordRead(KeywordBase):
    """Ответ API с ключевым словом."""

    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

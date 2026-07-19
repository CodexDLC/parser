"""Pydantic-схемы для источников новостей."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aibot.models.enums import SourceType


class SourceBase(BaseModel):
    """Общие поля источника новостей."""

    type: SourceType = Field(description="Тип источника: site или tg.")
    name: str = Field(min_length=1, max_length=255, description="Название источника.")
    url: str = Field(min_length=1, max_length=1024, description="URL сайта или username канала.")
    enabled: bool = Field(default=True, description="Включен ли источник.")


class SourceCreate(SourceBase):
    """Тело запроса создания источника."""


class SourceUpdate(BaseModel):
    """Тело запроса частичного обновления источника."""

    type: SourceType | None = Field(default=None, description="Новый тип источника.")
    name: str | None = Field(default=None, min_length=1, max_length=255, description="Новое имя.")
    url: str | None = Field(default=None, min_length=1, max_length=1024, description="Новый URL.")
    enabled: bool | None = Field(default=None, description="Новая активность источника.")


class SourceRead(SourceBase):
    """Ответ API с источником новостей."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceParseResponse(BaseModel):
    """Ответ ручного парсинга источника."""

    source_id: uuid.UUID
    parsed_count: int = Field(description="Сколько новостей вернул парсер.")
    saved_count: int = Field(description="Сколько новостей сохранено.")
    duplicate_count: int = Field(description="Сколько новостей пропущено как дубли.")
    filtered_out_count: int = Field(description="Сколько новостей не прошло фильтры.")
    ready_for_generation_count: int = Field(description="Сколько новостей готово к генерации.")

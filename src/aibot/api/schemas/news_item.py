"""Pydantic-схемы для новостей."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aibot.models.enums import NewsStatus


class NewsItemRead(BaseModel):
    """Ответ API с нормализованной новостью."""

    id: uuid.UUID
    title: str = Field(description="Заголовок новости.")
    url: str | None = Field(description="URL новости, если есть.")
    summary: str = Field(description="Краткое описание новости.")
    source_id: uuid.UUID = Field(description="ID источника новости.")
    published_at: datetime = Field(description="Дата публикации у источника.")
    raw_text: str | None = Field(description="Исходный текст, особенно для Telegram.")
    content_hash: str = Field(description="Hash для дедупликации.")
    status: NewsStatus = Field(description="Статус обработки новости.")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

"""Pydantic-схемы для AI-сгенерированных постов."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aibot.models.enums import PostStatus


class PostRead(BaseModel):
    """Ответ API с AI-сгенерированным постом."""

    id: uuid.UUID
    news_id: uuid.UUID = Field(description="ID новости, для которой создан пост.")
    generated_text: str = Field(description="Сгенерированный текст Telegram-поста.")
    status: PostStatus = Field(description="Статус генерации или публикации.")
    published_at: datetime | None = Field(description="Дата публикации в Telegram.")
    telegram_message_id: str | None = Field(description="ID сообщения Telegram.")
    error_message: str | None = Field(description="Последняя ошибка поста.")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

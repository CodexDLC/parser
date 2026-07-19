"""Pydantic-схемы для записей журнала ошибок."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aibot.models.enums import ErrorScope


class ErrorLogRead(BaseModel):
    """Ответ API с записью журнала ошибок."""

    id: uuid.UUID
    scope: ErrorScope = Field(description="Зона приложения, где возникла ошибка.")
    message: str = Field(description="Короткое описание ошибки.")
    details: str | None = Field(description="Подробности ошибки.")
    source_id: uuid.UUID | None
    news_id: uuid.UUID | None
    post_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

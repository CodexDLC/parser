"""Pydantic-схемы для ручной AI-генерации."""

from pydantic import BaseModel, Field


class ManualGenerationRequest(BaseModel):
    """Тело запроса ручной AI-генерации."""

    text: str = Field(min_length=1, description="Исходный текст новости.")
    source: str = Field(default="manual", description="Источник ручного текста.")

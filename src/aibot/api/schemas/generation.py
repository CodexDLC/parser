"""Pydantic-схемы для ручной AI-генерации."""

from pydantic import BaseModel, Field


class ManualGenerationRequest(BaseModel):
    """Тело запроса ручной AI-генерации."""

    text: str = Field(min_length=1, description="Исходный текст новости.")
    source: str = Field(default="manual", description="Источник ручного текста.")


class ManualGenerationResponse(BaseModel):
    """Ответ ручной AI-генерации."""

    generated_text: str = Field(description="Сгенерированный Telegram-пост.")
    fake_mode: bool = Field(description="Был ли использован fake AI режим.")

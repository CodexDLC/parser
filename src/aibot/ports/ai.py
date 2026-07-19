"""Application port для генерации текста через выбранную AI-интеграцию."""

from typing import Protocol


class AIClientPort(Protocol):
    """Стабильный контракт AI-генерации для сервисов приложения."""

    async def generate_telegram_post(self, input_text: str) -> str:
        """Сгенерировать Telegram-пост из нормализованного исходного текста."""

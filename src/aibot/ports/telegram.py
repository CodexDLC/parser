"""Application ports для раздельных Telegram reader и publisher."""

from typing import Protocol

from aibot.integrations.telegram_common import TelegramChannelMessage


class TelegramSourceReaderPort(Protocol):
    """Чтение источника не зависит от способа публикации."""

    async def verify_connection(self) -> None:
        """Проверить reader credentials."""

    async def read_channel_messages(
        self,
        channel: str,
        *,
        limit: int = 10,
    ) -> list[TelegramChannelMessage]:
        """Прочитать сообщения источника."""


class TelegramPublisherPort(Protocol):
    """Публикация не зависит от способа ingestion."""

    async def verify_connection(self) -> None:
        """Проверить publisher credentials и target."""

    async def publish_message(self, text: str) -> str:
        """Опубликовать один текст и вернуть message ID."""

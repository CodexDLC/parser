"""Совместимый Telethon facade для прежнего внутреннего контракта."""

from aibot.config import Settings
from aibot.integrations.telegram_common import (
    TelegramAuthorizationError,
    TelegramChannelMessage,
    TelegramClientError,
    TelegramConfigurationError,
    TelegramPublicationUncertainError,
    TelegramRateLimitError,
    TelegramTemporaryError,
)
from aibot.integrations.telethon_publisher import TelethonPublisher
from aibot.integrations.telethon_reader import TelethonChannelReader
from aibot.integrations.telethon_session import TelethonSession

__all__ = [
    "TelegramAuthorizationError",
    "TelegramChannelMessage",
    "TelegramClient",
    "TelegramClientError",
    "TelegramConfigurationError",
    "TelegramPublicationUncertainError",
    "TelegramRateLimitError",
    "TelegramTemporaryError",
]


class TelegramClient:
    """Compatibility facade; новые runtime-пути используют отдельные adapters."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        session = TelethonSession(settings)
        self._session = session
        self._reader = TelethonChannelReader(settings, session=session)
        self._publisher = TelethonPublisher(settings, session=session)

    async def read_channel_messages(
        self,
        channel: str,
        *,
        limit: int = 10,
    ) -> list[TelegramChannelMessage]:
        """Делегировать чтение отдельному Telethon reader."""

        return await self._reader.read_channel_messages(channel, limit=limit)

    async def publish_message(self, text: str) -> str:
        """Делегировать публикацию Telethon publisher."""

        return await self._publisher.publish_message(text)

    async def verify_connection(self) -> None:
        """Сохранить прежнюю проверку только Telethon session."""

        await self._session.verify_connection()

    async def authorize_session(self) -> None:
        """Сохранить прежнюю явную операцию авторизации."""

        await self._session.authorize()

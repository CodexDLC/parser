"""Публикация готовых постов через Telethon."""

from aibot.config import Settings
from aibot.integrations.telegram_common import (
    TelegramClientError,
    TelegramConfigurationError,
    build_dry_run_message_id,
)
from aibot.integrations.telethon_session import TelethonSession


class TelethonPublisher:
    """Telethon publication adapter, обязательный для Project M4."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: TelethonSession | None = None,
    ) -> None:
        self.settings = settings
        self.session = session or TelethonSession(settings)

    async def verify_connection(self) -> None:
        """Проверить session и наличие целевого канала."""

        self._ensure_target_channel()
        await self.session.verify_connection()

    async def publish_message(self, text: str) -> str:
        """Опубликовать сообщение или выполнить dry-run."""

        if self.settings.telegram_dry_run:
            return build_dry_run_message_id(text)
        self._ensure_target_channel()

        client = await self.session.connect_authorized()
        try:
            message = await client.send_message(self.settings.telegram_target_channel, text)
            return str(message.id)
        except TelegramClientError:
            raise
        except Exception as exc:
            raise TelegramClientError(
                f"Telegram publication failed: {exc.__class__.__name__}"
            ) from exc
        finally:
            await self.session.disconnect_quietly(client)

    def _ensure_target_channel(self) -> None:
        if not self.settings.telegram_target_channel:
            raise TelegramConfigurationError(
                "TELEGRAM_TARGET_CHANNEL is required when dry-run mode is disabled"
            )

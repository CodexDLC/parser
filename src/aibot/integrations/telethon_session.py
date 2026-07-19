"""Неинтерактивная Telethon session boundary и явная авторизация."""

from contextlib import suppress
from typing import Any

from aibot.config import Settings
from aibot.integrations.telegram_common import (
    TelegramAuthorizationError,
    TelegramClientError,
    TelegramConfigurationError,
)


class TelethonSession:
    """Создавать только авторизованные Telethon connections для adapters."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def connect_authorized(self) -> Any:
        """Подключить session без интерактивного запроса телефона или кода."""

        self.ensure_api_credentials()
        from telethon import TelegramClient as TelethonClient

        client = TelethonClient(
            self.settings.telegram_session_name,
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        )
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise TelegramAuthorizationError(
                    "Telegram session is not authorized; authorize it before starting workers"
                )
        except TelegramAuthorizationError:
            await self.disconnect_quietly(client)
            raise
        except Exception as exc:
            await self.disconnect_quietly(client)
            raise TelegramClientError(
                f"Telegram connection failed: {exc.__class__.__name__}"
            ) from exc
        return client

    async def verify_connection(self) -> None:
        """Проверить уже авторизованную session без публикации."""

        if self.settings.telegram_dry_run:
            raise TelegramConfigurationError(
                "TELEGRAM_DRY_RUN must be false for a real connection check"
            )
        client = await self.connect_authorized()
        try:
            account = await client.get_me()
            if account is None:
                raise TelegramAuthorizationError("Telegram session is not authorized")
        except TelegramClientError:
            raise
        except Exception as exc:
            raise TelegramClientError(
                f"Telegram verification failed: {exc.__class__.__name__}"
            ) from exc
        finally:
            await self.disconnect_quietly(client)

    async def authorize(self) -> None:
        """Явно запустить интерактивную первичную авторизацию."""

        self.ensure_api_credentials()
        from telethon import TelegramClient as TelethonClient

        client = TelethonClient(
            self.settings.telegram_session_name,
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        )
        try:
            await client.start()
            if not await client.is_user_authorized():
                raise TelegramAuthorizationError("Telegram session authorization failed")
        except TelegramClientError:
            raise
        except Exception as exc:
            raise TelegramClientError(
                f"Telegram session authorization failed: {exc.__class__.__name__}"
            ) from exc
        finally:
            await self.disconnect_quietly(client)

    def ensure_api_credentials(self) -> None:
        """Проверить наличие Telegram API credentials."""

        if not (self.settings.telegram_api_id and self.settings.telegram_api_hash):
            raise TelegramConfigurationError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH are required in real mode"
            )

    async def disconnect_quietly(self, client: Any) -> None:
        """Освободить connection, не маскируя основную ошибку."""

        with suppress(Exception):
            await client.disconnect()

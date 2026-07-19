"""Клиент Telethon для чтения каналов и публикации постов."""

import hashlib
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aibot.config import Settings


class TelegramClientError(RuntimeError):
    """Безопасная базовая ошибка Telegram adapter."""


class TelegramConfigurationError(TelegramClientError):
    """Telegram real-mode не имеет обязательных настроек."""


class TelegramAuthorizationError(TelegramClientError):
    """Telethon session не авторизована для фоновой работы."""


@dataclass(frozen=True)
class TelegramChannelMessage:
    """Нормализованное сообщение Telegram-канала до parser слоя."""

    message_id: int
    text: str
    published_at: datetime
    url: str | None = None


class TelegramClient:
    """Клиент чтения и публикации в Telegram с безопасным dry-run режимом."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def read_channel_messages(
        self,
        channel: str,
        *,
        limit: int = 10,
    ) -> list[TelegramChannelMessage]:
        """Прочитать сообщения канала или вернуть demo-сообщения в dry-run режиме."""

        if self.settings.telegram_dry_run:
            return self._build_dry_run_messages(channel=channel, limit=limit)

        messages: list[TelegramChannelMessage] = []
        client = await self._connect_authorized_client()
        try:
            async for message in client.iter_messages(channel, limit=limit):
                text = str(message.raw_text or message.message or "").strip()
                if not text:
                    continue
                published_at = message.date
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=UTC)
                messages.append(
                    TelegramChannelMessage(
                        message_id=message.id,
                        text=text,
                        published_at=published_at,
                        url=self._build_public_message_url(channel, message.id),
                    )
                )
        except TelegramClientError:
            raise
        except Exception as exc:
            raise TelegramClientError(
                f"Telegram read failed: {exc.__class__.__name__}"
            ) from exc
        finally:
            await self._disconnect_quietly(client)
        return messages

    async def publish_message(self, text: str) -> str:
        """Опубликовать сообщение или вернуть fake message_id в dry-run режиме."""

        if self.settings.telegram_dry_run:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
            return f"dry-run-{digest}"

        if not self.settings.telegram_target_channel:
            raise TelegramConfigurationError(
                "TELEGRAM_TARGET_CHANNEL is required when dry-run mode is disabled"
            )

        client = await self._connect_authorized_client()
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
            await self._disconnect_quietly(client)

    async def verify_connection(self) -> None:
        """Проверить real-mode credentials и авторизованную session без публикации."""

        if self.settings.telegram_dry_run:
            raise TelegramConfigurationError(
                "TELEGRAM_DRY_RUN must be false for a real connection check"
            )

        client = await self._connect_authorized_client()
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
            await self._disconnect_quietly(client)

    async def authorize_session(self) -> None:
        """Явно запустить интерактивную первичную авторизацию Telethon session."""

        self._ensure_api_credentials()
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
            await self._disconnect_quietly(client)

    def _ensure_api_credentials(self) -> None:
        """Проверить наличие Telegram API credentials для real-mode."""

        if not (self.settings.telegram_api_id and self.settings.telegram_api_hash):
            raise TelegramConfigurationError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH are required in real mode"
            )

    async def _connect_authorized_client(self) -> Any:
        """Подключить уже авторизованную session без интерактивного start()."""

        self._ensure_api_credentials()
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
            await self._disconnect_quietly(client)
            raise
        except Exception as exc:
            await self._disconnect_quietly(client)
            raise TelegramClientError(
                f"Telegram connection failed: {exc.__class__.__name__}"
            ) from exc
        return client

    async def _disconnect_quietly(self, client: Any) -> None:
        """Освободить Telethon connection, не маскируя основную ошибку."""

        with suppress(Exception):
            await client.disconnect()

    def _build_dry_run_messages(
        self,
        *,
        channel: str,
        limit: int,
    ) -> list[TelegramChannelMessage]:
        """Вернуть предсказуемые demo-сообщения без подключения к Telegram."""

        now = datetime.now(tz=UTC)
        messages = [
            TelegramChannelMessage(
                message_id=1001,
                text="Python community обсудила новый релиз и ускорение популярных сценариев.",
                published_at=now,
                url=self._build_public_message_url(channel, 1001),
            ),
            TelegramChannelMessage(
                message_id=1002,
                text="AI tools помогают редакциям быстрее готовить короткие новостные сводки.",
                published_at=now,
                url=self._build_public_message_url(channel, 1002),
            ),
        ]
        return messages[:limit]

    def _build_public_message_url(self, channel: str, message_id: int) -> str | None:
        """Построить публичную ссылку на сообщение, если источник похож на username."""

        username = channel.strip()
        if username.startswith("https://t.me/"):
            username = username.removeprefix("https://t.me/").split("/", maxsplit=1)[0]
        username = username.removeprefix("@").strip("/")
        if not username or username.startswith(("+", "joinchat/")):
            return None
        return f"https://t.me/{username}/{message_id}"

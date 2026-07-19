"""Клиент Telethon для чтения каналов и публикации постов."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from aibot.config import Settings


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

        self._ensure_api_credentials()
        from telethon import TelegramClient as TelethonClient

        messages: list[TelegramChannelMessage] = []
        async with TelethonClient(
            self.settings.telegram_session_name,
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        ) as client:
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
        return messages

    async def publish_message(self, text: str) -> str:
        """Опубликовать сообщение или вернуть fake message_id в dry-run режиме."""

        if self.settings.telegram_dry_run:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
            return f"dry-run-{digest}"

        self._ensure_api_credentials()
        if not self.settings.telegram_target_channel:
            raise RuntimeError("Telegram credentials are required when dry-run mode is disabled")

        from telethon import TelegramClient as TelethonClient

        async with TelethonClient(
            self.settings.telegram_session_name,
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        ) as client:
            message = await client.send_message(self.settings.telegram_target_channel, text)
            return str(message.id)

    def _ensure_api_credentials(self) -> None:
        """Проверить наличие Telegram API credentials для real-mode."""

        if not (self.settings.telegram_api_id and self.settings.telegram_api_hash):
            raise RuntimeError(
                "Telegram API credentials are required when dry-run mode is disabled"
            )

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

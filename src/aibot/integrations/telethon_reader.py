"""Чтение публичных Telegram-каналов через Telethon."""

from datetime import UTC, datetime

from aibot.config import Settings
from aibot.integrations.telegram_common import TelegramChannelMessage, TelegramClientError
from aibot.integrations.telethon_session import TelethonSession


class TelethonChannelReader:
    """Telethon adapter только для source ingestion."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: TelethonSession | None = None,
    ) -> None:
        self.settings = settings
        self.session = session or TelethonSession(settings)

    async def verify_connection(self) -> None:
        """Проверить авторизованную user session."""

        await self.session.verify_connection()

    async def read_channel_messages(
        self,
        channel: str,
        *,
        limit: int = 10,
    ) -> list[TelegramChannelMessage]:
        """Прочитать публичный канал или вернуть demo-сообщения."""

        if self.settings.telegram_dry_run:
            return self._build_dry_run_messages(channel=channel, limit=limit)

        messages: list[TelegramChannelMessage] = []
        client = await self.session.connect_authorized()
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
            raise TelegramClientError(f"Telegram read failed: {exc.__class__.__name__}") from exc
        finally:
            await self.session.disconnect_quietly(client)
        return messages

    def _build_dry_run_messages(
        self,
        *,
        channel: str,
        limit: int,
    ) -> list[TelegramChannelMessage]:
        """Вернуть предсказуемые demo-сообщения без Telegram."""

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
        """Построить публичную ссылку для username-источника."""

        username = channel.strip()
        if username.startswith("https://t.me/"):
            username = username.removeprefix("https://t.me/").split("/", maxsplit=1)[0]
        username = username.removeprefix("@").strip("/")
        if not username or username.startswith(("+", "joinchat/")):
            return None
        return f"https://t.me/{username}/{message_id}"

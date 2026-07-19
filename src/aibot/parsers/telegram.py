"""Парсер публичных Telegram-каналов через Telethon."""

from aibot.config import Settings, get_settings
from aibot.integrations.telegram_common import TelegramChannelMessage
from aibot.integrations.telethon_reader import TelethonChannelReader
from aibot.parsers.base import ParsedNewsItem
from aibot.ports.telegram import TelegramSourceReaderPort


class TelegramChannelParser:
    """Парсер публичного Telegram-канала в нормализованные новости."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        telegram_client: TelegramSourceReaderPort | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.telegram_client = telegram_client or TelethonChannelReader(self.settings)

    async def parse(
        self,
        *,
        source_name: str,
        url: str,
        limit: int = 10,
    ) -> list[ParsedNewsItem]:
        """Прочитать Telegram-канал и вернуть нормализованные элементы новостей."""

        messages = await self.telegram_client.read_channel_messages(url, limit=limit)
        return [
            ParsedNewsItem(
                title=self._build_title(message),
                url=message.url,
                summary=self._build_summary(message),
                source=source_name,
                published_at=message.published_at,
                raw_text=message.text,
            )
            for message in messages
        ]

    def _build_title(self, message: TelegramChannelMessage) -> str:
        """Построить короткий заголовок из текста Telegram-сообщения."""

        first_line = next(
            (line.strip() for line in message.text.splitlines() if line.strip()),
            message.text.strip(),
        )
        return self._compact(first_line, max_length=140)

    def _build_summary(self, message: TelegramChannelMessage) -> str:
        """Построить краткое описание из текста Telegram-сообщения."""

        return self._compact(message.text, max_length=280)

    def _compact(self, value: str, *, max_length: int) -> str:
        """Сжать пробелы и обрезать текст до читаемой длины."""

        compact_value = " ".join(value.split())
        if len(compact_value) <= max_length:
            return compact_value
        return f"{compact_value[: max_length - 1].rstrip()}…"

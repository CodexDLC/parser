"""Тесты Telegram client/parser в безопасном dry-run режиме."""

from datetime import UTC, datetime

import pytest

from aibot.config import Settings
from aibot.integrations.telegram_client import TelegramChannelMessage, TelegramClient
from aibot.parsers.telegram import TelegramChannelParser


class FakeTelegramClient:
    """Fake Telegram client для parser-теста без Telethon."""

    async def read_channel_messages(
        self,
        channel: str,
        *,
        limit: int = 10,
    ) -> list[TelegramChannelMessage]:
        """Вернуть одно fake-сообщение."""

        return [
            TelegramChannelMessage(
                message_id=42,
                text="Python release\nНовая версия ускорила несколько сценариев.",
                published_at=datetime(2026, 7, 11, tzinfo=UTC),
                url=f"https://t.me/{channel.removeprefix('@')}/42",
            )
        ][:limit]


@pytest.mark.asyncio
async def test_telegram_client_reads_dry_run_messages_without_credentials() -> None:
    """TelegramClient возвращает demo-сообщения без реальных ключей."""

    client = TelegramClient(Settings(telegram_dry_run=True))

    messages = await client.read_channel_messages("@demo_channel", limit=1)

    assert len(messages) == 1
    assert messages[0].message_id == 1001
    assert "Python" in messages[0].text
    assert messages[0].url == "https://t.me/demo_channel/1001"


@pytest.mark.asyncio
async def test_telegram_parser_normalizes_messages() -> None:
    """TelegramChannelParser превращает сообщения в ParsedNewsItem."""

    parser = TelegramChannelParser(
        settings=Settings(telegram_dry_run=True),
        telegram_client=FakeTelegramClient(),  # type: ignore[arg-type]
    )

    items = await parser.parse(source_name="Demo Telegram", url="@demo_channel", limit=1)

    assert len(items) == 1
    assert items[0].title == "Python release"
    assert "Новая версия" in items[0].summary
    assert items[0].source == "Demo Telegram"
    assert items[0].url == "https://t.me/demo_channel/42"
    assert items[0].raw_text.startswith("Python release")

"""Тесты Telegram client/parser в безопасном dry-run режиме."""

from datetime import UTC, datetime
from typing import Any

import pytest

from aibot.config import Settings
from aibot.integrations.telegram_client import (
    TelegramAuthorizationError,
    TelegramChannelMessage,
    TelegramClient,
)
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


class FakeTelethonClient:
    """Неинтерактивный Telethon double для real-mode контрактов."""

    authorized = True
    instances: list["FakeTelethonClient"] = []

    def __init__(self, *_: Any) -> None:
        self.connected = False
        self.disconnected = False
        self.started = False
        self.__class__.instances.append(self)

    async def connect(self) -> None:
        """Зафиксировать явное подключение без вызова start()."""

        self.connected = True

    async def disconnect(self) -> None:
        """Зафиксировать освобождение соединения."""

        self.disconnected = True

    async def start(self) -> None:
        """Имитировать явно запрошенную интерактивную авторизацию."""

        self.started = True

    async def is_user_authorized(self) -> bool:
        """Вернуть управляемый статус session."""

        return self.authorized

    async def get_me(self) -> object:
        """Имитировать проверку авторизованного аккаунта."""

        return object()

    async def iter_messages(self, _: str, *, limit: int) -> Any:
        """Вернуть одно сообщение через async iterator."""

        messages = [
            type(
                "Message",
                (),
                {
                    "id": 77,
                    "raw_text": "Live Telegram message",
                    "message": "Live Telegram message",
                    "date": datetime(2026, 7, 19, tzinfo=UTC),
                },
            )()
        ]
        for message in messages[:limit]:
            yield message


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
    assert items[0].raw_text is not None
    assert items[0].raw_text.startswith("Python release")


@pytest.mark.asyncio
async def test_real_telegram_read_uses_noninteractive_authorized_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real-mode явно подключается и не запускает интерактивную авторизацию."""

    FakeTelethonClient.authorized = True
    FakeTelethonClient.instances.clear()
    monkeypatch.setattr("telethon.TelegramClient", FakeTelethonClient)
    client = TelegramClient(
        Settings(
            telegram_api_id=123,
            telegram_api_hash="hash",
            telegram_dry_run=False,
        )
    )

    messages = await client.read_channel_messages("@public_channel", limit=1)

    assert [message.message_id for message in messages] == [77]
    assert len(FakeTelethonClient.instances) == 1
    assert FakeTelethonClient.instances[0].connected is True
    assert FakeTelethonClient.instances[0].disconnected is True


@pytest.mark.asyncio
async def test_real_telegram_rejects_unauthorized_session_without_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Background runtime завершается типизированной ошибкой вместо запроса телефона."""

    FakeTelethonClient.authorized = False
    FakeTelethonClient.instances.clear()
    monkeypatch.setattr("telethon.TelegramClient", FakeTelethonClient)
    client = TelegramClient(
        Settings(
            telegram_api_id=123,
            telegram_api_hash="hash",
            telegram_dry_run=False,
        )
    )

    with pytest.raises(TelegramAuthorizationError):
        await client.verify_connection()

    assert FakeTelethonClient.instances[0].disconnected is True


@pytest.mark.asyncio
async def test_telegram_session_authorization_is_a_separate_explicit_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Только специальная операция имеет право вызвать интерактивный start()."""

    FakeTelethonClient.authorized = True
    FakeTelethonClient.instances.clear()
    monkeypatch.setattr("telethon.TelegramClient", FakeTelethonClient)
    client = TelegramClient(
        Settings(
            telegram_api_id=123,
            telegram_api_hash="hash",
            telegram_dry_run=True,
        )
    )

    await client.authorize_session()

    assert FakeTelethonClient.instances[0].started is True
    assert FakeTelethonClient.instances[0].disconnected is True

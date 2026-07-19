"""Строгий выбор одного Telegram publisher без runtime fallback."""

from aibot.config import Settings
from aibot.integrations.telegram_bot_publisher import TelegramBotPublisher
from aibot.integrations.telethon_publisher import TelethonPublisher
from aibot.ports.telegram import TelegramPublisherPort


def build_telegram_publisher(settings: Settings) -> TelegramPublisherPort:
    """Построить ровно один adapter из явной настройки."""

    if settings.telegram_publisher == "bot_api":
        return TelegramBotPublisher(settings)
    return TelethonPublisher(settings)

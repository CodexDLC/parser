"""Явная интерактивная первичная авторизация Telethon session."""

import asyncio
import json

from aibot.config import Settings
from aibot.integrations.telegram_common import TelegramClientError
from aibot.integrations.telethon_session import TelethonSession


async def authorize() -> int:
    """Создать или обновить session без вывода credentials и account details."""

    try:
        await TelethonSession(Settings()).authorize()
    except TelegramClientError as exc:
        print(
            json.dumps(
                {
                    "service": "telegram",
                    "status": "failed",
                    "error_type": exc.__class__.__name__,
                },
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "service": "telegram",
                "status": "authorized",
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    """Запустить явно разрешённый интерактивный authorization flow."""

    return asyncio.run(authorize())


if __name__ == "__main__":
    raise SystemExit(main())

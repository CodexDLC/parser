"""Публикация сообщений через Telegram Bot HTTP API."""

from collections.abc import Mapping
from typing import Any

import httpx

from aibot.config import Settings
from aibot.integrations.telegram_common import (
    TelegramAuthorizationError,
    TelegramClientError,
    TelegramConfigurationError,
    TelegramPublicationUncertainError,
    TelegramRateLimitError,
    TelegramTemporaryError,
    build_dry_run_message_id,
)


class TelegramBotPublisher:
    """Bot API adapter только для исходящей публикации."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._http_client = http_client

    async def verify_connection(self) -> None:
        """Проверить bot token и доступность target без публикации."""

        self._ensure_configured()
        await self._call("getMe", {})
        await self._call(
            "getChat",
            {"chat_id": self.settings.telegram_target_channel},
        )

    async def publish_message(self, text: str) -> str:
        """Отправить текст через sendMessage или выполнить dry-run."""

        if self.settings.telegram_dry_run:
            return build_dry_run_message_id(text)
        self._ensure_configured()
        result = await self._call(
            "sendMessage",
            {
                "chat_id": self.settings.telegram_target_channel,
                "text": text,
            },
            publication=True,
        )
        message_id = result.get("message_id") if isinstance(result, Mapping) else None
        if not isinstance(message_id, int | str):
            raise TelegramPublicationUncertainError("Telegram publication result is invalid")
        return str(message_id)

    async def _call(
        self,
        method: str,
        payload: Mapping[str, object],
        *,
        publication: bool = False,
    ) -> Any:
        token = self.settings.telegram_bot_token
        if not token:
            raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is required")
        url = f"https://api.telegram.org/bot{token}/{method}"
        try:
            response = await self._post(url, payload)
        except httpx.TimeoutException as exc:
            error_type = (
                TelegramPublicationUncertainError if publication else TelegramTemporaryError
            )
            raise error_type("Telegram Bot API timeout") from exc
        except httpx.RequestError as exc:
            raise TelegramTemporaryError(
                f"Telegram Bot API request failed: {exc.__class__.__name__}"
            ) from exc

        body = self._safe_json(response)
        if response.status_code == 429:
            raise TelegramRateLimitError(retry_after_seconds=self._retry_after_seconds(body))
        if response.status_code in {401, 403}:
            raise TelegramAuthorizationError("Telegram Bot API authorization failed")
        if response.status_code >= 500:
            if publication:
                raise TelegramPublicationUncertainError("Telegram Bot API server error")
            raise TelegramTemporaryError("Telegram Bot API server error")
        if response.status_code >= 400:
            raise TelegramClientError("Telegram Bot API request rejected")
        if not isinstance(body, Mapping) or body.get("ok") is not True:
            if publication:
                raise TelegramPublicationUncertainError("Telegram Bot API response is invalid")
            raise TelegramClientError("Telegram Bot API response is invalid")
        return body.get("result")

    async def _post(
        self,
        url: str,
        payload: Mapping[str, object],
    ) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.post(url, json=payload)
        timeout = httpx.Timeout(self.settings.telegram_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, json=payload)

    def _ensure_configured(self) -> None:
        if not self.settings.telegram_bot_token:
            raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is required for bot_api publisher")
        if not self.settings.telegram_target_channel:
            raise TelegramConfigurationError(
                "TELEGRAM_TARGET_CHANNEL is required for bot_api publisher"
            )

    @staticmethod
    def _safe_json(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _retry_after_seconds(body: object) -> int | None:
        if not isinstance(body, Mapping):
            return None
        parameters = body.get("parameters")
        if not isinstance(parameters, Mapping):
            return None
        value = parameters.get("retry_after")
        return value if isinstance(value, int) and value >= 0 else None

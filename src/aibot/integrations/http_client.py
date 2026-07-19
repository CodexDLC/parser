"""Ограниченный async HTTP-клиент для загрузки внешних источников."""

from urllib.parse import urlsplit, urlunsplit

import httpx


class HttpClientError(Exception):
    """Базовая ошибка загрузки внешнего HTTP-ресурса."""


class HttpTemporaryError(HttpClientError):
    """Временная ошибка, которую Celery сможет повторить."""


class HttpPermanentError(HttpClientError):
    """Постоянная ошибка запроса, которую повторять не следует."""


class HttpResponseTooLargeError(HttpPermanentError):
    """HTTP-ответ превысил разрешённый размер."""


class HttpClient:
    """Загрузить ограниченный бинарный HTTP-ответ без бизнес-логики parser-а."""

    RETRYABLE_STATUS_CODES = frozenset({408, 425, 429})

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_response_bytes: int = 2_000_000,
        user_agent: str = "Project-M4-RSS/0.1",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if not user_agent.strip():
            raise ValueError("user_agent must not be empty")

        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent
        self._client = client

    async def get_bytes(self, url: str) -> bytes:
        """Загрузить URL, проверить статус и ограничить размер ответа."""

        if self._client is not None:
            return await self._download(self._client, url)

        async with httpx.AsyncClient() as client:
            return await self._download(client, url)

    async def _download(self, client: httpx.AsyncClient, url: str) -> bytes:
        safe_url = self._sanitize_url(url)
        try:
            async with client.stream(
                "GET",
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as response:
                self._raise_for_status(response.status_code, safe_url)
                self._raise_for_content_length(response, safe_url)

                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > self.max_response_bytes:
                        raise HttpResponseTooLargeError(
                            f"HTTP response exceeded {self.max_response_bytes} bytes: {safe_url}"
                        )
                return bytes(payload)
        except HttpClientError:
            raise
        except (httpx.InvalidURL, httpx.UnsupportedProtocol) as exc:
            raise HttpPermanentError(f"Invalid HTTP source URL: {safe_url}") from exc
        except httpx.TimeoutException as exc:
            raise HttpTemporaryError(f"HTTP timeout while fetching {safe_url}") from exc
        except httpx.RequestError as exc:
            raise HttpTemporaryError(f"HTTP request failed for {safe_url}") from exc

    def _raise_for_status(self, status_code: int, safe_url: str) -> None:
        if status_code < 400:
            return

        message = f"HTTP {status_code} while fetching {safe_url}"
        if status_code in self.RETRYABLE_STATUS_CODES or status_code >= 500:
            raise HttpTemporaryError(message)
        raise HttpPermanentError(message)

    def _raise_for_content_length(self, response: httpx.Response, safe_url: str) -> None:
        raw_content_length = response.headers.get("content-length")
        if raw_content_length is None:
            return
        try:
            content_length = int(raw_content_length)
        except ValueError:
            return
        if content_length > self.max_response_bytes:
            raise HttpResponseTooLargeError(
                f"HTTP response exceeded {self.max_response_bytes} bytes: {safe_url}"
            )

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Удалить query/fragment, чтобы не раскрывать токены в ошибках."""

        try:
            parts = urlsplit(url)
        except ValueError:
            return "<invalid-url>"
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

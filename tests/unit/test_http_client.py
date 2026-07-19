"""Тесты ограниченного HTTP-клиента без внешней сети."""

import httpx
import pytest

from aibot.integrations.http_client import (
    HttpClient,
    HttpPermanentError,
    HttpResponseTooLargeError,
    HttpTemporaryError,
)


@pytest.mark.asyncio
async def test_http_client_downloads_bytes_with_configured_user_agent() -> None:
    """Клиент загружает тело и передаёт явный User-Agent."""

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"<rss />")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        http_client = HttpClient(
            client=client,
            timeout_seconds=3,
            max_response_bytes=1024,
            user_agent="M4-Test/1.0",
        )
        payload = await http_client.get_bytes("https://news.example/feed.xml")

    assert payload == b"<rss />"
    assert requests[0].headers["user-agent"] == "M4-Test/1.0"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 425, 429, 500, 503])
async def test_http_client_marks_retryable_statuses_as_temporary(status_code: int) -> None:
    """Временные HTTP-статусы получают отдельный тип ошибки для Celery retry."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        http_client = HttpClient(client=client)

        with pytest.raises(HttpTemporaryError):
            await http_client.get_bytes("https://news.example/feed.xml")


@pytest.mark.asyncio
async def test_http_client_marks_non_retryable_status_as_permanent() -> None:
    """Постоянная HTTP-ошибка не должна запускать бесконечные retries."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        http_client = HttpClient(client=client)

        with pytest.raises(HttpPermanentError):
            await http_client.get_bytes("https://news.example/feed.xml")


@pytest.mark.asyncio
async def test_http_client_maps_timeout_to_temporary_error() -> None:
    """Timeout преобразуется в retryable ошибку интеграции."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        http_client = HttpClient(client=client)

        with pytest.raises(HttpTemporaryError):
            await http_client.get_bytes("https://news.example/feed.xml")


@pytest.mark.asyncio
async def test_http_client_rejects_oversized_response() -> None:
    """Клиент останавливает загрузку при превышении лимита."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"0123456789")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        http_client = HttpClient(client=client, max_response_bytes=5)

        with pytest.raises(HttpResponseTooLargeError):
            await http_client.get_bytes("https://news.example/feed.xml")


@pytest.mark.asyncio
async def test_http_error_does_not_expose_query_string() -> None:
    """Сообщение ошибки не раскрывает секретные query-параметры URL."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        http_client = HttpClient(client=client)

        with pytest.raises(HttpPermanentError) as error:
            await http_client.get_bytes("https://news.example/feed.xml?token=secret")

    assert "secret" not in str(error.value)
    assert "?token" not in str(error.value)

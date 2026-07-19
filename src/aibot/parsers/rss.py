"""Универсальный parser RSS/Atom-лент."""

import calendar
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from aibot.config import Settings, get_settings
from aibot.integrations.http_client import HttpClient
from aibot.parsers.base import ParsedNewsItem


class HttpContentReader(Protocol):
    """Минимальный HTTP port, необходимый RSS parser-у."""

    async def get_bytes(self, url: str) -> bytes:
        """Загрузить бинарное содержимое URL."""


class RssFeedParseError(Exception):
    """Полученный документ не является корректной RSS/Atom-лентой."""


class RssAtomParser:
    """Загрузить и нормализовать стандартную RSS или Atom-ленту."""

    def __init__(
        self,
        *,
        http_client: HttpContentReader | None = None,
        settings: Settings | None = None,
    ) -> None:
        runtime_settings = settings or get_settings()
        self.http_client = http_client or HttpClient(
            timeout_seconds=runtime_settings.http_timeout_seconds,
            max_response_bytes=runtime_settings.http_max_response_bytes,
            user_agent=runtime_settings.http_user_agent,
        )

    async def parse(
        self,
        *,
        source_name: str,
        url: str,
        limit: int = 10,
    ) -> list[ParsedNewsItem]:
        """Получить RSS/Atom и вернуть нормализованные записи."""

        if limit < 1:
            return []

        payload = await self.http_client.get_bytes(url)
        feed = feedparser.parse(payload)
        entries = list(feed.entries)
        if not feed.version or (feed.bozo and not entries):
            raise RssFeedParseError(f"Source is not a valid RSS/Atom feed: {self._safe_url(url)}")

        parsed_items: list[ParsedNewsItem] = []
        fallback_published_at = datetime.now(tz=UTC)
        for entry in entries:
            item = self._normalize_entry(
                entry,
                source_name=source_name,
                feed_url=url,
                fallback_published_at=fallback_published_at,
            )
            if item is None:
                continue
            parsed_items.append(item)
            if len(parsed_items) >= limit:
                break
        return parsed_items

    def _normalize_entry(
        self,
        entry: Any,
        *,
        source_name: str,
        feed_url: str,
        fallback_published_at: datetime,
    ) -> ParsedNewsItem | None:
        title = self._plain_text(entry.get("title"))
        if not title:
            return None

        raw_summary = self._entry_summary(entry)
        summary = self._plain_text(raw_summary) or title
        raw_link = entry.get("link")
        normalized_url = urljoin(feed_url, str(raw_link)) if raw_link else None

        return ParsedNewsItem(
            title=title,
            url=normalized_url,
            summary=summary,
            source=source_name,
            published_at=self._published_at(entry) or fallback_published_at,
            raw_text=self._plain_text(raw_summary) or None,
        )

    @staticmethod
    def _entry_summary(entry: Any) -> str:
        for field in ("summary", "description"):
            value = entry.get(field)
            if value:
                return str(value)

        content = entry.get("content") or []
        if content and content[0].get("value"):
            return str(content[0]["value"])
        return ""

    @staticmethod
    def _published_at(entry: Any) -> datetime | None:
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed_time is None:
            return None
        timestamp = calendar.timegm(parsed_time)
        return datetime.fromtimestamp(timestamp, tz=UTC)

    @staticmethod
    def _plain_text(value: Any) -> str:
        if value is None:
            return ""
        return BeautifulSoup(str(value), "lxml").get_text(" ", strip=True)

    @staticmethod
    def _safe_url(url: str) -> str:
        return url.split("?", maxsplit=1)[0]

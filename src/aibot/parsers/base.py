"""Базовый интерфейс парсера и нормализованный результат парсинга."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ParsedNewsItem:
    """Нормализованная новость, полученная парсером до сохранения в БД."""

    title: str
    url: str | None
    summary: str
    source: str
    published_at: datetime
    raw_text: str | None = None

    @property
    def text_for_filtering(self) -> str:
        """Вернуть текст, по которому удобно фильтровать и дедуплицировать новость."""

        parts = [self.title, self.summary, self.raw_text or ""]
        return " ".join(part for part in parts if part).strip()


class NewsParser(Protocol):
    """Минимальный контракт парсера источника новостей."""

    async def parse(self, *, source_name: str, url: str, limit: int = 10) -> list[ParsedNewsItem]:
        """Получить нормализованные новости из источника."""

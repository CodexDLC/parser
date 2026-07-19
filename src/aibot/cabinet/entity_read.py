"""Typed read port для доменных страниц кабинета."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EntityPage[T]:
    """Ограниченная страница данных и общий count."""

    items: tuple[T, ...]
    total: int


@dataclass(frozen=True, slots=True)
class SourceView:
    id: uuid.UUID
    type: str
    name: str
    url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class KeywordView:
    id: uuid.UUID
    word: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class NewsView:
    id: uuid.UUID
    title: str
    url: str | None
    summary: str
    raw_text: str | None
    source_id: uuid.UUID
    source_name: str
    status: str
    published_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PostView:
    id: uuid.UUID
    news_id: uuid.UUID
    news_title: str
    generated_text: str
    status: str
    published_at: datetime | None
    telegram_message_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ErrorLogView:
    id: uuid.UUID
    scope: str
    message: str
    details: str | None
    source_id: uuid.UUID | None
    news_id: uuid.UUID | None
    post_id: uuid.UUID | None
    created_at: datetime


class CabinetEntityReader(Protocol):
    """Application-owned read port, не зависящий от Jinja или HTTP."""

    async def list_sources(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        source_type: str,
        enabled: str,
    ) -> EntityPage[SourceView]: ...

    async def get_source(self, entity_id: uuid.UUID) -> SourceView | None: ...

    async def list_keywords(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        enabled: str,
    ) -> EntityPage[KeywordView]: ...

    async def get_keyword(self, entity_id: uuid.UUID) -> KeywordView | None: ...

    async def list_news(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        status: str,
        source_id: str,
    ) -> EntityPage[NewsView]: ...

    async def get_news(self, entity_id: uuid.UUID) -> NewsView | None: ...

    async def list_posts(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        status: str,
    ) -> EntityPage[PostView]: ...

    async def get_post(self, entity_id: uuid.UUID) -> PostView | None: ...

    async def list_errors(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        scope: str,
    ) -> EntityPage[ErrorLogView]: ...

    async def get_error(self, entity_id: uuid.UUID) -> ErrorLogView | None: ...

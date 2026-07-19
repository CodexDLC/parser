"""PostgreSQL adapter read-only страниц кабинета."""

import uuid
from enum import StrEnum

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aibot.cabinet.entity_read import (
    EntityPage,
    ErrorLogView,
    KeywordView,
    NewsView,
    PostView,
    SourceView,
)
from aibot.models.enums import ErrorScope, NewsStatus, PostStatus, SourceType
from aibot.models.error_log import ErrorLog
from aibot.models.keyword import Keyword
from aibot.models.news_item import NewsItem
from aibot.models.post import Post
from aibot.models.source import Source


class SqlAlchemyCabinetEntityReader:
    """Выполнять count + bounded rows для списка и один запрос для карточки."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_sources(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        source_type: str,
        enabled: str,
    ) -> EntityPage[SourceView]:
        statement = select(Source)
        if search:
            statement = statement.where(
                or_(Source.name.ilike(f"%{search}%"), Source.url.ilike(f"%{search}%"))
            )
        parsed_type = _enum_or_none(SourceType, source_type)
        if parsed_type is not None:
            statement = statement.where(Source.type == parsed_type)
        parsed_enabled = _bool_or_none(enabled)
        if parsed_enabled is not None:
            statement = statement.where(Source.enabled.is_(parsed_enabled))
        async with self._session_factory() as session:
            rows, total = await _page(
                session,
                statement.order_by(Source.created_at.desc(), Source.id.desc()),
                offset=offset,
                limit=limit,
            )
        return EntityPage(
            tuple(
                SourceView(
                    row.id,
                    row.type.value,
                    row.name,
                    row.url,
                    row.enabled,
                    row.created_at,
                    row.updated_at,
                )
                for row in rows
            ),
            total,
        )

    async def get_source(self, entity_id: uuid.UUID) -> SourceView | None:
        async with self._session_factory() as session:
            row = await session.get(Source, entity_id)
        if row is None:
            return None
        return SourceView(
            row.id,
            row.type.value,
            row.name,
            row.url,
            row.enabled,
            row.created_at,
            row.updated_at,
        )

    async def list_keywords(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        enabled: str,
    ) -> EntityPage[KeywordView]:
        statement = select(Keyword)
        if search:
            statement = statement.where(Keyword.word.ilike(f"%{search}%"))
        parsed_enabled = _bool_or_none(enabled)
        if parsed_enabled is not None:
            statement = statement.where(Keyword.enabled.is_(parsed_enabled))
        async with self._session_factory() as session:
            rows, total = await _page(
                session,
                statement.order_by(Keyword.created_at.desc(), Keyword.id.desc()),
                offset=offset,
                limit=limit,
            )
        return EntityPage(
            tuple(
                KeywordView(
                    row.id,
                    row.word,
                    row.enabled,
                    row.created_at,
                    row.updated_at,
                )
                for row in rows
            ),
            total,
        )

    async def get_keyword(self, entity_id: uuid.UUID) -> KeywordView | None:
        async with self._session_factory() as session:
            row = await session.get(Keyword, entity_id)
        return (
            None
            if row is None
            else KeywordView(row.id, row.word, row.enabled, row.created_at, row.updated_at)
        )

    async def list_news(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        status: str,
        source_id: str,
    ) -> EntityPage[NewsView]:
        statement = select(NewsItem, Source.name).join(Source, Source.id == NewsItem.source_id)
        if search:
            statement = statement.where(
                or_(
                    NewsItem.title.ilike(f"%{search}%"),
                    NewsItem.summary.ilike(f"%{search}%"),
                )
            )
        parsed_status = _enum_or_none(NewsStatus, status)
        if parsed_status is not None:
            statement = statement.where(NewsItem.status == parsed_status)
        parsed_source_id = _uuid_or_none(source_id)
        if parsed_source_id is not None:
            statement = statement.where(NewsItem.source_id == parsed_source_id)
        async with self._session_factory() as session:
            count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
            total = int((await session.scalar(count_statement)) or 0)
            rows = (
                await session.execute(
                    statement.order_by(NewsItem.created_at.desc(), NewsItem.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        return EntityPage(tuple(_news_view(news, source_name) for news, source_name in rows), total)

    async def get_news(self, entity_id: uuid.UUID) -> NewsView | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(NewsItem, Source.name)
                    .join(Source, Source.id == NewsItem.source_id)
                    .where(NewsItem.id == entity_id)
                )
            ).one_or_none()
        return None if row is None else _news_view(row[0], row[1])

    async def list_posts(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        status: str,
    ) -> EntityPage[PostView]:
        statement = select(Post, NewsItem.title).join(NewsItem, NewsItem.id == Post.news_id)
        if search:
            statement = statement.where(
                or_(
                    NewsItem.title.ilike(f"%{search}%"),
                    Post.generated_text.ilike(f"%{search}%"),
                )
            )
        parsed_status = _enum_or_none(PostStatus, status)
        if parsed_status is not None:
            statement = statement.where(Post.status == parsed_status)
        async with self._session_factory() as session:
            count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
            total = int((await session.scalar(count_statement)) or 0)
            rows = (
                await session.execute(
                    statement.order_by(Post.updated_at.desc(), Post.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        return EntityPage(tuple(_post_view(post, title) for post, title in rows), total)

    async def get_post(self, entity_id: uuid.UUID) -> PostView | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(Post, NewsItem.title)
                    .join(NewsItem, NewsItem.id == Post.news_id)
                    .where(Post.id == entity_id)
                )
            ).one_or_none()
        return None if row is None else _post_view(row[0], row[1])

    async def list_errors(
        self,
        *,
        offset: int,
        limit: int,
        search: str,
        scope: str,
    ) -> EntityPage[ErrorLogView]:
        statement = select(ErrorLog)
        if search:
            statement = statement.where(ErrorLog.message.ilike(f"%{search}%"))
        parsed_scope = _enum_or_none(ErrorScope, scope)
        if parsed_scope is not None:
            statement = statement.where(ErrorLog.scope == parsed_scope)
        async with self._session_factory() as session:
            rows, total = await _page(
                session,
                statement.order_by(ErrorLog.created_at.desc(), ErrorLog.id.desc()),
                offset=offset,
                limit=limit,
            )
        return EntityPage(tuple(_error_view(row) for row in rows), total)

    async def get_error(self, entity_id: uuid.UUID) -> ErrorLogView | None:
        async with self._session_factory() as session:
            row = await session.get(ErrorLog, entity_id)
        return None if row is None else _error_view(row)


async def _page[T](
    session: AsyncSession,
    statement: Select[tuple[T]],
    *,
    offset: int,
    limit: int,
) -> tuple[list[T], int]:
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int((await session.scalar(count_statement)) or 0)
    rows = list(await session.scalars(statement.offset(offset).limit(limit)))
    return rows, total


def _enum_or_none[T: StrEnum](enum_type: type[T], value: str) -> T | None:
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: str) -> bool | None:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _uuid_or_none(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (AttributeError, TypeError, ValueError):
        return None


def _news_view(row: NewsItem, source_name: str) -> NewsView:
    return NewsView(
        row.id,
        row.title,
        row.url,
        row.summary,
        row.raw_text,
        row.source_id,
        source_name,
        row.status.value,
        row.published_at,
        row.created_at,
    )


def _post_view(row: Post, news_title: str) -> PostView:
    return PostView(
        row.id,
        row.news_id,
        news_title,
        row.generated_text,
        row.status.value,
        row.published_at,
        row.telegram_message_id,
        row.error_message,
        row.created_at,
        row.updated_at,
    )


def _error_view(row: ErrorLog) -> ErrorLogView:
    return ErrorLogView(
        row.id,
        row.scope.value,
        row.message,
        row.details,
        row.source_id,
        row.news_id,
        row.post_id,
        row.created_at,
    )

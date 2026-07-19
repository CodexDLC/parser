"""Тесты SQLAlchemy metadata первого прототипа."""

from typing import cast

from sqlalchemy import Table, UniqueConstraint

from aibot.db.base import Base
from aibot.models.enums import ErrorScope, NewsStatus, PostStatus, SourceType
from aibot.models.error_log import ErrorLog
from aibot.models.keyword import Keyword
from aibot.models.news_item import NewsItem
from aibot.models.post import Post
from aibot.models.source import Source
from aibot.repositories import (
    ErrorLogRepository,
    KeywordRepository,
    NewsRepository,
    PostRepository,
    SourceRepository,
)


def test_metadata_contains_project_tables() -> None:
    """Metadata содержит все таблицы из модели данных."""

    assert set(Base.metadata.tables) == {
        "sources",
        "keywords",
        "news_items",
        "posts",
        "error_logs",
    }


def test_source_has_unique_type_url_constraint() -> None:
    """Source защищен от дублей по паре type/url."""

    source_table = cast(Table, Source.__table__)
    constraints = {
        constraint.name
        for constraint in source_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "uq_sources_type_url" in constraints


def test_keyword_has_lowercase_unique_index() -> None:
    """Keyword имеет уникальный индекс без учета регистра."""

    keyword_table = cast(Table, Keyword.__table__)
    assert "uq_keywords_word_lower" in {index.name for index in keyword_table.indexes}


def test_post_has_partial_unique_published_index() -> None:
    """Post ограничивает один опубликованный пост на одну новость."""

    post_table = cast(Table, Post.__table__)
    assert "uq_posts_one_published_per_news" in {index.name for index in post_table.indexes}


def test_enum_values_match_documented_contract() -> None:
    """Enum-значения совпадают с документацией проекта."""

    assert {item.value for item in SourceType} == {"site", "tg"}
    assert {item.value for item in NewsStatus} == {
        "new",
        "filtered_out",
        "ready_for_generation",
        "generated",
        "failed",
    }
    assert {item.value for item in PostStatus} == {
        "new",
        "generated",
        "publishing",
        "published",
        "failed",
    }
    assert {item.value for item in ErrorScope} == {"parser", "ai", "telegram", "celery", "api"}


def test_repositories_use_expected_models() -> None:
    """Repository-классы привязаны к своим ORM-моделям."""

    assert SourceRepository.model is Source
    assert KeywordRepository.model is Keyword
    assert NewsRepository.model is NewsItem
    assert PostRepository.model is Post
    assert ErrorLogRepository.model is ErrorLog

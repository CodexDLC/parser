"""Pydantic-схемы запросов и ответов API."""

from aibot.api.schemas.keyword import KeywordCreate, KeywordRead, KeywordUpdate
from aibot.api.schemas.news_item import NewsItemRead
from aibot.api.schemas.post import PostRead
from aibot.api.schemas.source import SourceCreate, SourceRead, SourceUpdate

__all__ = [
    "KeywordCreate",
    "KeywordRead",
    "KeywordUpdate",
    "NewsItemRead",
    "PostRead",
    "SourceCreate",
    "SourceRead",
    "SourceUpdate",
]

"""Repository слой для запросов к PostgreSQL через SQLAlchemy."""

from aibot.repositories.base_repository import BaseRepository
from aibot.repositories.error_log_repository import ErrorLogRepository
from aibot.repositories.keyword_repository import KeywordRepository
from aibot.repositories.news_repository import NewsRepository
from aibot.repositories.post_repository import PostRepository
from aibot.repositories.source_repository import SourceRepository

__all__ = [
    "BaseRepository",
    "ErrorLogRepository",
    "KeywordRepository",
    "NewsRepository",
    "PostRepository",
    "SourceRepository",
]

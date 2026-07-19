"""ORM-модели доменных сущностей проекта."""

from aibot.models.error_log import ErrorLog
from aibot.models.keyword import Keyword
from aibot.models.news_item import NewsItem
from aibot.models.post import Post
from aibot.models.source import Source

__all__ = ["ErrorLog", "Keyword", "NewsItem", "Post", "Source"]

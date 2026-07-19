"""Парсеры источников новостей."""

from aibot.parsers.base import NewsParser, ParsedNewsItem
from aibot.parsers.rss import RssAtomParser, RssFeedParseError
from aibot.parsers.sites import DemoSiteParser, StaticHtmlSiteParser

__all__ = [
    "DemoSiteParser",
    "NewsParser",
    "ParsedNewsItem",
    "RssAtomParser",
    "RssFeedParseError",
    "StaticHtmlSiteParser",
]

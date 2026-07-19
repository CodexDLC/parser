"""Парсеры источников новостей."""

from aibot.parsers.base import NewsParser, ParsedNewsItem
from aibot.parsers.sites import DemoSiteParser, StaticHtmlSiteParser

__all__ = ["DemoSiteParser", "NewsParser", "ParsedNewsItem", "StaticHtmlSiteParser"]

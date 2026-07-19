"""Тесты локального parser/filter/dedup pipeline без внешней сети."""

from dataclasses import dataclass

import pytest

from aibot.parsers.sites import DemoSiteParser, StaticHtmlSiteParser
from aibot.services.deduplication import DeduplicationService, build_content_hash
from aibot.services.filtering import KeywordFilterService


@dataclass(frozen=True)
class FakeKeyword:
    """Минимальное ключевое слово для фильтра."""

    word: str
    enabled: bool = True


@pytest.mark.asyncio
async def test_demo_site_parser_returns_news_without_network() -> None:
    """DemoSiteParser возвращает новости без внешних запросов."""

    parser = DemoSiteParser()

    items = await parser.parse(source_name="Demo", url="demo://news", limit=1)

    assert len(items) == 1
    assert "Python" in items[0].title
    assert items[0].url == "demo://news/python-performance"


def test_static_html_site_parser_extracts_articles() -> None:
    """StaticHtmlSiteParser извлекает article-блоки из HTML."""

    html = """
    <article>
      <h2>AI news digest</h2>
      <a href="/ai">Read</a>
      <p>AI helps editors prepare short posts.</p>
    </article>
    """
    parser = StaticHtmlSiteParser()

    items = parser.parse_html(html=html, source_name="Local HTML", base_url="https://example.com")

    assert len(items) == 1
    assert items[0].title == "AI news digest"
    assert items[0].url == "https://example.com/ai"
    assert "short posts" in items[0].summary


@pytest.mark.asyncio
async def test_deduplication_uses_url_and_content_hash() -> None:
    """DeduplicationService находит дубли по URL и hash."""

    parser = DemoSiteParser()
    item = (await parser.parse(source_name="Demo", url="demo://news", limit=1))[0]
    service = DeduplicationService()

    assert service.is_duplicate(item, existing_urls={item.url or ""}, existing_hashes=set())
    assert service.is_duplicate(
        item,
        existing_urls=set(),
        existing_hashes={build_content_hash(item)},
    )
    assert not service.is_duplicate(item, existing_urls=set(), existing_hashes=set())


@pytest.mark.asyncio
async def test_keyword_filter_accepts_matching_news() -> None:
    """KeywordFilterService принимает новости с совпадающим ключевым словом."""

    item = (await DemoSiteParser().parse(source_name="Demo", url="demo://news", limit=1))[0]
    service = KeywordFilterService()

    accepted = service.evaluate(item, [FakeKeyword("python")])
    rejected = service.evaluate(item, [FakeKeyword("telegram")])

    assert accepted.accepted is True
    assert accepted.matched_keywords == ["python"]
    assert rejected.accepted is False
    assert rejected.reason == "no_keyword_match"

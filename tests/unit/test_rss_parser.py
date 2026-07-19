"""Тесты универсального RSS/Atom parser без внешней сети."""

from datetime import UTC, datetime

import pytest

from aibot.parsers.rss import RssAtomParser, RssFeedParseError

RSS_FEED = b"""\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Example RSS</title>
    <link>https://news.example/</link>
    <description>Example feed</description>
    <item>
      <title>Python 3.15 released</title>
      <link>/posts/python-315</link>
      <description><![CDATA[<p>Python became faster.</p>]]></description>
      <pubDate>Sat, 18 Jul 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second item</title>
      <link>https://news.example/posts/second</link>
      <description>Second summary</description>
    </item>
  </channel>
</rss>
"""

ATOM_FEED = b"""\
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom</title>
  <link href="https://atom.example/" />
  <updated>2026-07-18T11:30:00Z</updated>
  <entry>
    <title>AI newsroom update</title>
    <link href="/entries/ai-newsroom" />
    <updated>2026-07-18T11:30:00Z</updated>
    <summary type="html">&lt;p&gt;Editors received new AI tools.&lt;/p&gt;</summary>
  </entry>
</feed>
"""


class FakeHttpClient:
    """Предсказуемый HTTP port для RSS parser."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.requested_urls: list[str] = []

    async def get_bytes(self, url: str) -> bytes:
        self.requested_urls.append(url)
        return self.payload


@pytest.mark.asyncio
async def test_rss_parser_normalizes_rss_items_and_respects_limit() -> None:
    """RSS parser очищает HTML, нормализует URL/дату и применяет limit."""

    http_client = FakeHttpClient(RSS_FEED)
    parser = RssAtomParser(http_client=http_client)

    items = await parser.parse(
        source_name="Example",
        url="https://news.example/feed.xml",
        limit=1,
    )

    assert http_client.requested_urls == ["https://news.example/feed.xml"]
    assert len(items) == 1
    assert items[0].title == "Python 3.15 released"
    assert items[0].url == "https://news.example/posts/python-315"
    assert items[0].summary == "Python became faster."
    assert items[0].source == "Example"
    assert items[0].published_at == datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    assert items[0].raw_text == "Python became faster."


@pytest.mark.asyncio
async def test_rss_parser_normalizes_atom_feed() -> None:
    """Тот же parser поддерживает стандартный Atom feed."""

    parser = RssAtomParser(http_client=FakeHttpClient(ATOM_FEED))

    items = await parser.parse(
        source_name="Atom",
        url="https://atom.example/feed.atom",
    )

    assert len(items) == 1
    assert items[0].title == "AI newsroom update"
    assert items[0].url == "https://atom.example/entries/ai-newsroom"
    assert items[0].summary == "Editors received new AI tools."
    assert items[0].published_at == datetime(2026, 7, 18, 11, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_rss_parser_returns_empty_list_for_valid_empty_feed() -> None:
    """Пустая, но валидная лента не считается сетевой ошибкой."""

    payload = b"<rss version='2.0'><channel><title>Empty</title></channel></rss>"
    parser = RssAtomParser(http_client=FakeHttpClient(payload))

    items = await parser.parse(source_name="Empty", url="https://news.example/feed.xml")

    assert items == []


@pytest.mark.asyncio
async def test_rss_parser_rejects_invalid_payload() -> None:
    """HTML или повреждённый XML не принимается как RSS/Atom."""

    parser = RssAtomParser(http_client=FakeHttpClient(b"<html>not a feed</html>"))

    with pytest.raises(RssFeedParseError):
        await parser.parse(source_name="Broken", url="https://news.example/feed.xml")


@pytest.mark.asyncio
async def test_rss_parser_skips_entry_without_title() -> None:
    """Запись без обязательного заголовка не попадает в ingestion."""

    payload = b"""\
    <rss version="2.0"><channel><title>Feed</title>
      <item><description>No title</description></item>
    </channel></rss>
    """
    parser = RssAtomParser(http_client=FakeHttpClient(payload))

    items = await parser.parse(source_name="Example", url="https://news.example/feed.xml")

    assert items == []

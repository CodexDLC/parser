"""Парсеры новостных сайтов."""

from datetime import UTC, datetime

from bs4 import BeautifulSoup

from aibot.parsers.base import ParsedNewsItem


class DemoSiteParser:
    """Демо-парсер сайта, который работает без внешней сети."""

    async def parse(self, *, source_name: str, url: str, limit: int = 10) -> list[ParsedNewsItem]:
        """Вернуть предсказуемые demo-новости для первого прототипа."""

        items = [
            ParsedNewsItem(
                title="Python получил важное обновление производительности",
                url=f"{url.rstrip('/')}/python-performance",
                summary="Разработчики ускорили несколько популярных сценариев выполнения кода.",
                source=source_name,
                published_at=datetime.now(tz=UTC),
                raw_text="Python release performance update",
            ),
            ParsedNewsItem(
                title="AI помогает редакциям быстрее готовить короткие новости",
                url=f"{url.rstrip('/')}/ai-newsrooms",
                summary="Инструменты генерации текста используют для черновиков и кратких сводок.",
                source=source_name,
                published_at=datetime.now(tz=UTC),
                raw_text="AI newsroom assistant",
            ),
        ]
        return items[:limit]


class StaticHtmlSiteParser:
    """Парсер простого HTML с article-блоками для локальных тестов."""

    def parse_html(
        self,
        *,
        html: str,
        source_name: str,
        base_url: str | None = None,
        limit: int = 10,
    ) -> list[ParsedNewsItem]:
        """Извлечь новости из HTML без сетевого запроса."""

        soup = BeautifulSoup(html, "lxml")
        articles = soup.find_all("article")
        parsed_items: list[ParsedNewsItem] = []

        for article in articles[:limit]:
            title_node = article.find(["h1", "h2", "h3"])
            summary_node = article.find("p")
            link_node = article.find("a", href=True)
            if title_node is None or summary_node is None:
                continue

            href = str(link_node["href"]) if link_node is not None else None
            parsed_items.append(
                ParsedNewsItem(
                    title=title_node.get_text(" ", strip=True),
                    url=self._normalize_url(href=href, base_url=base_url),
                    summary=summary_node.get_text(" ", strip=True),
                    source=source_name,
                    published_at=datetime.now(tz=UTC),
                    raw_text=article.get_text(" ", strip=True),
                )
            )

        return parsed_items

    def _normalize_url(self, *, href: str | None, base_url: str | None) -> str | None:
        """Нормализовать относительную ссылку article-блока."""

        if not href:
            return None
        if href.startswith(("http://", "https://")):
            return href
        if base_url is None:
            return href
        return f"{base_url.rstrip('/')}/{href.lstrip('/')}"

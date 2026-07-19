"""Локальный демонстрационный pipeline без базы, сети и реальных ключей."""

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any

from aibot.config import Settings, get_settings
from aibot.integrations.telegram_client import TelegramClient
from aibot.parsers.sites import DemoSiteParser
from aibot.services.deduplication import DeduplicationService, build_content_hash
from aibot.services.filtering import KeywordFilterService
from aibot.services.post_generation import PostGenerationService


@dataclass(frozen=True)
class DemoKeyword:
    """Ключевое слово для локального demo-фильтра."""

    word: str
    enabled: bool = True


@dataclass(frozen=True)
class DemoGeneratedPost:
    """Результат генерации и dry-run публикации одной новости."""

    title: str
    source_url: str | None
    matched_keywords: list[str]
    generated_text: str
    telegram_message_id: str


@dataclass(frozen=True)
class DemoPipelineResult:
    """Сводка локального demo-pipeline."""

    source_name: str
    source_url: str
    fake_mode: bool
    telegram_dry_run: bool
    parsed_count: int
    duplicate_count: int
    filtered_out_count: int
    accepted_count: int
    generated_count: int
    published_count: int
    posts: list[DemoGeneratedPost]


async def run_demo_pipeline(
    *,
    limit: int = 10,
    settings: Settings | None = None,
) -> DemoPipelineResult:
    """Прогнать локальный сценарий: parse -> dedupe -> filter -> generate -> publish."""

    runtime_settings = settings or get_settings()
    source_name = "Demo News"
    source_url = "https://example.test/news"
    keywords = [DemoKeyword("python"), DemoKeyword("ai")]

    parser = DemoSiteParser()
    deduplication_service = DeduplicationService()
    filter_service = KeywordFilterService()
    generation_service = PostGenerationService(runtime_settings)
    telegram_client = TelegramClient(runtime_settings)

    parsed_items = await parser.parse(source_name=source_name, url=source_url, limit=limit)
    existing_urls: set[str] = set()
    existing_hashes: set[str] = set()
    posts: list[DemoGeneratedPost] = []
    duplicate_count = 0
    filtered_out_count = 0

    for parsed_item in parsed_items:
        content_hash = build_content_hash(parsed_item)
        if deduplication_service.is_duplicate(
            parsed_item,
            existing_urls=existing_urls,
            existing_hashes=existing_hashes,
        ):
            duplicate_count += 1
            continue

        if parsed_item.url:
            existing_urls.add(parsed_item.url)
        existing_hashes.add(content_hash)

        filter_decision = filter_service.evaluate(parsed_item, keywords)
        if not filter_decision.accepted:
            filtered_out_count += 1
            continue

        generated_text = await generation_service.generate_manual_post(
            parsed_item.text_for_filtering
        )
        telegram_message_id = await telegram_client.publish_message(generated_text)
        posts.append(
            DemoGeneratedPost(
                title=parsed_item.title,
                source_url=parsed_item.url,
                matched_keywords=filter_decision.matched_keywords,
                generated_text=generated_text,
                telegram_message_id=telegram_message_id,
            )
        )

    accepted_count = len(posts)
    return DemoPipelineResult(
        source_name=source_name,
        source_url=source_url,
        fake_mode=runtime_settings.ai_fake_mode,
        telegram_dry_run=runtime_settings.telegram_dry_run,
        parsed_count=len(parsed_items),
        duplicate_count=duplicate_count,
        filtered_out_count=filtered_out_count,
        accepted_count=accepted_count,
        generated_count=accepted_count,
        published_count=accepted_count,
        posts=posts,
    )


def result_to_dict(result: DemoPipelineResult) -> dict[str, Any]:
    """Преобразовать результат demo-pipeline в JSON-friendly словарь."""

    return asdict(result)


def build_arg_parser() -> argparse.ArgumentParser:
    """Создать CLI parser для локального demo-сценария."""

    parser = argparse.ArgumentParser(description="Run Project M4 local dry-run demo pipeline.")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of demo news items to parse.",
    )
    return parser


def main() -> None:
    """Запустить demo-pipeline из командной строки."""

    args = build_arg_parser().parse_args()
    result = asyncio.run(run_demo_pipeline(limit=args.limit))
    print(json.dumps(result_to_dict(result), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

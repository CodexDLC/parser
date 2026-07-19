"""Изолированный запуск парсинга всех включённых источников."""

import uuid
from dataclasses import dataclass

from aibot.repositories.source_repository import SourceRepository
from aibot.services.news_ingestion import NewsIngestionService, SourceParseResult


@dataclass(frozen=True)
class SourceParseFailure:
    """Безопасная сводка сбоя одного источника."""

    source_id: uuid.UUID
    error_type: str


@dataclass(frozen=True)
class SourceBatchParseResult:
    """Сводка успешных и неуспешных запусков источников."""

    successful: list[SourceParseResult]
    failed: list[SourceParseFailure]


class SourceBatchParsingService:
    """Обработать включённые источники независимо друг от друга."""

    def __init__(
        self,
        *,
        source_repository: SourceRepository,
        ingestion_service: NewsIngestionService,
    ) -> None:
        self.source_repository = source_repository
        self.ingestion_service = ingestion_service

    async def parse_enabled_sources(self, *, limit: int = 10) -> SourceBatchParseResult:
        """Продолжить batch после сбоя отдельного источника."""

        sources = await self.source_repository.list_filtered(enabled=True)
        successful: list[SourceParseResult] = []
        failed: list[SourceParseFailure] = []

        for source in sources:
            try:
                result = await self.ingestion_service.parse_source(source.id, limit=limit)
            except Exception as exc:
                failed.append(
                    SourceParseFailure(
                        source_id=source.id,
                        error_type=exc.__class__.__name__,
                    )
                )
                continue
            successful.append(result)

        return SourceBatchParseResult(successful=successful, failed=failed)

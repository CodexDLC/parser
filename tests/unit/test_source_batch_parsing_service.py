"""Тесты изоляции ошибок при групповом парсинге источников."""

import uuid
from dataclasses import dataclass

import pytest

from aibot.integrations.http_client import HttpTemporaryError
from aibot.services.news_ingestion import SourceParseResult
from aibot.services.source_batch_parsing import (
    SourceBatchParseResult,
    SourceBatchParsingService,
    SourceParseFailure,
)
from aibot.tasks.parsing import _serialize_batch_result


@dataclass(frozen=True)
class FakeSource:
    """Минимальный источник для batch service."""

    id: uuid.UUID


class FakeSourceRepository:
    """Вернуть два включённых источника."""

    failed_source_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    successful_source_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    async def list_filtered(self, **_: object) -> list[FakeSource]:
        return [
            FakeSource(self.failed_source_id),
            FakeSource(self.successful_source_id),
        ]


class FakeNewsIngestionService:
    """Первый источник завершить ошибкой, второй успешно обработать."""

    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []

    async def parse_source(
        self,
        source_id: uuid.UUID,
        *,
        limit: int = 10,
    ) -> SourceParseResult:
        self.calls.append(source_id)
        assert limit == 7
        if source_id == FakeSourceRepository.failed_source_id:
            raise HttpTemporaryError("contains-sensitive-query")
        return SourceParseResult(
            source_id=source_id,
            parsed_count=3,
            saved_count=2,
            duplicate_count=1,
            filtered_out_count=1,
            ready_for_generation_count=1,
        )


@pytest.mark.asyncio
async def test_batch_parsing_continues_after_source_failure() -> None:
    """Сбой одного источника не останавливает обработку остальных."""

    ingestion_service = FakeNewsIngestionService()
    service = SourceBatchParsingService(
        source_repository=FakeSourceRepository(),  # type: ignore[arg-type]
        ingestion_service=ingestion_service,  # type: ignore[arg-type]
    )

    result = await service.parse_enabled_sources(limit=7)

    assert ingestion_service.calls == [
        FakeSourceRepository.failed_source_id,
        FakeSourceRepository.successful_source_id,
    ]
    assert [item.source_id for item in result.successful] == [
        FakeSourceRepository.successful_source_id
    ]
    assert result.failed[0].source_id == FakeSourceRepository.failed_source_id
    assert result.failed[0].error_type == "HttpTemporaryError"
    assert "sensitive" not in repr(result.failed[0])


def test_batch_task_payload_does_not_expose_exception_message() -> None:
    """Celery result содержит тип сбоя, но не исходный текст исключения."""

    result = SourceBatchParseResult(
        successful=[],
        failed=[
            SourceParseFailure(
                source_id=FakeSourceRepository.failed_source_id,
                error_type="HttpTemporaryError",
            )
        ],
    )

    payload = _serialize_batch_result(result)

    assert payload == [
        {
            "source_id": str(FakeSourceRepository.failed_source_id),
            "status": "failed",
            "error_type": "HttpTemporaryError",
        }
    ]
    assert "contains-sensitive-query" not in repr(payload)

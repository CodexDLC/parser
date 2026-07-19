"""Тест локального demo-pipeline с внедрённым AI test double."""

import pytest

from aibot.config import Settings
from aibot.demo import run_demo_pipeline


class FakeAIClient:
    """Предсказуемый AI test double без runtime fake-настроек."""

    async def generate_telegram_post(self, input_text: str) -> str:
        return f"Generated: {input_text}"


@pytest.mark.anyio
async def test_demo_pipeline_runs_without_real_credentials() -> None:
    """Демо проходит через тестовый AI port и Telegram dry-run."""

    settings = Settings(telegram_dry_run=True)

    result = await run_demo_pipeline(
        settings=settings,
        ai_client=FakeAIClient(),  # type: ignore[arg-type]
    )

    assert result.telegram_dry_run is True
    assert result.parsed_count == 2
    assert result.duplicate_count == 0
    assert result.filtered_out_count == 0
    assert result.accepted_count == 2
    assert result.generated_count == 2
    assert result.published_count == 2
    assert [post.matched_keywords for post in result.posts] == [["python"], ["ai"]]
    assert all(post.generated_text.startswith("Generated: ") for post in result.posts)
    assert all(post.telegram_message_id.startswith("dry-run-") for post in result.posts)

"""Тест локального demo-pipeline без базы, сети и ключей."""

import pytest

from aibot.config import Settings
from aibot.demo import run_demo_pipeline


@pytest.mark.anyio
async def test_demo_pipeline_runs_without_real_credentials() -> None:
    """Демо-сценарий проходит через parse/filter/generate/publish в dry-run режиме."""

    settings = Settings(ai_fake_mode=True, telegram_dry_run=True)

    result = await run_demo_pipeline(settings=settings)

    assert result.fake_mode is True
    assert result.telegram_dry_run is True
    assert result.parsed_count == 2
    assert result.duplicate_count == 0
    assert result.filtered_out_count == 0
    assert result.accepted_count == 2
    assert result.generated_count == 2
    assert result.published_count == 2
    assert [post.matched_keywords for post in result.posts] == [["python"], ["ai"]]
    assert all(post.generated_text.startswith("📰 ") for post in result.posts)
    assert all(post.telegram_message_id.startswith("dry-run-") for post in result.posts)

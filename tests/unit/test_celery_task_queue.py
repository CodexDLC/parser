"""Тесты Celery adapter-а постановки тяжёлых задач."""

import uuid
from types import SimpleNamespace

import pytest

from aibot.integrations.celery_task_queue import CeleryTaskQueue


def test_celery_task_queue_serializes_api_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adapter передаёт Celery только JSON-совместимые аргументы."""

    source_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    news_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    post_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def fake_delay(name: str, task_id: str):
        def delay(*args: object, **kwargs: object) -> SimpleNamespace:
            calls.append((name, args, kwargs))
            return SimpleNamespace(id=task_id)

        return delay

    monkeypatch.setattr(
        "aibot.integrations.celery_task_queue.parse_source.delay",
        fake_delay("parse_source", "parse-id"),
    )
    monkeypatch.setattr(
        "aibot.integrations.celery_task_queue.generate_post.delay",
        fake_delay("generate_post", "generate-id"),
    )
    monkeypatch.setattr(
        "aibot.integrations.celery_task_queue.publish_post.delay",
        fake_delay("publish_post", "publish-id"),
    )
    monkeypatch.setattr(
        "aibot.integrations.celery_task_queue.generate_text.delay",
        fake_delay("generate_text", "manual-id"),
    )

    queue = CeleryTaskQueue()

    assert queue.enqueue_source_parsing(source_id, limit=4) == "parse-id"
    assert queue.enqueue_news_generation(news_id) == "generate-id"
    assert queue.enqueue_post_publication(post_id) == "publish-id"
    assert queue.enqueue_manual_generation("Python release") == "manual-id"
    assert calls == [
        ("parse_source", (str(source_id),), {"limit": 4}),
        ("generate_post", (str(news_id),), {}),
        ("publish_post", (str(post_id),), {}),
        ("generate_text", ("Python release",), {}),
    ]

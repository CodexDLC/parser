---
name: m4-celery-pipeline
description: Celery and background workflow rules for Project M4. Use when creating or editing Celery app setup, scheduled tasks, parsing/generation/publishing tasks, retry behavior, task chains, Redis broker/backend configuration, or async processing status updates.
---

# M4 Celery Pipeline

## Required Context

Before Celery or pipeline changes, read:

- `docs/celery-pipeline.md`
- `docs/architecture.md`
- `docs/data-model.md`

## Task Design Rules

- Keep Celery tasks thin.
- Put reusable business logic in services.
- Make tasks idempotent where practical.
- Store task results in the database through domain entities, not only in Celery backend.
- Log start, success, counts, and failures.

## Required Tasks

Maintain these logical tasks:

- `parse_enabled_sources`
- `parse_source(source_id)`
- `filter_news(news_id)`
- `generate_post(news_id)`
- `publish_post(post_id)`

Names may vary in code, but responsibilities should stay separate.

## Retry Rules

- Retry temporary parser network errors.
- Retry AI rate limits and timeouts with backoff.
- Retry temporary Telegram errors.
- Do not retry validation errors or missing database rows endlessly.

## Schedule Rules

- Configure Celery Beat to parse enabled sources every 30 minutes.
- Keep schedule values configurable if simple to do.

## Status Rules

- Update `NewsItem.status` and `Post.status` as the pipeline moves.
- A failed task should record an `ErrorLog` entry where possible.
- `publish_post` must not publish a post that is already `published`.


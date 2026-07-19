---
name: m4-api
description: FastAPI API design rules for Project M4. Use when creating or editing endpoints, Pydantic schemas, request/response contracts, Swagger-facing behavior, API errors, or manual control endpoints for sources, keywords, news, posts, generation, publication, logs, and healthchecks.
---

# M4 API

## Required Context

Before API changes, read:

- `docs/api-design.md`
- `docs/data-model.md`
- `docs/architecture.md`

## Endpoint Rules

- Use `/api` as the API prefix.
- Keep CRUD endpoints predictable and REST-like.
- Return JSON responses only.
- Keep endpoints thin: validate input, call a service, return a schema.
- Use Celery for slow operations and return `task_id` where appropriate.

## Core Endpoints

Implement and maintain these API groups:

- `/api/health`
- `/api/sources/`
- `/api/keywords/`
- `/api/news/`
- `/api/posts/`
- `/api/generate/`
- `/api/logs/`

## Error Rules

- Use `404` for missing entities.
- Use `409` for duplicate or already-published conflicts.
- Use `422` for validation errors through FastAPI/Pydantic.
- Do not expose secrets, session paths, raw tracebacks, or API keys in responses.

## Schema Rules

- Separate create, update, read, and list schemas when fields differ.
- Put schemas in `src/aibot/api/schemas/`, grouped by entity or feature, not in one large `schemas.py`.
- Do not accept server-managed fields like `id`, `created_at`, `updated_at`, or `status` in create payloads unless explicitly needed.
- Include status fields in read schemas for `NewsItem` and `Post`.

## Swagger Rules

- Add concise summaries/descriptions when endpoint purpose is not obvious.
- Keep example payloads aligned with `docs/api-design.md`.

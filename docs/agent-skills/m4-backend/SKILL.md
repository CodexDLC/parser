---
name: m4-backend
description: Backend architecture rules for Project M4, the FastAPI/Celery AI Telegram news generator. Use when creating or editing backend structure, configuration, database models, services, repositories, tests, or shared application code in this project.
---

# M4 Backend

## Required Context

Before backend changes, read:

- `docs/index.md`
- `docs/project-brief.md`
- `docs/architecture.md`
- `docs/data-model.md`
- `docs/development-plan.md`

## Architecture Rules

- Keep FastAPI endpoints thin.
- Use Python 3.12 for this project.
- Keep package and tool dependencies in `pyproject.toml`.
- Use PostgreSQL as the project database.
- Use `src/aibot/` as the Python package root.
- Prefer a modular file layout: one main class, entity, repository, service, parser, or integration client per Python file.
- Put SQLAlchemy models in `src/aibot/models/`, with one model per file.
- Put database setup in `src/aibot/db/`.
- Put repositories in `src/aibot/repositories/`, with one repository per main entity.
- Put business logic in `src/aibot/services/`.
- Put external API wrappers in `src/aibot/integrations/`.
- Put parsers in `src/aibot/parsers/`.
- Put Celery tasks in `src/aibot/tasks/`.
- Do not call OpenAI, Telethon, or network parsers directly from SQLAlchemy models.
- Do not put long-running work directly inside HTTP handlers unless the endpoint is explicitly a small manual test endpoint.

## Data Rules

- Persist `Source`, `Keyword`, `NewsItem`, `Post`, and `ErrorLog`.
- Use PostgreSQL-friendly types: UUID primary keys, timezone-aware timestamps, explicit unique constraints, and indexed lookup fields.
- Use explicit statuses for processing state.
- Protect against duplicates with URL uniqueness and content hash uniqueness.
- Store external errors in `ErrorLog` when they affect a source, news item, or post.

## Configuration Rules

- Read runtime settings from environment variables.
- Commit `.env.example`, never real `.env` secrets.
- Add safe dry-run or fake modes for AI and Telegram integrations.

## Implementation Order

Prefer this order:

1. Project skeleton and healthcheck.
2. Configuration and PostgreSQL database.
3. Models, schemas, and repositories.
4. CRUD API.
5. Parsers and filtering.
6. AI generation.
7. Celery tasks.
8. Telegram publishing.

## Verification

After backend changes, run the narrowest useful check:

- import/startup check for app wiring;
- API smoke check for endpoints;
- focused tests for changed services when tests exist.

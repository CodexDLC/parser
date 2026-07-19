---
name: m4-integrations
description: External integration rules for Project M4. Use when creating or editing OpenAI-compatible AI generation, Telethon Telegram parsing or publishing, website parsers, external API clients, prompts, dry-run modes, secrets handling, or integration error handling.
---

# M4 Integrations

## Required Context

Before integration changes, read:

- `docs/integrations.md`
- `docs/celery-pipeline.md`
- `docs/data-model.md`

## General Rules

- Isolate external SDK details in `src/aibot/integrations/`.
- Keep parser-specific HTML or Telegram details out of services.
- Never commit real API keys, Telegram sessions, tokens, or `.env`.
- Add dry-run or fake modes where useful for local demo and tests.

## AI Rules

- Build prompts in one place.
- Keep generated posts concise and fact-preserving.
- Handle rate limit, timeout, auth, invalid response, and empty response errors.
- Do not publish if AI generation failed.

## Telegram Rules

- Separate reading source channels from publishing to the target channel.
- Protect against duplicate publishing.
- Store `telegram_message_id` after successful publication.
- Support `TELEGRAM_DRY_RUN=true`.

## Parser Rules

- Return normalized news items from parsers.
- Include `title`, optional `url`, `summary`, `source`, `published_at`, and optional `raw_text`.
- Limit how many items a parser processes in one run.
- Deduplicate outside the parser layer using URL and content hash.

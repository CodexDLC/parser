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
- Keep `TELEGRAM_DRY_RUN` for safe publishing.
- Do not add an AI runtime fake mode; inject test doubles through the AI port in tests.

## AI Rules

- Use `codex-ai[openai]==0.2.5` as the only runtime AI provider.
- Read the OpenAI key from `OPENAI_API_KEY` and the model from `OPENAI_MODEL`.
- Build prompts in one place.
- Keep generated posts concise and fact-preserving.
- Handle rate limit, timeout, auth, invalid response, and empty response errors.
- Do not publish if AI generation failed.

## Telegram Rules

- Separate reading source channels from publishing to the target channel.
- Keep Telethon reader and Telethon publisher for the required Project M4 contract.
- Allow `TELEGRAM_PUBLISHER=bot_api` as an explicit alternative for publication only.
- Select exactly one publisher through the factory; never fall back between Telegram
  adapters after an error.
- Bot API publication must not require a Telethon session unless a `tg` source is read.
- Protect against duplicate publishing.
- Store `telegram_message_id` after successful publication.
- Support `TELEGRAM_DRY_RUN=true`.

## Parser Rules

- Return normalized news items from parsers.
- Include `title`, optional `url`, `summary`, `source`, `published_at`, and optional `raw_text`.
- Limit how many items a parser processes in one run.
- Deduplicate outside the parser layer using URL and content hash.

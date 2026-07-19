# Integration Verification Report

Дата проверки: 2026-07-19.

## OpenAI

- Runtime provider: `codex-ai==0.2.5`.
- Настроенная модель: `gpt-5.6-terra`.
- `OPENAI_API_KEY` присутствует; значение не выводилось и не сохранялось в отчёт.
- Production-запрос дошёл до OpenAI Responses API.
- Adapter корректно классифицировал ответ как `AIClientRateLimitError`.
- Успешная генерация заблокирована состоянием API quota, а не кодом M4.

Повторная проверка после пополнения quota:

```powershell
uv run python -m aibot.verify_integrations --service openai
```

## Telegram

Текущая локальная конфигурация:

- `TELEGRAM_DRY_RUN=true`;
- `TELEGRAM_PUBLISHER=telethon` по умолчанию;
- `TELEGRAM_API_ID` не настроен;
- `TELEGRAM_API_HASH` не настроен;
- `TELEGRAM_TARGET_CHANNEL` не настроен;
- авторизованная Telethon session отсутствует.

Поэтому реальное чтение и публикация не выполнялись. Dry-run чтение и публикация
покрыты автоматическими тестами. Production client переведён на неинтерактивное
подключение: worker не запрашивает телефон или код и возвращает типизированную ошибку,
если session не авторизована.

После этой проверки integration boundary расширена без отмены исходного контракта:

- Telethon reader и publisher разделены;
- добавлен `TELEGRAM_PUBLISHER=bot_api`;
- Bot API publisher использует `TELEGRAM_BOT_TOKEN` и общий
  `TELEGRAM_TARGET_CHANNEL`;
- publisher factory не делает fallback между adapters;
- live-verifier не требует Telethon session для Bot API, пока не передан
  `--telegram-source`.

Реальный Bot API вызов ещё не выполнялся: BotFather token и тестовый канал не
предоставлены. Этот пункт остаётся внешним prerequisite, а не считается пройденным.

После заполнения настроек:

```powershell
uv run python -m aibot.authorize_telegram
uv run python -m aibot.verify_integrations --service telegram --telegram-source @public_channel
uv run python -m aibot.verify_integrations --service telegram --publish-telegram-test
```

Последняя команда действительно отправляет один тестовый пост в настроенный целевой
канал и должна запускаться только намеренно.

Для Bot API режима авторизация session не нужна:

```powershell
$env:TELEGRAM_PUBLISHER = "bot_api"
uv run python -m aibot.verify_integrations --service telegram
uv run python -m aibot.verify_integrations --service telegram --publish-telegram-test
```

Если вместе с Bot API используется `Source(type="tg")`, команда
`aibot.authorize_telegram` и Telethon credentials всё равно обязательны для reader-а.

## Безопасность результата

Verifier не выводит:

- API keys и Telegram credentials;
- provider exception message и request ID;
- prompt или AI-generated text;
- Telegram account details.

Ненулевой exit code используется для `blocked` и `failed`, поэтому verifier можно
подключить к ручному pre-production checklist.

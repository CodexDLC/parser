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
- `TELEGRAM_API_ID` не настроен;
- `TELEGRAM_API_HASH` не настроен;
- `TELEGRAM_TARGET_CHANNEL` не настроен;
- авторизованная Telethon session отсутствует.

Поэтому реальное чтение и публикация не выполнялись. Dry-run чтение и публикация
покрыты автоматическими тестами. Production client переведён на неинтерактивное
подключение: worker не запрашивает телефон или код и возвращает типизированную ошибку,
если session не авторизована.

После заполнения настроек:

```powershell
uv run python -m aibot.authorize_telegram
uv run python -m aibot.verify_integrations --service telegram --telegram-source @public_channel
uv run python -m aibot.verify_integrations --service telegram --publish-telegram-test
```

Последняя команда действительно отправляет один тестовый пост в настроенный целевой
канал и должна запускаться только намеренно.

## Безопасность результата

Verifier не выводит:

- API keys и Telegram credentials;
- provider exception message и request ID;
- prompt или AI-generated text;
- Telegram account details.

Ненулевой exit code используется для `blocked` и `failed`, поэтому verifier можно
подключить к ручному pre-production checklist.

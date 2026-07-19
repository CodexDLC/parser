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

После этой проверки runtime расширен Gemini fallback без удаления OpenAI:

- `AI_PROVIDER=openai`;
- `AI_FALLBACK_PROVIDER=gemini`;
- Gemini model по умолчанию — `gemini-3.5-flash`;
- `GEMINI_API_KEY` присутствует; значение не выводилось и не сохранялось в отчёт;
- после OpenAI `429 insufficient_quota` fallback получил Gemini `200 OK`;
- создан Post со статусом `generated`, а связанная NewsItem переведена в `generated`.
- после обнаружения усечённых reasoning-ответов output budget увеличен до 2048;
- короткий, незавершённый или размеченный AI-ответ теперь блокируется до сохранения;
- реальный Gemini preview повторно проверен: 722 символа, plain text и исходная
  HTTP(S)-ссылка из `NewsItem.url`.

Имя `--service openai` сохранено для совместимости verifier CLI, но команда проходит
через общую AI chain.

## Telegram

Локальная real-mode проверка выполнена:

- `TELEGRAM_PUBLISHER=telethon`;
- `TELEGRAM_DRY_RUN=false`;
- API credentials и target channel настроены без сохранения значений в отчёте;
- Telethon session авторизована и хранится в отдельном Compose volume;
- verifier успешно отправил одно контрольное сообщение;
- полный pipeline успешно выполнил реальные публикации и сохранил message ID.

Worker использует session неинтерактивно и не запрашивает телефон или код. Dry-run
чтение и публикация дополнительно покрыты автоматическими тестами.

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

Повторная ручная проверка:

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

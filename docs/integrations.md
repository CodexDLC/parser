# Integrations

## AI API

AI-интеграция изолирована в `src/aibot/integrations/`. Runtime использует
`codex-ai[openai,gemini]==0.2.5`. `AI_PROVIDER` задаёт основной provider,
`AI_FALLBACK_PROVIDER` — резервный. По умолчанию цепочка равна
`openai -> gemini`.

OpenAI читает `OPENAI_API_KEY`, `OPENAI_MODEL` (`gpt-5.6-terra`) и
`OPENAI_TIMEOUT_SECONDS`. Gemini читает `GEMINI_API_KEY` и `GEMINI_MODEL`
(`gemini-3.5-flash`). Общий `AI_MAX_OUTPUT_TOKENS=2048` оставляет reasoning-модели
достаточный budget для формирования законченного ответа.

`ai_provider_factory.py` строит только provider-ы с настроенными credentials.
`ai_fallback_provider.py` вызывает Gemini после `LLMProviderError` OpenAI, но никогда
не вызывает fallback после успешного primary-ответа. Если primary key отсутствует,
а fallback key заполнен, используется единственный настроенный provider.

Доменный сервис не должен знать детали конкретного SDK. Он должен вызывать метод уровня:

```python
generate_telegram_post(input_text: str) -> str
```

## Prompt

Базовый prompt:

```text
Подготовь законченный информационный пост для русскоязычного Telegram-канала.
Сохрани факты и не выдумывай подробности.
Добавь 1-3 emoji, короткий заголовок, 2-3 абзаца и короткий призыв.
Верни 350-700 символов обычного текста без Markdown/HTML.
Обязательно закончи последнее предложение знаком пунктуации.
```

Правила:

- не отправлять пустой или короче 180 символов текст;
- не просить модель публиковать непроверенные факты;
- отклонять ответы длиннее 900 символов, с Markdown/HTML или незавершённой фразой;
- сохранять ссылку на источник отдельно, а не заставлять модель придумывать ссылку.

`PlainTextTelegramPostValidator` применяется на AI integration boundary до создания
`Post`. Невалидный ответ преобразуется в `AIClientInvalidResponseError`, записывается
как AI failure и не достигает Telegram.

После валидации `TelegramPostComposer` формирует сохранённый `Post.generated_text`:
к AI-тексту добавляется блок `🔗 Источник` с исходным `NewsItem.url`. Принимаются
только абсолютные HTTP(S)-адреса; при отсутствующей или неподдерживаемой ссылке
сохраняется только AI-текст. Поэтому preview кабинета полностью совпадает с будущим
сообщением Telegram.

## Ошибки AI

Обрабатывать отдельно:

- rate limit;
- timeout;
- authentication error;
- invalid response;
- empty response.

При ошибке нужно:

- записать `ErrorLog(scope="ai")`;
- не публиковать пост.

Успешный fallback считается успешной генерацией и не создаёт `ErrorLog`. Ошибка
передаётся сервису и Celery только после того, как доступная provider chain не смогла
вернуть результат.

`PostGenerationService` сохраняет `news_id`, короткое сообщение
`AI generation failed` и только имя класса исключения в `details`. Текст provider
exception и traceback не сохраняются, потому что могут содержать credentials или
служебные данные. Исходное исключение пробрасывается Celery для retry временных ошибок.

News остаётся `ready_for_generation` после временной AI-ошибки, чтобы Celery retry или
повторный ручной запуск могли снова обработать её.

## Telegram boundaries

Чтение источников и публикация разделены application ports:

1. `TelethonChannelReader` читает публичные Telegram-каналы.
2. `TelethonPublisher` публикует через user session и сохраняет обязательный
   контракт исходного задания.
3. `TelegramBotPublisher` публикует через Bot HTTP API без user session.

`TELEGRAM_PUBLISHER` выбирает ровно один publication adapter. Автоматического
fallback между Telethon и Bot API нет: ошибка выбранного provider-а должна завершать
операцию, а не создавать риск второй отправки через другой adapter.

## Telegram настройки

Ожидаемые переменные окружения:

```text
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_SESSION_NAME=
TELEGRAM_PUBLISHER=telethon
TELEGRAM_BOT_TOKEN=
TELEGRAM_TARGET_CHANNEL=
TELEGRAM_DRY_RUN=true
TELEGRAM_TIMEOUT_SECONDS=15
```

В репозиторий нельзя коммитить реальные session-файлы и секреты.

`TELEGRAM_PUBLISHER=telethon` является default и используется для демонстрации
Project M4. `TELEGRAM_PUBLISHER=bot_api` подходит для RSS/Atom ingestion и
односторонней публикации в собственный канал. Bot token создаётся через `@BotFather`,
а бот получает только право публикации в target channel.

Bot API не является reader-ом произвольных публичных каналов. Любой
`Source(type="tg")` по-прежнему требует `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` и
заранее авторизованную Telethon session независимо от publication adapter.

## HTTP-клиент

`src/aibot/integrations/http_client.py` отвечает только за сетевую загрузку:

- разрешает HTTP/HTTPS-запрос через `httpx`;
- применяет timeout и явный User-Agent;
- ограничивает размер уже распакованного ответа;
- удаляет query-параметры из сообщений об ошибках;
- разделяет временные и постоянные ошибки.

HTTP-клиент не выполняет собственные retries. Он возвращает типизированную временную
ошибку, а retry/backoff принадлежит Celery-задаче, чтобы избежать умножения попыток.

## Парсинг RSS/Atom

Production parser для источника `type="site"` — универсальный `RssAtomParser`.
В `Source.url` хранится прямой URL RSS/Atom-ленты.

Правила:

- parser поддерживает стандартные RSS и Atom feeds;
- записи без заголовка пропускаются;
- HTML в title/summary преобразуется в обычный текст;
- относительные ссылки нормализуются относительно URL ленты;
- отсутствующая дата заменяется временем получения ленты;
- парсер должен иметь лимит количества новостей за один запуск.

`DemoSiteParser` используется только через явное внедрение в unit/integration/smoke
сценариях. Production ingestion не имеет fallback на demo-данные.

HTML-парсеры конкретных сайтов не входят в текущий этап.

## Ошибки парсинга

`NewsIngestionService` сохраняет ошибки внешнего parser-а в `ErrorLog`:

- `scope="parser"`;
- `source_id` указывает на проблемный источник;
- timeout и временные HTTP-ошибки классифицируются отдельно от постоянных;
- некорректная RSS/Atom-лента получает отдельную категорию;
- исходный тип исключения сохраняется для будущей Celery retry-политики.

Сообщения HTTP/RSS parser-ов уже содержат URL без query и могут сохраняться в
`details`. Для неизвестного исключения сохраняется только имя класса — без исходного
текста, traceback, API-ключей, session-данных и других потенциальных секретов.

## Языковая фильтрация

`LanguageDetector` использует `langdetect` с фиксированным seed и возвращает
нормализованный ISO language code. Разрешённые языки задаются через:

```text
NEWS_ALLOWED_LANGUAGES=ru,en
```

Порядок применения правил:

1. определить язык по `title + summary + raw_text`;
2. отклонить неизвестный язык как `language_unknown`;
3. отклонить запрещённый язык как `language_not_allowed`;
4. только после этого проверить включённые ключевые слова.

Определение языка и filter decision не зависят от конкретного RSS/Telegram parser.

## Парсинг Telegram-каналов

Правила:

- читать только публичные каналы, добавленные как `Source(type="tg")`;
- сохранять исходный текст в `raw_text`;
- если URL новости отсутствует, дедуплицировать по hash текста;
- не публиковать обратно в источник, из которого читаем, если это не целевой канал.

## Безопасная работа с внешними сервисами

Для Telegram сохраняется безопасный режим:

- `TELEGRAM_DRY_RUN=true` - не подключать reader и не отправлять реальные сообщения;
- Bot API token и Telethon session никогда не копируются в `ErrorLog`;
- timeout/невалидный ответ после `sendMessage` классифицируется как неопределённый
  результат и не получает автоматический fallback на Telethon.

У AI нет runtime fake-режима: отсутствие credentials у всех выбранных provider-ов
является ошибкой конфигурации. Unit, integration и acceptance-тесты внедряют test
double через AI port, поэтому не выполняют внешних запросов и не расходуют токены.

## Operational verification

`python -m aibot.verify_integrations` использует production adapters и возвращает
только безопасные метаданные:

- `service`;
- `passed`, `blocked` или `failed`;
- имя класса ошибки без исходного provider message;
- длину AI-ответа, число прочитанных Telegram-сообщений или ID явно запрошенной
  test-публикации.

Telegram real-mode разделён на независимые операции:

1. `python -m aibot.authorize_telegram` — явно интерактивное создание session.
2. `--service telegram` — проверка выбранного publisher без отправки.
3. `--telegram-source` — дополнительная проверка Telethon reader.
4. `--publish-telegram-test` — явная публикация через выбранный publisher.

В режиме `bot_api` publisher verification использует только безопасные `getMe` и
`getChat`; Telethon не вызывается, если `--telegram-source` не передан. Это исключает
зависание фонового процесса на запросе номера телефона или кода. Test-публикация
выполняется только с явным `--publish-telegram-test`.

В контейнерном runtime первичная Telethon-авторизация выполняется отдельным
интерактивным tool-service при остановленном Worker:

```powershell
docker compose --profile tools run --rm telegram-auth
```

Session сохраняется в отдельном named volume и монтируется только в singleton Worker
и `telegram-auth`. API и Beat не получают доступ к session-файлу. Для проверки
интеграции из того же image Worker предварительно останавливают, чтобы не открывать
SQLite session параллельно:

```powershell
docker compose stop worker
docker compose run --rm worker python -m aibot.verify_integrations --service telegram
docker compose start worker
```

# Celery Pipeline

## Зачем нужен Celery

Парсинг, AI-генерация и публикация в Telegram могут быть медленными и нестабильными из-за внешних сервисов. Поэтому FastAPI не должен ждать их выполнения в HTTP-запросе.

Celery отвечает за:

- регулярный парсинг;
- запуск тяжелых задач в фоне;
- повторные попытки при временных ошибках;
- разделение API и фоновой обработки.

## Broker

Для MVP выбираем Redis.

Причины:

- проще поднять локально;
- подходит для Celery broker/backend;
- может использоваться для простых локов и кэша.

## Celery Beat

Регулярная задача:

```text
run-full-pipeline: every 30 minutes
```

Она запускает полный проход:

```text
enabled sources -> parse/filter/save -> generate ready news -> publish generated posts
```

Интервал и лимиты одного прохода задаются через:

```text
PIPELINE_INTERVAL_SECONDS=1800
PIPELINE_PARSE_LIMIT=10
PIPELINE_GENERATION_LIMIT=10
PIPELINE_PUBLISHING_LIMIT=10
```

## Основные задачи

### `parse_enabled_sources`

Получает все `Source(enabled=true)` и обрабатывает их независимо в batch-сервисе.
Сбой одного источника не останавливает остальные. Результат каждой обработки содержит
`status=success` или `status=failed`; для ошибки наружу возвращается только имя типа,
а полная безопасная запись хранится в `ErrorLog`.

Ручной endpoint ставит отдельную `parse_source`-задачу. Она повторяется с backoff
до трёх раз только для `HttpTemporaryError`; постоянные HTTP/feed ошибки не retry-ятся.

### `parse_source(source_id)`

Выбирает парсер по типу источника:

- `site` -> site parser;
- `tg` -> Telegram parser.

После парсинга передает новости на сохранение и дедупликацию.

### `filter_news(news_id)`

Проверяет:

- язык;
- ключевые слова;
- источник;
- дубли.

Если новость подходит, ставит статус `ready_for_generation`.

### `generate_post(news_id)`

Готовит prompt, вызывает AI-клиент, создает или обновляет `Post`.

Успех:

- `Post.status = generated`;
- `NewsItem.status = generated`.

Ошибка:

- `Post.status = failed`;
- ошибка пишется в `ErrorLog`.

### `publish_post(post_id)`

Проверяет, что пост:

- существует;
- имеет статус `generated`;
- еще не опубликован;
- содержит непустой `generated_text`.

После успешной отправки:

- `Post.status = published`;
- `Post.published_at = now`;
- сохраняется `telegram_message_id`.

Задача не знает деталей Telegram SDK. `PublishingService` получает
`TelegramPublisherPort`, а runtime factory выбирает `telethon` или `bot_api` из
`TELEGRAM_PUBLISHER`. Одновременно активен только один publisher; fallback после
ошибки запрещён.

## Полный pipeline

```text
parse_enabled_sources
  -> parse_source
    -> filter_news
      -> generate_post
        -> publish_post
```

Beat вызывает `run_pipeline`, который последовательно выполняет все стадии в одном
worker task. Ошибка одного parser-источника уже записана в `ErrorLog` и не останавливает
остальные источники или последующие generation/publish стадии. Результат запуска
содержит количество успешных и неуспешных источников.

AI или Telegram ошибка завершает текущий pipeline task, но сохраняется через
integration-specific ErrorLog и общий Celery failure hook.

## Ручные API-запуски

FastAPI не вызывает parser, AI или Telegram напрямую. Ручные endpoints возвращают
`202 Accepted` и единый JSON:

```json
{
  "task_id": "celery-task-id",
  "status": "queued"
}
```

Celery adapter сериализует UUID в строки. Перед постановкой entity-based задач API
выполняет быструю проверку существования и допустимого статуса сущности, а worker
повторяет доменную проверку перед фактической операцией.

## Повторные попытки

Рекомендуемые retry-правила:

- parser network errors: 3 попытки;
- AI rate limit: 3-5 попыток с backoff;
- Telegram temporary errors: 3 попытки;
- validation/data errors: не повторять.

HTTP-клиент и ingestion не выполняют внутренние retries. Они сохраняют тип временной
ошибки; retry/backoff остаётся ответственностью Celery-задачи.

## Идемпотентность

Задачи должны быть безопасны при повторном запуске:

- `parse_source` не создает дубли благодаря `url` и `content_hash`;
- `generate_post` не создает второй активный пост без явного запроса на регенерацию;
- `publish_post` не публикует пост, если статус уже `published`.

### Конкурентная генерация

`generate_post(news_id)` захватывает строку `NewsItem` через PostgreSQL
`SELECT ... FOR UPDATE SKIP LOCKED` до обращения к AI и удерживает lock до
commit/rollback. Если строка уже занята другим worker:

- второй worker получает `ConcurrentGenerationError`;
- AI повторно не вызывается;
- второй `Post` не создаётся;
- lock автоматически освобождается PostgreSQL при завершении транзакции или падении
  worker-а.

API preflight остаётся неблокирующим. Авторитетная проверка конкурентности выполняется
в worker непосредственно перед AI-вызовом.

## Наблюдаемость

Каждая задача должна логировать:

- старт;
- количество обработанных элементов;
- внешний сервис, если он вызывался;
- ошибку и идентификаторы связанных сущностей.

Для учебного проекта достаточно стандартного `logging` и таблицы `ErrorLog`.

Все project tasks используют общий `LoggedTask`. После окончательного failure, уже
после исчерпания встроенных retries, он записывает:

- `scope="celery"`;
- внутреннее имя task;
- только имя класса исключения;
- `source_id`, `news_id` или `post_id`, если ID присутствует в аргументах task.

Raw traceback, exception message, API keys и session paths в `ErrorLog` не попадают.

Celery tasks и lifecycle hooks получают SQLAlchemy sessions из отдельного
`WorkerSessionFactory` с `NullPool`. Это обязательная граница Worker runtime:
последовательные вызовы `asyncio.run()` не должны повторно использовать одно
asyncpg-соединение между разными event loop. FastAPI продолжает использовать свой
обычный pooled `AsyncSessionFactory`.

## Запуски из кабинета

До dispatch создаётся `PipelineRun(status="queued")` с уникальным idempotency key.
Celery hooks переводят его в `running`, затем в `succeeded` или `failed`, сохраняя
только integer counts и имя класса ошибки. Повторный submit с тем же ключом возвращает
существующий run и не вызывает `.delay()` повторно.

Beat создаёт собственный `PipelineRun(initiator="beat")`. Отдельная периодическая
задача `reconcile_pipeline_runs` помечает зависшие queued/running записи `stale`.
Интервалы задаются `PIPELINE_RECONCILIATION_INTERVAL_SECONDS` и
`PIPELINE_RUN_STALE_AFTER_SECONDS`.

Публикационная задача получает Post через `SELECT ... FOR UPDATE SKIP LOCKED` и
удерживает lock до результата Telegram-вызова. Поэтому два worker-а не могут
одновременно отправить один и тот же пост.

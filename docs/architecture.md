# Architecture

## Общая схема

```text
Sources
  |-- websites
  |-- public Telegram channels
        |
        v
Parser layer
        |
        v
News storage
        |
        v
Filtering and deduplication
        |
        v
AI generation
        |
        v
Post storage
        |
        v
Telegram publisher
```

Параллельно с этим FastAPI дает API для ручного управления источниками, ключевыми словами, постами и генерацией.

## Предлагаемая структура проекта

```text
.
  src/
    aibot/
      __init__.py
      main.py
      config.py
      db/
        base.py
        session.py
        migrations/
          env.py
      models/
        mixins.py
        enums.py
        source.py
        keyword.py
        news_item.py
        post.py
        error_log.py
      api/
        deps.py
        routers/
          health.py
          sources.py
          keywords.py
          news.py
          posts.py
          generation.py
          logs.py
        schemas/
          source.py
          keyword.py
          news_item.py
          post.py
          generation.py
          error_log.py
          task.py
          common.py
    repositories/
      base_repository.py
      source_repository.py
      keyword_repository.py
      news_repository.py
      post_repository.py
      error_log_repository.py
    services/
      source_service.py
      keyword_service.py
      news_service.py
      post_service.py
        error_log_service.py
        filtering.py
        language_detection.py
        deduplication.py
        post_generation.py
        publishing.py
      parsers/
        base.py
        rss.py
        sites.py
        telegram.py
      integrations/
        ai_client.py
        telegram_client.py
        telegram_bot_publisher.py
        telegram_publisher_factory.py
        telethon_reader.py
        telethon_publisher.py
        http_client.py
      ports/
        telegram.py
      tasks/
        celery_app.py
        parsing.py
        filtering.py
        generation.py
        publishing.py
        pipeline.py
      logging_config.py
  celery_worker.py
  docker-compose.yml
  tests/
    conftest.py
    unit/
    integration/
  pyproject.toml
  .python-version
  README.md
  .env.example
```

Эта структура шире исходной из задания намеренно. Код приложения лежит в `src/aibot/`: это нормальный Python `src` layout, где `aibot` является импортируемым пакетом. Мы не складываем все модели в `models.py` и все схемы в `schemas.py`. Для этого проекта выбираем более модульный стиль: одна сущность, один класс или одна самостоятельная ответственность - отдельный Python-файл.

## Правило одного класса/ответственности

Базовое правило для будущей реализации:

- `Source` -> `src/aibot/models/source.py`;
- `SourceCreate`, `SourceUpdate`, `SourceRead` -> `src/aibot/api/schemas/source.py`;
- `SourceRepository` -> `src/aibot/repositories/source_repository.py`;
- `Source` endpoints -> `src/aibot/api/routers/sources.py`;
- самостоятельный сервис -> отдельный файл в `src/aibot/services/`;
- самостоятельный внешний клиент -> отдельный файл в `src/aibot/integrations/`.

Не нужно доводить это до абсурда для маленьких enum/helper-объектов, но основные классы и сущности не должны жить в одном большом файле.

## Слои ответственности

### API layer

Отвечает только за HTTP:

- принимает запрос;
- валидирует входные данные через Pydantic-схемы;
- вызывает сервисы;
- возвращает понятный JSON-ответ.

API не должен напрямую выполнять тяжелые операции: парсинг, генерацию и публикацию лучше запускать через Celery.

### Services layer

Содержит бизнес-логику:

- фильтрация;
- дедупликация;
- подготовка промпта;
- создание `Post`;
- смена статусов;
- проверка возможности публикации.

Сервисы не должны зависеть от FastAPI.

### Repositories layer

Отвечает за работу с PostgreSQL через SQLAlchemy:

- создание, чтение, обновление и удаление сущностей;
- небольшие query-методы;
- транзакционные операции, если они относятся к одной сущности.

Repository не должен вызывать AI, Telegram или Celery.

### Parsers layer

Отвечает за получение сырых новостей из источников.

Каждый парсер должен возвращать нормализованный список `NewsItem`, а не сохранять данные как попало. Сохранение и дедупликация выполняются отдельным сервисом.

### Integrations layer

Содержит тонкие клиенты для внешних API:

- AI API;
- Telegram/Telethon;
- HTTP-загрузка страниц.

Внешние ошибки нужно превращать в понятные исключения или результат со статусом ошибки.

Telegram integration разделена на независимые adapters. `TelethonChannelReader`
обслуживает только `Source(type="tg")`; публикация проходит через
`TelegramPublisherPort`, для которого доступны `TelethonPublisher` и
`TelegramBotPublisher`. Factory выбирает один adapter по `TELEGRAM_PUBLISHER` и не
выполняет fallback. Совместимый `TelegramClient` остаётся фасадом старого внутреннего
контракта, но production parser/publishing service больше от него не зависят.

### Tasks layer

Содержит Celery-задачи:

- регулярный запуск парсеров;
- генерация постов;
- публикация;
- полный pipeline.

Celery-задача должна быть тонкой: взять параметры, вызвать сервис, записать результат.

## Основной сценарий

1. Celery Beat запускает `run_pipeline`.
2. Pipeline получает все включенные источники и изолирует сбой каждого parser-а.
3. Для каждого источника выбирается подходящий парсер.
4. Найденные новости сохраняются после дедупликации.
5. Отобранные новости проходят фильтрацию.
6. Для подходящих новостей создаются задачи генерации.
7. AI-генератор создает текст поста.
8. Пост получает статус `generated`.
9. Публикационная задача отправляет пост в Telegram.
10. Пост получает статус `published` или `failed`.

## Режимы работы

### Автоматический режим

Работает по расписанию через Celery Beat.

### Ручной режим

Через API можно:

- запустить парсинг конкретного источника;
- вручную сгенерировать пост из текста;
- опубликовать уже сгенерированный пост;
- посмотреть ошибки.

### Dry-run режим

Для учебной демонстрации полезно иметь `TELEGRAM_DRY_RUN=true`. В этом режиме сервис не отправляет реальный пост в Telegram, а только записывает, что публикация была бы выполнена.

## Container runtime topology

Один immutable application image используется несколькими Compose-сервисами:

```text
PostgreSQL healthy ──> migrate completed ──> API
                           │               ├─> Worker ──> Telethon session volume
Redis healthy ────────────┴───────────────└─> Beat ────> Beat schedule volume
```

`migrate` является единственным процессом, который запускает Alembic. API, Worker и
Beat не изменяют схему при старте. Worker и Beat запускаются в одном экземпляре;
Worker использует concurrency `1`, потому что является единственным владельцем
SQLite session-файла Telethon.

FastAPI использует обычный SQLAlchemy connection pool. Celery task adapters используют
отдельный `WorkerSessionFactory` с `NullPool`: синхронные Celery hooks и task bodies
запускают async-код через отдельные `asyncio.run()`, поэтому asyncpg-соединения нельзя
переносить между event loop.

PostgreSQL, Redis, Beat state и Telethon session используют независимые named
volumes. Env-файлы и session никогда не входят в build context или image.
Application containers работают от non-root пользователя с read-only root
filesystem; writable paths предоставляются только через tmpfs и целевые volumes.

## Принципы реализации

- PostgreSQL - основная база данных проекта.
- Использовать `src/aibot/` как корень Python-пакета.
- Использовать Python `3.12` и хранить зависимости в `pyproject.toml`.
- Хранить внешние ключи и статусы явно.
- Не смешивать HTTP-логику, Celery и доменные сервисы.
- Не вызывать parser, AI или Telegram напрямую из HTTP endpoints.
- Все тяжёлые ручные операции ставить через task queue port и Celery adapter.
- Любая публикация должна быть идемпотентной: один пост нельзя отправить дважды.
- Ошибки внешних сервисов должны попадать в логи и в статус сущности.
- Основные классы и сущности размещать по отдельным файлам.

## Административный кабинет

Server-rendered кабинет является входным HTTP/Jinja adapter-ом. Providers обращаются
к application ports и SQLAlchemy read repositories напрямую, без HTTP к собственному
API. Мутации Source/Keyword переиспользуют domain services; тяжёлые операции проходят
только через task queue port.

Граница разделена на:

- read repositories для dashboard, entity pages и operational journals;
- mutation service с CSRF, row lock, optimistic version и audit;
- operation service с entity preflight, idempotency, Celery dispatch и `PipelineRun`;
- Celery lifecycle hooks и reconciliation;
- integrations остаются внутри worker-а и никогда не вызываются при рендере страницы.

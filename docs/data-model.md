# Data Model

## База данных

Основная база данных проекта - PostgreSQL.

Рекомендуемые общие правила:

- использовать `UUID` для публичных идентификаторов сущностей;
- хранить даты в `TIMESTAMP WITH TIME ZONE`;
- хранить статусы через строковые enum-значения;
- добавлять `created_at` и `updated_at` к основным таблицам;
- использовать уникальные индексы для `Source(type, url)`, `Keyword(word)`, `NewsItem.url` и `NewsItem.content_hash`.

В локальной разработке проект тоже должен запускаться на PostgreSQL, лучше всего через Docker Compose. SQLite не используем как целевую БД, чтобы не получить расхождения с PostgreSQL по типам, индексам и ограничениям.

## Source

Источник новостей.

Поля:

- `id`: UUID primary key.
- `type`: `site` или `tg`.
- `name`: человекочитаемое имя.
- `url`: URL сайта или username Telegram-канала.
- `enabled`: включен ли источник.
- `created_at`: дата создания.
- `updated_at`: дата обновления.

Ограничения:

- пара `type + url` должна быть уникальной;
- отключенный источник не должен участвовать в автоматическом парсинге.

## Keyword

Ключевое слово для фильтрации.

Поля:

- `id`: UUID primary key.
- `word`: ключевое слово.
- `enabled`: включено ли слово.
- `created_at`: дата создания.

Ограничения:

- `word` должно быть уникальным без учета регистра.

## NewsItem

Нормализованная новость, полученная из сайта или Telegram-канала.

Поля:

- `id`: UUID primary key.
- `title`: заголовок.
- `url`: ссылка, если есть.
- `summary`: краткое описание.
- `source_id`: ссылка на `Source`.
- `published_at`: дата публикации у источника.
- `raw_text`: исходный текст, особенно для Telegram.
- `content_hash`: hash для дедупликации.
- `status`: статус обработки.
- `created_at`: дата сохранения.

Статусы:

- `new`: новость сохранена, но еще не обработана.
- `filtered_out`: новость не прошла фильтры.
- `ready_for_generation`: новость подходит для генерации.
- `generated`: для новости создан пост.
- `failed`: обработка завершилась ошибкой.

Ограничения:

- `url` уникален, если он есть;
- `content_hash` уникален для защиты от дублей без URL.

## Post

AI-сгенерированный пост для Telegram.

Поля:

- `id`: UUID primary key.
- `news_id`: ссылка на `NewsItem`.
- `generated_text`: готовый текст поста.
- `status`: статус публикации.
- `published_at`: дата фактической публикации.
- `telegram_message_id`: ID сообщения в Telegram, если публикация успешна.
- `error_message`: последняя ошибка, если есть.
- `created_at`: дата создания.
- `updated_at`: дата обновления.

Статусы:

- `new`: пост создан как заготовка.
- `generated`: текст успешно сгенерирован.
- `publishing`: публикация выполняется.
- `published`: пост опубликован.
- `failed`: генерация или публикация завершилась ошибкой.

Ограничения:

- один `NewsItem` не должен иметь больше одного опубликованного `Post`;
- повторная публикация `published` поста запрещена.
- конкурентная генерация одного `NewsItem` защищена транзакционным PostgreSQL row lock;
  дополнительное поле или Redis lock для этого не требуется.

## ErrorLog

Журнал ошибок для API и фоновых задач.

Поля:

- `id`: UUID primary key.
- `scope`: зона ошибки: `parser`, `ai`, `telegram`, `celery`, `api`.
- `message`: короткое описание.
- `details`: подробности ошибки.
- `source_id`: опциональная ссылка на источник.
- `news_id`: опциональная ссылка на новость.
- `post_id`: опциональная ссылка на пост.
- `created_at`: дата ошибки.

## Связи

```text
Source 1--N NewsItem
NewsItem 1--N Post
Source 1--N ErrorLog
NewsItem 1--N ErrorLog
Post 1--N ErrorLog
```

В MVP можно упростить `NewsItem 1--N Post` до `NewsItem 1--1 Post`, но в модели лучше оставить возможность регенерации поста.

## PipelineRun

Persisted lifecycle фоновой операции кабинета или Beat:

- `initiator`: `beat`, `cabinet` или `api`;
- `operation`: `parse_source`, `generate_news`, `publish_post`, `run_pipeline`;
- `status`: `queued`, `running`, `succeeded`, `failed`, `revoked`, `stale`;
- optional entity UUID и Celery `task_id`;
- уникальный `idempotency_key`;
- безопасные параметры, integer result counts и категория ошибки;
- timestamps запуска, heartbeat и завершения.

Queued/running записи периодически reconcилируются и становятся `stale`, если worker
не обновил lifecycle за настроенный интервал.

## AdminAuditLog

Append-only журнал административных мутаций:

- безопасный actor identifier;
- action и тип/UUID сущности;
- outcome `succeeded`, `rejected` или `failed`;
- только bounded категория результата, без form payload, cookies и секретов.

`Keyword` дополнительно имеет `updated_at`, используемый вместе с row lock для
защиты форм от lost update.

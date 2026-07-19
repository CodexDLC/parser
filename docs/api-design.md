# API Design

## Общие правила

- Базовый префикс API: `/api`.
- Все ответы возвращаются в JSON.
- Swagger доступен по `/docs`.
- Ошибки возвращаются в едином формате:

```json
{
  "detail": "Human readable error"
}
```

Для MVP можно использовать стандартный формат FastAPI.

## Sources

### `GET /api/sources/`

Вернуть список источников.

Query-параметры:

- `enabled`: фильтр по активности.
- `type`: `site` или `tg`.

### `POST /api/sources/`

Создать источник.

Пример тела:

```json
{
  "type": "site",
  "name": "Example News",
  "url": "https://example.com/news",
  "enabled": true
}
```

### `GET /api/sources/{source_id}`

Вернуть один источник.

### `PATCH /api/sources/{source_id}`

Частично обновить источник.

### `DELETE /api/sources/{source_id}`

Удалить или мягко отключить источник. Для MVP предпочтительно мягкое удаление через `enabled=false`, чтобы история новостей не ломалась.

### `POST /api/sources/{source_id}/parse`

Запустить ручной парсинг конкретного источника через Celery.

Успешный ответ: `202 Accepted`.

```json
{
  "task_id": "celery-task-id",
  "status": "queued"
}
```

## Keywords

### `GET /api/keywords/`

Вернуть список ключевых слов.

### `POST /api/keywords/`

Создать ключевое слово.

```json
{
  "word": "python",
  "enabled": true
}
```

### `PATCH /api/keywords/{keyword_id}`

Обновить слово или активность.

### `DELETE /api/keywords/{keyword_id}`

Удалить ключевое слово.

## News

### `GET /api/news/`

Вернуть список новостей.

Query-параметры:

- `source_id`;
- `status`;
- `limit`;
- `offset`.

### `GET /api/news/{news_id}`

Вернуть одну новость.

### `POST /api/news/{news_id}/generate`

Запустить генерацию поста для конкретной новости.

Успешный ответ: `202 Accepted` с `task_id` и `status="queued"`.
До постановки задачи API проверяет, что новость существует и имеет статус
`ready_for_generation`.

## Posts

### `GET /api/posts/`

Вернуть историю постов.

Query-параметры:

- `status`;
- `limit`;
- `offset`.

### `GET /api/posts/{post_id}`

Вернуть один пост.

### `POST /api/posts/{post_id}/publish`

Запустить публикацию поста.

Правило:

- если пост уже `published`, вернуть ошибку 409 Conflict.
- успешный ответ: `202 Accepted` с `task_id` и `status="queued"`.

## Manual Generation

### `POST /api/generate/`

Ручная генерация поста из произвольного текста.

Пример тела:

```json
{
  "text": "Python 3.14 получил новую оптимизацию интерпретатора...",
  "source": "manual"
}
```

Успешный ответ: `202 Accepted`.

```json
{
  "task_id": "celery-task-id",
  "status": "queued"
}
```

Этот эндпоинт полезен для демонстрации AI-интеграции без полного pipeline.

## Фоновые операции

Все четыре тяжёлых endpoint используют единый контракт:

- `POST /api/sources/{source_id}/parse`;
- `POST /api/news/{news_id}/generate`;
- `POST /api/posts/{post_id}/publish`;
- `POST /api/generate/`.

HTTP handler выполняет только валидацию и постановку задачи. Парсинг, AI и Telegram
не вызываются внутри HTTP-запроса. Итог сохраняется доменными сервисами в PostgreSQL,
а технический результат задачи доступен через Celery backend по полученному `task_id`.

## Logs

### `GET /api/logs/`

Вернуть последние ошибки.

Query-параметры:

- `scope`;
- `limit`;
- `offset`.

## Health

### `GET /api/health`

Простой healthcheck.

Ответ:

```json
{
  "status": "ok"
}
```

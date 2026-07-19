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

Ответ:

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

Пример ответа:

```json
{
  "generated_text": "..."
}
```

Этот эндпоинт полезен для демонстрации AI-интеграции без полного pipeline.

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


# Runtime And Dependencies

## Python Version

Выбран Python `3.12`.

В `pyproject.toml` это зафиксировано так:

```toml
requires-python = ">=3.12,<3.13"
```

Причины:

- в локальном окружении доступен Python `3.12.13`;
- Python 3.12 достаточно свежий для FastAPI, SQLAlchemy 2, Celery, Telethon и OpenAI SDK;
- версия не слишком новая, поэтому меньше риск несовместимости библиотек;
- ограничение `<3.13` делает учебную сдачу более предсказуемой.

Также добавлен файл `.python-version` со значением:

```text
3.12
```

## Runtime Dependencies

### FastAPI API

- `fastapi` - HTTP API и Swagger.
- `uvicorn[standard]` - ASGI-сервер для локального запуска.
- `pydantic` - валидация данных.
- `pydantic-settings` - настройки из переменных окружения.
- `python-dotenv` - чтение локального `.env`.
- `codex-fastapi-cabinet==0.1.0` - server-rendered shell, страницы и dashboard
  widgets административного кабинета.
- `pwdlib[argon2]` - Argon2 password hash единственного администратора.
- `itsdangerous` - подпись opaque session и login CSRF cookies.
- `python-multipart` - form runtime для следующих CRUD-этапов кабинета.

Read-only dashboard работает через SQLAlchemy repository напрямую, без HTTP к
собственному API. Метрики и таблицы загружаются одним request-scoped snapshot:
один агрегирующий запрос, две группировки и две ограниченные последние выборки.
Passive health выполняет только cached Redis PING; OpenAI, Telegram и Celery
worker на открытии кабинета не вызываются.

Operational кабинет хранит `PipelineRun` и `AdminAuditLog` в PostgreSQL. Celery hooks
обновляют lifecycle, Beat запускает stale reconciliation, а status polling читает
только безопасную persisted read-model. Формы Source/Keyword используют общий CSRF
boundary и PostgreSQL row lock; публикация удерживает Post lock до ответа Telegram.

### PostgreSQL And ORM

- `sqlalchemy[asyncio]` - ORM и async database layer.
- `asyncpg` - async-драйвер PostgreSQL.
- `psycopg[binary]` - PostgreSQL-драйвер, полезный для sync-инструментов и миграций.
- `alembic` - единственный production-механизм создания и изменения схемы БД;
  initial revision покрывает все пять ORM-моделей и проверяется round-trip тестом.

### Celery And Redis

- `celery[redis]` - фоновые задачи и Redis transport.
- `redis` - прямой клиент Redis для локов, кэша или служебных операций.

### Telegram And AI

- `telethon` - чтение Telegram-каналов и публикация постов.
- `codex-ai[openai]==0.2.5` - единый AI provider; OpenAI-интеграция работает через
  Responses API и `gpt-5.6-terra`.
- `tenacity` - retry/backoff для внешних API.

### Parsing

- `requests` - простой sync HTTP-клиент для учебных site parsers.
- `httpx` - современный HTTP-клиент, удобный для API и async-сценариев.
- `beautifulsoup4` - HTML parsing.
- `lxml` - быстрый HTML/XML parser backend.
- `feedparser` - RSS/Atom источники.
- `langdetect` - простая языковая фильтрация новостей.

## Dev Dependencies

Группа `dev`:

- `pytest`;
- `pytest-asyncio`;
- `pytest-cov`;
- `ruff`;
- `mypy`;
- `pre-commit`.

Группа `test` дополнительно содержит:

- `testcontainers[postgres]` для интеграционных тестов с PostgreSQL.

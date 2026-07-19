# Project M4: AI Telegram News Generator

Учебный backend-проект для автоматизации новостного Telegram-канала.

Документация проекта находится в [docs/index.md](docs/index.md).

## Runtime

- Python: `3.12`
- Package layout: `src/aibot`
- API framework: FastAPI

## Первый запуск

```powershell
uv sync --extra dev
docker compose up -d postgres redis
uv run python -m aibot.db.init_db
uv run uvicorn aibot.main:app --reload
```

После запуска:

- Swagger: <http://127.0.0.1:8000/docs>
- Healthcheck: <http://127.0.0.1:8000/api/health>

## Smoke-проверка прототипа

После запуска PostgreSQL/Redis можно одной командой проверить полный dry-run сценарий через реальную БД:

```powershell
uv run python -m aibot.smoke --reset
```

Команда пересоздает таблицы, добавляет demo-источник и ключевое слово, парсит demo-новости, генерирует пост через fake AI и публикует его в Telegram dry-run режиме.

## Демо без ключей

Если Docker, PostgreSQL, OpenAI-ключ или Telegram-ключи пока не настроены, можно запустить безопасный локальный сценарий:

```powershell
uv run python -m aibot.demo
```

Он проходит цепочку `demo site parser -> deduplication -> keyword filter -> fake AI generation -> Telegram dry-run publish` и печатает JSON-сводку. Реальных внешних запросов и публикаций нет.

В режиме `TELEGRAM_DRY_RUN=true` Telegram parser тоже работает безопасно: вместо подключения к Telegram он возвращает demo-сообщения. Для реального чтения каналов и публикации нужно заполнить Telegram-переменные из [.env.example](.env.example) и отключить dry-run.

## Проверки

```powershell
uv run --extra dev ruff check src tests
uv run --extra dev python -m pytest
```

Интеграционный CRUD-тест с PostgreSQL запускается тем же `pytest`. Если Docker/PostgreSQL не поднят, тест будет пропущен.

## Инфраструктура

Локальный `docker-compose.yml` поднимает:

- PostgreSQL на `localhost:5432`, база `m4`, пользователь `m4`, пароль `m4`;
- Redis на `localhost:6379`.

Переменные окружения описаны в [.env.example](.env.example).

## Примеры API-запросов

Команды ниже предполагают, что API уже запущен на `http://127.0.0.1:8000`.

```powershell
$base = "http://127.0.0.1:8000/api"

$source = Invoke-RestMethod -Method Post -Uri "$base/sources/" -ContentType "application/json" -Body '{
  "type": "site",
  "name": "Demo News",
  "url": "https://example.test/news",
  "enabled": true
}'

Invoke-RestMethod -Method Post -Uri "$base/keywords/" -ContentType "application/json" -Body '{
  "word": "python",
  "enabled": true
}'

Invoke-RestMethod -Method Post -Uri "$base/sources/$($source.id)/parse?limit=2"
Invoke-RestMethod -Uri "$base/news/"
Invoke-RestMethod -Uri "$base/posts/"
```

После появления новости со статусом `ready_for_generation` можно сгенерировать пост:

```powershell
$news = Invoke-RestMethod -Uri "$base/news/?status=ready_for_generation&limit=1"
$post = Invoke-RestMethod -Method Post -Uri "$base/news/$($news[0].id)/generate"
Invoke-RestMethod -Method Post -Uri "$base/posts/$($post.id)/publish"
```

При `AI_FAKE_MODE=true` и `TELEGRAM_DRY_RUN=true` генерация и публикация безопасны: внешние API не вызываются, а Telegram message id будет вида `dry-run-*`.

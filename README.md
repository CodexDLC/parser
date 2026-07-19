# Project M4: AI Telegram News Generator

Учебный backend-проект для автоматизации новостного Telegram-канала.

Документация проекта находится в [docs/index.md](docs/index.md).
Репозиторий: <https://github.com/CodexDLC/parser>.

Stage-gated план административного кабинета на
`codex-fastapi-cabinet==0.1.0` описан в
[docs/cabinet-plan.md](docs/cabinet-plan.md). Кабинет остаётся выключенным по
умолчанию через `CABINET_ENABLED=false`; после включения доступны single-admin
shell, dashboard, страницы сущностей, Source/Keyword CRUD, мониторинг Celery и
подтверждаемая Telegram-публикация. Passive health не делает платных внешних вызовов.

Защищённая оболочка подключается только после создания single-admin credentials:

```powershell
uv run python -m aibot.cabinet.credentials --username admin
```

Команда дважды запрашивает пароль длиной не менее 12 символов и выводит Argon2 hash
и отдельный session secret. Значения уже заключены в одинарные кавычки, чтобы Docker
Compose не интерполировал символы `$` внутри Argon2. Полученные строки нужно вручную
перенести в игнорируемые `.env` и `.env.prod`, затем установить
`CABINET_ENABLED=true`. Plaintext password в файлы и Git не записывается. После
запуска вход доступен по <http://127.0.0.1:8000/cabinet/login>.
Календарные метрики используют IANA timezone из `CABINET_TIMEZONE`.
Каждая тяжёлая операция кабинета создаёт persisted `PipelineRun`; повторная отправка
той же формы не ставит вторую задачу. История мутаций доступна в разделе «Аудит».

## Runtime

- Python: `3.12`
- Package layout: `src/aibot`
- API framework: FastAPI

## Первый запуск

```powershell
uv sync --extra dev
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn aibot.main:app --reload
```

После запуска:

- Swagger: <http://127.0.0.1:8000/docs>
- Healthcheck: <http://127.0.0.1:8000/api/health>
- Административный кабинет: <http://127.0.0.1:8000/cabinet/>
- Вход в кабинет: <http://127.0.0.1:8000/cabinet/login>

Кабинет доступен только при `CABINET_ENABLED=true`.

## Полный контейнерный стек

`Dockerfile` собирает один non-root runtime image. Из него Compose запускает разные
роли: одноразовый `migrate`, FastAPI `api`, singleton `worker` и singleton `beat`.
PostgreSQL, Redis и Telethon session используют отдельные named volumes.

Для первого локального запуска:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

`migrate` завершится после `alembic upgrade head`; остальные application-сервисы
стартуют только после успешной миграции. API будет доступен на
<http://127.0.0.1:8000>. PostgreSQL и Redis доступны application-контейнерам только
во внутренней Docker-сети и не занимают host-порты.

Основные команды:

```powershell
docker compose logs -f api worker beat
docker compose restart api worker beat
docker compose down
```

`docker compose down` сохраняет данные. Команда `docker compose down --volumes`
безвозвратно удаляет PostgreSQL, Redis, Beat state и Telethon session volumes, поэтому
её нельзя использовать на сервере без осознанного решения и резервной копии.

### Production env

В `.env.prod` необходимо как минимум заменить:

```env
APP_ENV_FILE=".env.prod"
APP_IMAGE_TAG="prod"
ENVIRONMENT="production"
DEBUG=false
DOCS_ENABLED=false

POSTGRES_PASSWORD="случайный_пароль"
CONTAINER_DATABASE_URL="postgresql+asyncpg://m4:URL_ENCODED_PASSWORD@postgres:5432/m4"
```

`POSTGRES_PASSWORD` и пароль внутри `CONTAINER_DATABASE_URL` должны совпадать; в URL
зарезервированные символы необходимо percent-encode. Запуск с production-файлом:

```powershell
docker compose --env-file .env.prod up -d --build
```

Compose передаёт `.env.prod` только во время запуска: `.dockerignore` исключает
`.env`, `.env.prod` и `*.session` из build context и image layers.

### AI provider и fallback

AI runtime использует `codex-ai[openai,gemini]==0.2.5`. По умолчанию OpenAI остаётся
основным provider-ом, а Gemini вызывается только после ошибки OpenAI:

```env
AI_PROVIDER="openai"
AI_FALLBACK_PROVIDER="gemini"

OPENAI_API_KEY=""
OPENAI_MODEL="gpt-5.6-terra"
OPENAI_TIMEOUT_SECONDS=60

GEMINI_API_KEY=""
GEMINI_MODEL="gemini-3.5-flash"
AI_MAX_OUTPUT_TOKENS=2048
```

Если ключ fallback provider-а не заполнен, chain использует только настроенный
provider. Если OpenAI не настроен, но заполнен `GEMINI_API_KEY`, генерация сразу идёт
через Gemini. Чтобы полностью переключить порядок, установите
`AI_PROVIDER="gemini"` и `AI_FALLBACK_PROVIDER="openai"`. Реальные ключи хранятся
только в игнорируемых `.env`/`.env.prod` и не передаются в Git.

`AI_MAX_OUTPUT_TOKENS` учитывает внутренние reasoning-токены provider-а. Перед
сохранением AI-ответ проходит отдельную проверку: принимается только законченный
plain-text пост длиной 180–900 символов без Markdown/HTML. Оборванный или размеченный
ответ считается ошибкой генерации и никогда не передаётся Telegram publisher-у.
После проверки `TelegramPostComposer` добавляет к preview исходный HTTP(S)-адрес из
`NewsItem.url`. Ссылка не передаётся модели для генерации и поэтому не может быть
выдумана или изменена AI.

### Telethon внутри Compose

Первичную авторизацию выполняют до запуска Worker либо при остановленном Worker:

```powershell
docker compose up -d --build postgres redis
docker compose --profile tools run --rm telegram-auth
docker compose up -d
```

Интерактивная команда сохраняет session в volume `telegram_session`. Этот volume
монтируется только в singleton Worker и `telegram-auth`; API и Beat к нему доступа не
имеют. Worker запускается с `--concurrency=1`, чтобы один SQLite session-файл не
использовался параллельно несколькими процессами.

## Миграции базы данных

Alembic является единственным production-механизмом создания и изменения схемы.
Основные команды:

```powershell
uv run alembic current
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic revision --autogenerate -m "describe schema change"
uv run alembic check
```

Команда `uv run python -m aibot.db.init_db` сохранена как короткий bootstrap и внутри
также выполняет `alembic upgrade head`; прямого `Base.metadata.create_all` в production
bootstrap нет.

Тяжёлые API-операции только ставят задачи в Redis, поэтому во втором терминале нужен
Celery worker. На Windows используется solo pool:

```powershell
uv run celery -A celery_worker.celery_app worker --loglevel=info --pool=solo
```

Для автоматического pipeline в третьем терминале запускается Beat:

```powershell
uv run celery -A celery_worker.celery_app beat --loglevel=info
```

По умолчанию Beat каждые 30 минут запускает полный проход
`parse/filter/save → generate → publish`. Настройки расписания и лимитов:

```env
PIPELINE_INTERVAL_SECONDS=1800
PIPELINE_PARSE_LIMIT=10
PIPELINE_GENERATION_LIMIT=10
PIPELINE_PUBLISHING_LIMIT=10
```

Ошибки AI и окончательные сбои Celery доступны через `GET /api/logs/`. В журнал
записываются безопасные типы исключений и связанные entity ID, но не traceback,
provider message или секреты. Конкурентные задачи генерации одной новости защищены
PostgreSQL row lock, поэтому только один worker вызывает AI.

## Smoke-проверка прототипа

После запуска PostgreSQL/Redis и заполнения хотя бы одного AI API key можно одной
командой проверить полный сценарий через реальную БД и настроенную provider chain:

```powershell
uv run python -m aibot.smoke --reset
```

Команда пересоздает таблицы, добавляет demo-источник и ключевое слово, парсит
demo-новости, генерирует пост через AI provider chain и публикует его в Telegram
dry-run режиме. AI-вызов является реальным и расходует quota выбранного provider-а.

## Демо без базы

Если Docker и PostgreSQL не настроены, но заполнен `OPENAI_API_KEY` или
`GEMINI_API_KEY`, можно запустить локальный сценарий:

```powershell
uv run python -m aibot.demo
```

Он проходит цепочку `demo site parser -> deduplication -> keyword filter -> AI
provider chain -> Telegram dry-run publish` и печатает JSON-сводку. Сообщения в
Telegram не отправляются, но внешний AI API вызывается.

В режиме `TELEGRAM_DRY_RUN=true` Telegram parser возвращает demo-сообщения, а
выбранный publisher создаёт детерминированный `dry-run-*` ID без внешнего запроса.
Для real-mode отдельно настраиваются Telethon reader и выбранный publisher.

## Проверки

```powershell
uv run --extra dev ruff check src tests
uv run --extra dev mypy src/aibot tests
uv run --extra dev python -m pytest
```

Интеграционные CRUD- и Alembic-тесты с PostgreSQL запускаются тем же `pytest`.
Migration-тест использует отдельную временную базу `m4_alembic_test` и проверяет
`upgrade → check → downgrade → upgrade`. Если Docker/PostgreSQL не поднят, тесты
будут пропущены вне строгого acceptance-режима.

## Обязательная acceptance-проверка

Полный базовый набор одной командой:

```powershell
.\scripts\acceptance.ps1
```

Он поднимает PostgreSQL и Redis, запускает Ruff, Mypy, все unit/integration тесты в
строгом инфраструктурном режиме и проверяет импорт приложения. В тестах AI заменён
внедряемым test double, поэтому acceptance не требует ключа и не вызывает OpenAI.
Подробный контракт описан в [docs/acceptance-tests.md](docs/acceptance-tests.md).

Отдельная контейнерная проверка собирает production image и в изолированном Compose
project проверяет миграцию, API health, non-root runtime, Worker ping и Beat:

```powershell
.\scripts\container-acceptance.ps1
```

По умолчанию временный стек и его volumes удаляются после проверки. Флаг
`-KeepStack` оставляет их для ручной диагностики.

## Инфраструктура

`docker-compose.yml` поднимает:

- PostgreSQL и Redis с persistent volumes;
- одноразовые Alembic-миграции;
- FastAPI и административный кабинет;
- singleton Celery Worker и Beat.

Переменные окружения описаны в [.env.example](.env.example). Локальные значения
хранятся в игнорируемом Git файле `.env`, production-шаблон с пустыми секретами —
в игнорируемом файле `.env.prod`. Локальные команды `uv run ...` продолжают работать
и используют host URLs из `DATABASE_URL`/`REDIS_URL`; контейнеры получают отдельные
внутренние URLs из `CONTAINER_DATABASE_URL`/`CONTAINER_REDIS_URL`.

Пароль кабинета в env должен оставаться в одинарных кавычках, как его выводит
`aibot.cabinet.credentials`. Двойные кавычки позволяют Compose ошибочно
интерполировать части Argon2 hash после символа `$`.

Для запуска локальных Python-команд и integration-тестов вне контейнеров используется
dev override, который дополнительно открывает PostgreSQL и Redis на loopback:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
```

## RSS/Atom источники

Источник с типом `site` должен содержать прямой URL RSS/Atom-ленты, а не адрес
главной страницы сайта. Универсальный parser загружает ленту через ограниченный
async HTTP-клиент, поддерживает RSS и Atom и нормализует записи без привязки к
конкретному домену.

Сетевые ограничения настраиваются через:

```env
HTTP_TIMEOUT_SECONDS=15
HTTP_MAX_RESPONSE_BYTES=2000000
HTTP_USER_AGENT="Project-M4-RSS/0.1"
```

Автоматические тесты используют mock HTTP и не обращаются в интернет. Live-проверка
будет выполняться отдельно после выбора одного публичного RSS URL.

## Языковая фильтрация

Разрешённые языки новостей задаются comma-separated ISO-кодами:

```env
NEWS_ALLOWED_LANGUAGES="ru,en"
```

Язык определяется по объединённому `title + summary + raw_text` до проверки ключевых
слов. Неопределённый язык получает причину `language_unknown`, запрещённый —
`language_not_allowed`; обе новости сохраняются со статусом `filtered_out`.

## Telegram: раздельные reader и publisher

Telegram ingestion и публикация являются независимыми integration boundaries:

- `TelethonChannelReader` читает публичные источники `Source(type="tg")`;
- `TelethonPublisher` сохраняет обязательную публикацию через Telethon из Project M4;
- `TelegramBotPublisher` позволяет публиковать RSS/AI-посты через Bot API без
  пользовательской session на сервере.

Активен ровно один publisher, выбранный без автоматического fallback:

```env
TELEGRAM_PUBLISHER="telethon"
```

Это значение по умолчанию и режим демонстрации исходного задания. Для RSS → AI →
собственный канал можно выбрать Bot API:

```env
TELEGRAM_PUBLISHER="bot_api"
TELEGRAM_BOT_TOKEN=""
TELEGRAM_TARGET_CHANNEL="@project_m4_test"
TELEGRAM_DRY_RUN=false
TELEGRAM_TIMEOUT_SECONDS=15
```

Бота создают через `@BotFather`, добавляют администратором целевого канала и выдают
только право публикации. Token хранится только в игнорируемом `.env`/secret storage.
Команды, webhook и обработка пользовательских сообщений проекту не нужны.

Bot API не заменяет Telethon reader: если включён хотя бы один Telegram-источник,
нужны `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` и заранее авторизованная session,
независимо от выбранного publisher.

## Примеры API-запросов

Команды ниже предполагают, что API уже запущен на `http://127.0.0.1:8000`.

```powershell
$base = "http://127.0.0.1:8000/api"

$source = Invoke-RestMethod -Method Post -Uri "$base/sources/" -ContentType "application/json" -Body '{
  "type": "site",
  "name": "Example RSS",
  "url": "https://site.example/feed.xml",
  "enabled": true
}'

Invoke-RestMethod -Method Post -Uri "$base/keywords/" -ContentType "application/json" -Body '{
  "word": "python",
  "enabled": true
}'

$parseTask = Invoke-RestMethod -Method Post -Uri "$base/sources/$($source.id)/parse?limit=2"
$parseTask
Invoke-RestMethod -Uri "$base/news/"
Invoke-RestMethod -Uri "$base/posts/"
```

Ответ тяжёлого endpoint имеет вид `{"task_id":"...","status":"queued"}`. После обработки
задачи worker-ом результат появляется в PostgreSQL и доступен через read endpoints.

После появления новости со статусом `ready_for_generation` можно поставить генерацию,
а после появления поста со статусом `generated` — публикацию:

```powershell
$news = Invoke-RestMethod -Uri "$base/news/?status=ready_for_generation&limit=1"
$generationTask = Invoke-RestMethod -Method Post -Uri "$base/news/$($news[0].id)/generate"

$posts = Invoke-RestMethod -Uri "$base/posts/?status=generated&limit=1"
$publishTask = Invoke-RestMethod -Method Post -Uri "$base/posts/$($posts[0].id)/publish"
```

AI-генерация использует `codex-ai[openai,gemini]==0.2.5`. Основной provider задаётся
через `AI_PROVIDER`, резервный — через `AI_FALLBACK_PROVIDER`; модели читаются из
`OPENAI_MODEL` и `GEMINI_MODEL`. `TELEGRAM_DRY_RUN=true` блокирует только реальную
публикацию в Telegram; внешний AI API при генерации всё равно вызывается.

## Проверка реальных интеграций

Безопасный verifier выполняет production-вызовы, но не печатает ключи, provider
payload, prompt, сгенерированный текст или Telegram account details:

```powershell
uv run python -m aibot.verify_integrations --service openai
uv run python -m aibot.verify_integrations --service telegram
```

Имя `openai` в verifier сохранено для совместимости команды; проверяется вся
настроенная AI chain, поэтому при ошибке OpenAI возможен реальный Gemini fallback.

Статус `blocked` и ненулевой exit code означают внешний prerequisite: например,
отсутствующую квоту, включённый dry-run, неавторизованную Telethon session или
неполную конфигурацию Bot API.

Команда `--service telegram` проверяет publisher из `TELEGRAM_PUBLISHER`. Если передан
`--telegram-source`, дополнительно проверяется Telethon reader и чтение одного
сообщения. Worker никогда не запускает интерактивный login.

Первичная Telethon-авторизация нужна для режима публикации `telethon` и для любых
Telegram-источников. Она выполняется отдельно после заполнения `TELEGRAM_API_ID` и
`TELEGRAM_API_HASH`:

```powershell
uv run python -m aibot.authorize_telegram
```

После авторизации можно проверить чтение одного публичного источника:

```powershell
uv run python -m aibot.verify_integrations --service telegram --telegram-source @public_channel
```

Публикация не входит в проверку по умолчанию. После настройки выбранного publisher,
`TELEGRAM_TARGET_CHANNEL` и `TELEGRAM_DRY_RUN=false` следующая команда действительно
отправляет один маркированный тестовый пост:

```powershell
uv run python -m aibot.verify_integrations --service telegram --publish-telegram-test
```

Результат текущей проверки зафиксирован в
[docs/integration-verification-report.md](docs/integration-verification-report.md).

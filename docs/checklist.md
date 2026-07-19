# Project Checklist

## Документация

- [x] Исходное задание проанализировано.
- [x] Создана проектная документация.
- [x] Описана архитектура.
- [x] Описана модель данных.
- [x] Описан API.
- [x] Описан Celery pipeline.
- [x] Описаны внешние интеграции.
- [x] Описан план разработки.
- [ ] Документация прочитана и согласована владельцем проекта.
- [x] Создан каркас Python-файлов с описательными docstring.
- [x] Выбрана версия Python 3.12.
- [x] Создан `pyproject.toml` с зависимостями проекта.
- [x] Создан `.python-version`.
- [x] Описан выбор runtime и зависимостей.
- [x] Создан `docker-compose.yml` для PostgreSQL и Redis.
- [x] Зафиксирован обязательный acceptance-набор для базовой сборки.

## Backend

- [x] Создан FastAPI-проект.
- [x] Создана модульная структура проекта.
- [x] Добавлен healthcheck.
- [x] Подключена конфигурация через `.env`.
- [x] Подключена PostgreSQL-база данных.
- [x] Созданы модели данных.
- [x] Каждая основная ORM-модель вынесена в отдельный файл.
- [x] Созданы Pydantic-схемы.
- [x] Каждая группа Pydantic-схем вынесена в отдельный файл.
- [x] Созданы repository-файлы для основных сущностей.
- [x] Alembic настроен как единственный production-механизм схемы.
- [x] Добавлена начальная миграция для всех пяти ORM-моделей.
- [x] Проверен цикл `upgrade → check → downgrade → upgrade` на чистой PostgreSQL-БД.
- [x] Production bootstrap переведён с `create_all` на `alembic upgrade head`.

## API

- [x] CRUD источников.
- [x] CRUD ключевых слов.
- [x] Просмотр новостей.
- [x] Просмотр постов.
- [x] Просмотр ошибок.
- [x] Ручная генерация поста.
- [x] Ручной запуск парсинга.
- [x] Ручная публикация поста.
- [x] Swagger доступен по `/docs`.

## Парсинг и фильтрация

- [x] Универсальный сетевой RSS/Atom parser.
- [x] Telegram parser.
- [x] Нормализация новости.
- [x] Дедупликация по URL.
- [x] Дедупликация по content hash.
- [x] Фильтрация по разрешённым языкам.
- [x] Фильтрация по ключевым словам.
- [x] Статусы обработки новости.
- [x] `ErrorLog(scope="parser")` с привязкой к источнику.
- [x] Изоляция сбоя одного источника при batch-парсинге.
- [x] Безопасные детали parser-ошибок без traceback и секретов.

## AI

- [x] AI client.
- [x] Prompt builder.
- [x] Обработка rate limit.
- [x] Обработка timeout.
- [x] Внедряемый AI test double для тестов без runtime fake-режима.
- [x] Сохранение сгенерированного поста.
- [x] Безопасный `ErrorLog(scope="ai")` с привязкой к новости.
- [x] PostgreSQL row lock против конкурентной генерации.

## Celery

- [x] Celery app.
- [x] Worker entrypoint.
- [x] Parsing task.
- [x] Filtering task.
- [x] Generation task.
- [x] Publishing task.
- [x] Full pipeline task.
- [x] Celery Beat расписание каждые 30 минут.
- [x] Beat запускает полный parse → generate → publish pipeline.
- [x] Interval и batch limits pipeline настраиваются через env.
- [x] Retry-настройки.
- [x] Тяжёлые API endpoints возвращают `202` и `task_id`.
- [x] Parser retry выполняется только для временных HTTP-ошибок.
- [x] Общий `ErrorLog(scope="celery")` для окончательных task failures.

## Telegram

- [x] Telethon client.
- [x] Dry-run чтение Telegram-источника.
- [ ] Чтение публичных каналов.
- [ ] Публикация в целевой канал.
- [x] Защита от повторной публикации.
- [x] Логирование ошибок публикации.
- [x] `TELEGRAM_DRY_RUN`.
- [x] Worker использует только заранее авторизованную Telethon session без prompt.
- [x] Добавлена отдельная команда первичной Telegram-авторизации.
- [x] Добавлен безопасный live-verifier OpenAI/Telegram.
- [x] Реальный OpenAI-запрос дошёл до Responses API через `codex-ai==0.2.5`.
- [ ] Успешная реальная OpenAI-генерация — внешний blocker: API quota.
- [ ] Real-mode Telegram verification — отсутствуют credentials, target и session.

## Сдача

- [x] README с описанием.
- [x] README с запуском.
- [x] README с примерами API-запросов.
- [x] Локальный demo-сценарий с реальным AI и Telegram dry-run.
- [x] DB-backed smoke-сценарий прототипа.
- [x] `.env.example`.
- [x] GitHub-репозиторий.
- [x] Ссылка на репозиторий подготовлена для преподавателя.
- [x] Результаты live-проверки интеграций зафиксированы без секретов.

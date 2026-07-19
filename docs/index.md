# Project M4 Documentation

Эта папка описывает будущий проект до написания кода. Сначала читаем и согласовываем документы, потом реализуем сервис по ним.

## Что строим

Project M4 - backend-сервис для автоматизации новостного Telegram-канала:

1. Собирает новости с сайтов и публичных Telegram-каналов.
2. Фильтрует новости по источникам, ключевым словам, языку и дублям.
3. Генерирует короткий Telegram-пост через AI API.
4. Публикует готовый пост в Telegram-канал.
5. Дает REST API для ручного управления и мониторинга.

## Документы

- [project-brief.md](project-brief.md) - краткое описание продукта, цели и границы MVP.
- [architecture.md](architecture.md) - архитектура приложения и основные модули.
- [data-model.md](data-model.md) - сущности, статусы и связи данных.
- [api-design.md](api-design.md) - план REST API и основные эндпоинты.
- [celery-pipeline.md](celery-pipeline.md) - фоновые задачи и пайплайн обработки.
- [integrations.md](integrations.md) - внешние сервисы: OpenAI, Telethon, источники новостей.
- [development-plan.md](development-plan.md) - порядок разработки по этапам.
- [runtime-and-dependencies.md](runtime-and-dependencies.md) - версия Python и зависимости проекта.
- [checklist.md](checklist.md) - чеклист готовности проекта к сдаче.

## Project Agent Skills

В [agent-skills](agent-skills/) лежат правила для Codex, которые нужно читать перед будущими правками:

- `m4-backend` - общие backend-правила и структура проекта.
- `m4-api` - правила для FastAPI, схем и эндпоинтов.
- `m4-celery-pipeline` - правила для Celery, очередей и фоновой обработки.
- `m4-integrations` - правила для AI, Telegram и парсеров.

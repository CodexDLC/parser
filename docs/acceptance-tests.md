# Acceptance Tests

## Назначение

Обязательный acceptance-набор подтверждает базовую готовность Project M4:

1. Зависимости синхронизируются в Python 3.12 окружение.
2. `docker-compose.yml` валиден.
3. PostgreSQL и Redis запускаются и проходят healthcheck.
4. Ruff не находит lint-ошибок.
5. Mypy не находит ошибок типизации.
6. Unit и integration тесты проходят без инфраструктурных skip.
7. AI pipeline проверяется с внедрённым test double без внешних ключей и API-вызовов.
8. FastAPI-приложение импортируется с production AI wiring.
9. Alembic initial revision на отдельной PostgreSQL-БД проходит
   `upgrade → check → downgrade → upgrade`.
10. Выключенный кабинет не добавляет routes, а включённая shell требует
    authentication, Redis-backed session и CSRF.
11. Cabinet security tests проверяют login rate limit, secure cookie, logout
    invalidation, headers и реальный Redis round-trip.
12. Dashboard metrics сверяются с реальной PostgreSQL, а весь overview ограничен
    пятью SQL-запросами без N+1.
13. Passive health использует только cached Redis PING и не вызывает OpenAI,
    Telegram или Celery worker.
14. Read-only entity pages проверяют фильтры, server-side pagination, 404 и
    HTML escaping.
15. Alembic создаёт `PipelineRun`, `AdminAuditLog` и `Keyword.updated_at`, а
    migration chain проходит `upgrade → check → downgrade → upgrade`.
16. Source/Keyword mutations требуют session-bound CSRF, используют optimistic
    version и пишут успешный/отклонённый audit.
17. Повторный idempotency key создаёт один `PipelineRun` и одну Celery-задачу;
    status polling не раскрывает payload или credentials.
18. Конкурентная публикация блокируется PostgreSQL row lock до Telegram-вызова.

## Запуск

Из корня проекта:

```powershell
.\scripts\acceptance.ps1
```

Скрипт самостоятельно запускает PostgreSQL и Redis. Контейнеры после проверки остаются
запущенными для локальной разработки.

## Обычный pytest и строгий режим

Обычный запуск разрешает пропуск integration-тестов, если инфраструктура недоступна:

```powershell
uv run pytest
```

Acceptance-режим запрещает такие пропуски:

```powershell
uv run pytest --require-infrastructure
```

Если PostgreSQL или Redis недоступны, команда завершается ошибкой.

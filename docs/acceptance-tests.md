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

# M4 Management Cabinet

## Назначение

`/docs` остаётся техническим Swagger-интерфейсом. `/cabinet` станет
server-rendered интерфейсом единственного оператора M4: наблюдение за pipeline,
управление источниками и фильтрами, запуск фоновых операций и подтверждаемая
публикация.

Интерфейс строится на строго закреплённом PyPI-релизе
`codex-fastapi-cabinet==0.1.0`. Локальный checkout
`C:\install\projects\codex_tools\codex-fast-api-cabinet` используется только как
документация и справочник по исходному коду. Runtime M4 не получает path/editable
override на локальный репозиторий.

## Границы ответственности

`codex-fastapi-cabinet` отвечает за:

- layout, sidebar, topbar и адаптивный базовый CSS;
- Jinja-шаблоны страниц и dashboard widgets;
- декларации модулей, страниц, actions и permissions;
- маршрутизацию кабинета и преобразование provider results в представление.

M4 отвечает за:

- single-admin authentication, session и logout;
- authorization, CSRF, login rate limit и security headers;
- SQLAlchemy sessions, repositories и транзакции;
- агрегирующие SQL-запросы для метрик;
- валидацию и прикладные операции;
- постановку Celery-задач и идемпотентность;
- `PipelineRun`, `AdminAuditLog`, ErrorLog и безопасные сообщения об ошибках.

Providers вызывают application services/repositories напрямую. HTTP-запросы M4 к
собственным `/api` endpoints запрещены. Бизнес-правила не дублируются в Jinja,
providers или action handlers.

## Маршруты и feature flags

| Настройка | Default | Контракт |
| --- | --- | --- |
| `CABINET_ENABLED` | `false` | Не монтировать кабинет до завершения security shell |
| `CABINET_MOUNT_PATH` | `/cabinet` | Отдельный mount, не пересекающийся с `/api` и `/docs` |
| `DOCS_ENABLED` | local: `true`, production: `false` | Явно разрешает Swagger/OpenAPI |
| `CABINET_TIMEZONE` | `Europe/Berlin` | IANA timezone календарных метрик кабинета |

Планируемые публичные исключения внутри mount:

- `/cabinet/login`;
- `/cabinet/static/*`.

Остальные `/cabinet/*` требуют действующую admin session. Logout является
изменяющей POST-операцией и требует CSRF.

## Single-admin security contract

Таблица пользователей и RBAC в текущий scope не входят. Единственный оператор
настраивается через environment:

- `CABINET_USERNAME`;
- `CABINET_PASSWORD_HASH` с Argon2id hash, без plaintext password;
- `CABINET_SESSION_SECRET` достаточной случайной длины;
- `CABINET_SESSION_TTL_SECONDS`.

Session cookie должна быть подписанной, `HttpOnly`, `SameSite=Lax`, с `Secure=true`
в production. После login session ID ротируется, logout инвалидирует session.
Изменяющие формы используют отдельный непредсказуемый CSRF token и constant-time
сравнение. Login ограничивается по IP и username через Redis.

Все cabinet responses получают `Cache-Control: no-store`, CSP, запрет MIME sniffing
и frame embedding. В production Swagger отключён по умолчанию; осознанное включение
выполняется только через `DOCS_ENABLED=true`.

## Threat model

| Угроза | Обязательная защита |
| --- | --- |
| Анонимный доступ | Security boundary на весь cabinet mount |
| Brute force login | Redis rate limit без раскрытия существования username |
| CSRF | Session-bound token на каждой мутации |
| Session theft/fixation | Secure cookie flags, rotation, TTL и logout invalidation |
| Stored XSS из RSS/Telegram/AI/ErrorLog | Autoescape, запрет `safe`, CSP и XSS tests |
| Утечка секретов | Не отображать DSN, keys, hashes, session strings и provider payload |
| Повторный action click | Idempotency key, domain locks и подтверждение |
| Lost update | Проверка `updated_at`/version при сохранении формы |
| N+1/неограниченный список | Агрегирующий SQL, server pagination и query-count tests |
| Платный/опасный health check | Только passive/cached snapshot без AI call или Telegram send |
| Сбой worker после enqueue | `PipelineRun` lifecycle, stale detection и reconciliation |

Недоверенные тексты выводятся только как escaped plain text. Если позже появится
форматированный preview, он требует allow-list sanitizer; необработанный HTML и
`javascript:` URLs запрещены.

## Модули кабинета

1. **Обзор** — метрики, графики 7/30 дней, последние события, passive health.
2. **Источники** — список, карточка, форма и ручной parse.
3. **Ключевые слова** — список, создание, изменение и enable/disable.
4. **Новости** — фильтры, карточка, исходный текст и запуск генерации.
5. **Посты** — preview, статусы и подтверждаемая публикация.
6. **Ошибки** — read-only ErrorLog с фильтрами по scope.
7. **Pipeline** — история и состояние `PipelineRun`, ручной полный запуск.
8. **Аудит** — read-only журнал административных мутаций.

Базовые templates и CSS библиотеки сохраняются. M4 переопределяет только brand
name, русские подписи, цвета статусов, необходимые empty/error states и при
необходимости логотип.

## Разрешённые операции

Без подтверждения:

- просмотр dashboard, списков, карточек и истории;
- фильтрация, поиск, сортировка и пагинация.

С CSRF и аудитом:

- создать или изменить Source;
- включить или отключить Source;
- создать или изменить Keyword;
- включить или отключить Keyword.

С CSRF, подтверждением, аудитом и idempotency:

- поставить parsing Source в Celery;
- поставить generation NewsItem в Celery;
- запустить полный pipeline;
- опубликовать готовый Post в Telegram.

Физическое удаление доменных данных, изменение секретов из UI, произвольный prompt,
выполнение shell-команд и синхронное ожидание Celery-задач не входят в scope.

## PipelineRun и AdminAuditLog

`PipelineRun` добавляется до первой управляющей Celery-кнопки и хранит:

- инициатора `beat`, `cabinet` или `api`;
- тип операции, entity ID и безопасные параметры;
- Celery `task_id`;
- `queued`, `running`, `succeeded`, `failed`, `revoked` или `stale`;
- timestamps, счётчики результата и безопасную категорию ошибки.

Worker обновляет lifecycle. Периодический reconciliation помечает зависшие записи и
согласует retry/revoke после перезапуска. Политика retention определяется до
production rollout.

`AdminAuditLog` фиксирует успешные и отклонённые мутации: тип действия, entity ID,
время, безопасный actor identifier и результат. Пароли, CSRF tokens, cookies,
provider payload и секреты не сохраняются.

## Acceptance

Обязательные проверки:

- зависимость установлена из PyPI и закреплена exact pin;
- кабинет полностью отсутствует при `CABINET_ENABLED=false`;
- production Swagger выключен без явного `DOCS_ENABLED=true`;
- анонимный, expired и поддельный session доступ отклоняются;
- login rate limit, session rotation, logout и CSRF проверены;
- stored XSS payload не исполняется ни в одном типе страницы;
- метрики совпадают с контрольными SQL-запросами;
- empty database и server pagination работают;
- query-count tests не обнаруживают N+1;
- каждый action использует service/Celery port, а не self-HTTP;
- повторный/конкурентный action не создаёт дубли;
- `PipelineRun` восстанавливается после retry, revoke и worker failure;
- health widgets не вызывают AI provider-ы и не отправляют Telegram message;
- Alembic проходит upgrade/check/downgrade/upgrade;
- Ruff, Mypy, Pytest и responsive browser smoke проходят;
- `.env`, password hash, session secret и session files не попадают в Git.

## Этапы реализации

После каждого этапа выполняются относящиеся к нему проверки, предоставляется отчёт
и работа останавливается до явной команды пользователя.

0. Контракт, threat model, feature flags и exact dependency.
1. Защищённая shell, single-admin login/session/logout и CSRF.
2. Read-only dashboard и passive health snapshot.
3. Read-only entity lists/details с фильтрами и пагинацией.
4. `PipelineRun`, `AdminAuditLog`, migration и reconciliation.
5. Безопасный CRUD Source/Keyword.
6. Celery actions, idempotency и polling состояния.
7. Preview и подтверждаемая Telegram publication.
8. Security/regression acceptance, документация, commit и push.

Текущий статус:

- этап 0 завершён;
- этап 1 завершён: shell, single-admin login, opaque signed cookie, Redis session,
  CSRF logout, login rate limit и security headers;
- этап 2 завершён: read-only метрики, 7-дневные графики, последние посты/ошибки,
  request-scoped SQL snapshot и passive/cached health без AI/Telegram вызовов;
- этап 3 завершён: read-only списки и карточки Source, Keyword, NewsItem, Post и
  ErrorLog, server-side фильтры и пагинация;
- этап 4 завершён: `PipelineRun`, `AdminAuditLog`, migration, lifecycle и
  периодический stale reconciliation;
- этап 5 завершён: Source/Keyword формы, общий CSRF boundary, row lock,
  optimistic `updated_at` и audit;
- этап 6 завершён: idempotent Celery actions, полный pipeline, persisted task
  lifecycle и authenticated status polling;
- этап 7 завершён: escaped preview, явное подтверждение публикации и PostgreSQL
  row lock до завершения Telegram-вызова;
- этап 8 завершён: полный security/regression acceptance, документация,
  единый финальный commit и push в `origin/main`.

## Rollout и rollback

1. Применить migration независимо от включения UI.
2. Развернуть backend с `CABINET_ENABLED=false`.
3. Выполнить smoke и security checks.
4. Включить кабинет только после настройки admin secrets.
5. При проблеме отключить feature flag без отката API/Celery.

Rollback миграций допускается только после проверки отсутствия нужных audit/run
данных и отдельного подтверждения оператора.

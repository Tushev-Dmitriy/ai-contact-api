# План реализации AI Contact API

## 1. Итоговая архитектура

Проект реализуется как один FastAPI-сервис — модульный монолит со слоистой
архитектурой:

```text
HTTP / middleware
        ↓
API endpoints + Pydantic schemas
        ↓
application services
        ↓
repositories  → PostgreSQL
integrations  → Redis / AI / SMTP
```

Endpoint отвечает за HTTP-контракт, service — за сценарий использования,
repository — за SQLAlchemy-запросы, integration adapters — за внешние системы.
Небольшие `Protocol` нужны только на границах AI и email, где тестовые/fallback
реализации действительно заменяются. Общие base repository, фабрики и DI-
контейнер не вводятся: зависимости создаются в FastAPI dependency functions.

Предлагаемая структура:

```text
app/
  api/v1/endpoints/{contact,health,metrics}.py
  api/v1/router.py
  core/{config,exceptions,logging,security}.py
  db/models/contact_request.py
  db/{base,session}.py
  integrations/ai/{base,fallback,openai_compatible}.py
  integrations/email/{base,disabled,smtp}.py
  middleware/{body_limit,request_context}.py
  repositories/{contact,metrics}.py
  schemas/{ai,contact,error,health,metrics}.py
  services/{contact,rate_limit}.py
  utils/{normalization,pii}.py
  main.py
alembic/
tests/{unit,integration}/
docs/
bruno/
scripts/
```

Корректировки исходной структуры минимальны: модели и интеграции разнесены по
файлам, middleware разделены по одной ответственности, добавлены отдельные
error/health/metrics schemas и Bruno collection.

## 2. Ключевой сценарий

1. Middleware проверяет размер запроса, устанавливает request ID и безопасный
   client identity.
2. Pydantic нормализует и валидирует контакт.
3. Redis limiter атомарно увеличивает счётчик с TTL; при сбое действует
   fail-open.
4. Service сохраняет `processing` request в короткой транзакции.
5. AI adapter возвращает валидированный результат или детерминированный
   fallback; service сохраняет его.
6. API планирует одну background-задачу отправки обоих писем и возвращает 202.
7. Background-задача создаёт собственную DB session, по отдельности фиксирует
   оба email status и итоговый processing status. Ошибки логируются безопасно.

Это не надёжная production-очередь: процесс может завершиться после ответа, но
до отправки. Ограничение честно документируется; production-улучшение —
transactional outbox и внешний worker.

## 3. Зависимости

### Runtime

- `fastapi`, `uvicorn[standard]`
- `pydantic`, `pydantic-settings`, `email-validator`
- `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
- `redis` (async client)
- `httpx`

SMTP реализуется стандартной библиотекой (`smtplib`, `email.message`) через
`asyncio.to_thread`, поэтому отдельная зависимость не нужна. Стандартный
`logging` с `RotatingFileHandler` достаточен вместо structlog.

### Development

- `pytest`, `pytest-asyncio`, `pytest-cov`
- `ruff`, `mypy`
- `aiosqlite` только для быстрых repository tests, если семантика PostgreSQL не
  важна; PostgreSQL-specific integration tests используют Compose
- `pre-commit`

### Явно не добавляются

OpenAI SDK не обязателен: `httpx` лучше соответствует OpenAI-compatible
base URL и сохраняет малый dependency surface. Также не нужны Celery, task
broker, Loguru, DI framework и frontend packages.

## 4. Этапы и критерии готовности

### Этап 1. Анализ и планирование

- Сверить PDF и расширенное ТЗ.
- Зафиксировать обязательные/дополнительные требования, трассировку,
  архитектуру, зависимости и спорные решения.
- Проверка: Markdown читается, diff содержит только документацию.
- Коммит: `docs: analyze requirements and define implementation plan`.

### Этап 2. Каркас и инструменты

- Создать uv-проект, `pyproject.toml`, lock-файл, пакеты, `.env.example`,
  `.gitignore`, Makefile и минимальный app factory.
- Настроить Ruff/mypy/pytest/pre-commit.
- Коммит: `chore: initialize FastAPI project and development tooling`.

### Этап 3. Конфигурация и request context

- Централизовать settings и environment validation.
- Добавить body limit, request ID, structured safe logging в stdout/file,
  ротацию и PII helpers.
- Коммит: `feat: add application configuration and request logging`.

### Этап 4. Persistence

- Настроить async engine/session, модель и репозиторий.
- Добавить Alembic и начальную PostgreSQL migration с оправданными индексами.
- Коммит: `feat: add contact persistence and database migrations`.

### Этап 5. Contact API

- Реализовать schemas, normalization, service skeleton, endpoint и 202/error
  contracts.
- До появления реальных adapters использовать явные тестовые зависимости.
- Коммит: `feat: implement contact request API`.

### Этап 6. Redis rate limiting

- Добавить atomic Redis counter/TTL, configurable limits, trusted proxy logic
  и fail-open.
- Коммит: `feat: add Redis-backed contact rate limiting`.

### Этап 7. AI

- Реализовать Protocol, hardened prompt, OpenAI-compatible httpx adapter,
  selective retry и fallback.
- Валидировать structured JSON и безопасное логирование.
- Коммит: `feat: integrate AI contact classification with fallback`.

### Этап 8. Email

- Реализовать safe templates, SMTP/disabled adapters и background orchestration
  с независимыми status updates.
- Коммит: `feat: add contact email notifications`.

### Этап 9. Ошибки

- Добавить доменные исключения и глобальные handlers, проверить отсутствие
  traceback/internal details в ответах.
- Коммит: `feat: standardize API error handling`.

### Этап 10. Health и metrics

- Добавить live/ready dependency checks, агрегаты и скрываемый API-key protected
  endpoint.
- Коммит: `feat: add health checks and contact metrics`.

### Этап 11. Контейнеризация

- Добавить non-root multi-stage/slim Dockerfile, Compose и health checks.
- Миграции сделать отдельной явной командой, не запускать конкурентно каждым
  web worker.
- Коммит: `build: containerize API and dependencies`.

### Этап 12. Тесты

- Покрыть все перечисленные unit и API/integration сценарии.
- Fakes/dependency overrides исключают обращения к реальным AI/SMTP.
- Коммит: `test: cover critical contact processing scenarios`.

### Этап 13. CI и API collection

- Добавить GitHub Actions (Ruff, mypy, pytest, Docker build), Bruno collection
  и окончательные developer commands.
- Коммит: `ci: add automated quality checks`.

### Этап 14. Документация

- Заполнить README и требуемые ARCHITECTURE/AI_USAGE/DEPLOYMENT/SECURITY/
  DECISIONS документы; проверить curl/OpenAPI/Windows commands.
- Коммит: `docs: document architecture setup API and AI usage`.

### Этап 15. Финальный аудит

- Выполнить requirements trace, secret scan, clean-clone/Compose smoke test,
  migration, full lint/typecheck/tests и Docker build.
- Исправлять только подтверждённые дефекты; не придумывать метрики.
- Коммит при наличии изменений:
  `refactor: finalize test task implementation`.

## 5. Проверки после каждого этапа

По мере появления инструментов:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest
git diff --check
git status --short
```

Дополнительно запускаются релевантные migration/Compose/Docker проверки.
Невыполненная из-за внешней зависимости проверка указывается как
`not run`, а не `passed`. Перед коммитом обновляется трассировка требований и
проверяется staged diff. Push не выполняется.

## 6. Рекомендуемые решения по спорным вопросам

| Вопрос | Рекомендуемое решение | Причина |
|---|---|---|
| `/api/contact` или `/api/v1/contact` | Только `/api/contact` | Прямое решение заказчика: публичные маршруты должны точно соответствовать PDF |
| SMTP failure response | `202`, статусы в БД | Соответствует прямо указанному предпочтительному flow |
| Фоновые задачи | FastAPI `BackgroundTasks` | Достаточно для тестового; ограничение документируется |
| Redis outage | Fail-open + warning | Приём контакта важнее антиспам-функции |
| Metrics без ключа | `404 Not Found` | Не раскрывает административную поверхность |
| AI client | `httpx` adapter | Поддерживает compatible endpoints без лишнего SDK |
| Logging | stdlib structured formatter | Меньше зависимостей, есть ротация и два handler |
| Phone normalization | E.164-compatible 7–15 digits | Интернационально и объяснимо |
| IP protection | HMAC-SHA256 с обязательной production salt | Стабильный псевдоним без открытого IP |
| Integration database | PostgreSQL в Compose | SQLite не проверяет PostgreSQL-specific поведение |
| Production jobs | Outbox/worker только как рекомендация | Не раздувает scope текущего задания |

## 7. Риски

- `BackgroundTasks` не гарантирует доставку после падения процесса.
- Rate limit по IP требует корректной конфигурации trusted proxy.
- Файловые логи на Render/Railway эфемерны.
- OpenAI-compatible providers могут различаться форматом structured output;
  adapter должен валидировать ответ и уходить в fallback.
- Проверка отдельных email status должна переживать частичный SMTP-сбой.
- DB запись до фоновой отправки требует новой session внутри background task,
  а не повторного использования request-scoped session.

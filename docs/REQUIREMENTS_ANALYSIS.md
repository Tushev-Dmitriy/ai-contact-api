# Анализ требований AI Contact API

## 1. Источники и приоритет требований

Анализ выполнен по исходному PDF `Тест.pdf` (4 страницы) и расширенному
техническому заданию, приложенному к репозиторию. PDF задаёт минимальный
результат, а расширенное ТЗ конкретизирует реализацию и вводит более строгие
ограничения. Если требования различаются, принимается более строгий вариант из
расширенного ТЗ при сохранении функционального смысла PDF.

Статусы в таблице: `planned` — запланировано; `in progress` — частично
реализовано; `optional` — дополнительное; `decision` — требуется
зафиксированное архитектурное решение; `done` — выполнено.

## 2. Обязательные требования

### 2.1. API и поток обработки

- Реализовать backend без Django и без frontend до завершения его тестирования.
- Предоставить `POST /api/v1/contact` с полями `name`, `phone`, `email`,
  `comment`.
- После trim имя должно содержать 2–100 символов, комментарий — 10–3000;
  email должен быть валидным, телефон — разумно валидироваться без привязки к
  одной стране. Пустые и состоящие из пробелов строки запрещены.
- Нормализовать ввод, ограничить размер тела и всех строк, не исполнять
  пользовательские HTML/Markdown и не раскрывать внутренние исключения.
- Выполнять полный цикл: валидация → rate limit → запись со статусом
  `processing` → AI-классификация → сохранение результата → планирование двух
  писем → обновление статусов → понятный ответ.
- После успешного сохранения возвращать `202 Accepted`; ответ содержит только
  `request_id`, `status`, `message` и, при необходимости, безопасную AI-категорию.
- Сбой AI не отменяет сохранение и стандартные письма. Письма выполняются через
  `BackgroundTasks`; SMTP-сбои сохраняются в БД и логируются.
- Использовать единый формат ошибок с `code`, `message`, `details`,
  `request_id`; обработать validation/HTTP/rate-limit/database/unknown errors
  со статусами 400, 422, 429, 500 и 503 по смыслу.

### 2.2. AI

- Реализовать заменяемые через `Protocol` OpenAI-compatible и fallback
  провайдеры.
- Результат строго валидируется Pydantic-схемой: категории `job_offer`,
  `project_request`, `collaboration`, `support`, `feedback`, `spam`, `other`;
  sentiment `positive|neutral|negative`; urgency `low|medium|high`; summary
  не более 200 символов.
- Защитить системную инструкцию от prompt injection, считать комментарий
  данными, требовать только JSON и не включать лишние персональные данные.
- Настроить timeout и ограниченные повторы лишь для временных сетевых ошибок,
  429 и 5xx; не повторять конфигурационные и прочие 4xx ошибки.
- Не логировать ключ и полный комментарий.
- При недоступности AI возвращать `other/neutral/low/null/unavailable`; сервис
  должен запускаться без `AI_API_KEY`.
- Централизованно читать `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`,
  `AI_TIMEOUT_SECONDS`, `AI_ENABLED`.

### 2.3. Email

- Отправлять владельцу request ID, контактные данные, комментарий, AI-результат
  и дату; пользователю — нейтральное подтверждение без обещания срока ответа.
- Формировать безопасное plain-text письмо (HTML необязателен), исключить
  header injection.
- Поддержать SMTP-настройки из ТЗ. При `EMAIL_ENABLED=false` использовать
  заглушку, логирующую только безопасный факт попытки.
- Не логировать SMTP-пароль или содержимое с персональными данными.

### 2.4. Данные и rate limiting

- Использовать PostgreSQL, async SQLAlchemy 2.0 и Alembic.
- Создать `contact_requests` с UUID, исходными полями, AI-результатом,
  processing/email-статусами, nullable IP hash и ограниченным user agent,
  `created_at`, `updated_at`.
- Не хранить открытый IP; хешировать его серверной солью. Индексировать только
  оправданные поля: `created_at`, `category`, `processing_status` и при
  подтверждённой необходимости email.
- Реализовать Redis-счётчик rate limit с TTL; default — 5 запросов за 15 минут
  на IP, параметры задаются через env.
- При недоступности Redis использовать документированный fail-open и warning.
- Доверять `X-Forwarded-For` только при `TRUST_PROXY_HEADERS=true`.

### 2.5. Наблюдаемость, health и metrics

- Логировать в stdout и ротируемый файл request ID, метод, путь, статус,
  длительность, безопасный IP hash и обработанные исключения.
- Не логировать секреты, тела запросов, полные comment/phone/email.
- Принимать безопасный `X-Request-ID`, иначе генерировать UUID; возвращать его
  заголовком.
- Предоставить health API с liveness и readiness. PostgreSQL критичен; Redis и
  AI отражаются в деталях, но не блокируют при выбранных fallback-стратегиях.
- Предоставить защищённую продуктовую статистику: total/today, категории,
  sentiment, email failures, AI fallback count. Ключ — `METRICS_API_KEY` в
  `X-API-Key`; при отсутствии настройки endpoint скрывается как 404.

### 2.6. Конфигурация, API-документация и безопасность

- Использовать `pydantic-settings`, `.env.example`, безопасные development
  defaults, `APP_ENV` и строгую production-валидацию; `.env` не коммитить.
- Настроить CORS allowlist через `CORS_ALLOWED_ORIGINS`; не сочетать `*` с
  credentials. Development defaults разрешают только явные localhost origins.
- Предоставить `/docs`, `/redoc`, `/openapi.json` с версией, описанием,
  безопасным contact, тегами, примерами и документированными ошибками.
- Не использовать `eval/exec`; не хранить секреты; применять timeout внешних
  вызовов; защищать metrics API key; ограничивать ввод и безопасно работать с
  HTML/Markdown.
- Архитектура — понятный модульный монолит со слоями API, service, repository и
  integrations; без избыточных паттернов.

### 2.7. Поставка, тесты и документация

- Python 3.12, FastAPI, Pydantic v2, async SQLAlchemy, Alembic, PostgreSQL,
  Redis, httpx/OpenAI-compatible API, SMTP, Docker Compose, pytest,
  pytest-asyncio, Ruff, mypy и uv.
- Добавить Dockerfile, `.dockerignore`, Compose-сервисы api/postgres/redis и
  health checks. API запускается не от root на slim image, без секретов,
  через uvicorn; миграции выполняются явной командой/startup script.
- Добавить unit-тесты schema validation, AI fallback/valid/invalid response,
  PII masking, disabled email; API/integration-тесты success, validation,
  rate limit, AI outage, DB outage, health, metrics auth, request ID и CORS.
  Реальные AI/SMTP в тестах запрещены.
- Настроить Ruff lint/format, mypy, pytest, Makefile-команды из ТЗ и
  необязательный pre-commit. В README дать Windows-эквиваленты.
- CI устанавливает зависимости, запускает Ruff/mypy/pytest и собирает Docker
  image без реального деплоя и секретов.
- Подготовить подробный README со всеми 26 разделами из расширенного ТЗ,
  архитектурную/AI/deployment/security/decisions документацию и Postman либо
  Bruno collection.
- Подготовить проект к Render или Railway, но не выполнять деплой без прямого
  указания. Если рабочего URL нет, дать локальную инструкцию.
- Честно документировать использование Codex и ручную проверку.
- Работать отдельными этапами и коммитами, выполнять доступные проверки,
  проверять diff, не делать push.

## 3. Дополнительные требования

- Отдельный `/metrics` в формате Prometheus.
- HTML-версия писем при сохранении безопасного plain-text варианта.
- Frontend после полного завершения и тестирования backend.
- Индекс по email, только если появится реальный query pattern.
- Рабочий публичный деплой предпочтителен в исходном PDF, но расширенное ТЗ
  прямо запрещает выполнять его без отдельного указания; локальная инструкция
  является допустимой альтернативой.

## 4. Трассировка

| Требование | Способ реализации | Предполагаемые файлы | Статус |
|---|---|---|---|
| Анализ и план | Сопоставить PDF и расширенное ТЗ, зафиксировать решения | `docs/REQUIREMENTS_ANALYSIS.md`, `docs/IMPLEMENTATION_PLAN.md` | done |
| Contact API и validation | Pydantic v2 schema, FastAPI endpoint, orchestration service | `app/schemas/contact.py`, `app/api/v1/endpoints/contact.py`, `app/services/contact.py` | done |
| Persistence | Async SQLAlchemy repository, PostgreSQL model, Alembic migration | `app/db/models/contact_request.py`, `app/repositories/contact.py`, `alembic/` | done |
| AI classification/fallback | Protocol, httpx provider, validated JSON, fallback | `app/integrations/ai/`, `app/schemas/ai.py` | done |
| Email notifications | SMTP and disabled providers, BackgroundTasks, safe messages | `app/integrations/email/`, `app/services/contact.py` | done |
| Redis rate limit | Atomic counter with TTL, fail-open | `app/services/rate_limit.py`, `app/core/config.py` | done |
| Request ID and logging | Middleware, JSON/structured stdlib logging, rotating file | `app/middleware/request_context.py`, `app/core/logging.py` | done |
| Error contract | Typed app exceptions and global handlers | `app/core/exceptions.py`, `app/main.py` | done |
| Health/readiness | Separate live/ready handlers and dependency checks | `app/api/v1/endpoints/health.py` | done |
| Protected statistics | Aggregate SQL queries and constant-time API-key check; hidden when disabled | `app/api/v1/endpoints/metrics.py`, `app/repositories/metrics.py`, `app/core/security.py` | done |
| CORS and OpenAPI | Settings-driven middleware and FastAPI metadata/examples | `app/core/config.py`, `app/main.py`, endpoint schemas | planned |
| Central configuration | `BaseSettings`, env profiles/validation, safe example | `app/core/config.py`, `.env.example` | done |
| Docker/Compose | Non-root slim image, explicit migration command, health checks | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `scripts/` | done |
| Automated tests | Unit fakes and API dependency overrides; no live providers | `tests/unit/`, `tests/integration/` | planned |
| Quality and CI | uv, Ruff, mypy, pytest, pre-commit, Actions | `pyproject.toml`, `uv.lock`, `Makefile`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml` | in progress |
| Documentation and API examples | README, focused docs, Bruno collection | `README.md`, `docs/`, `bruno/` | planned |
| Deployment readiness | Platform-neutral container guide and env/migration/health instructions | `docs/DEPLOYMENT.md`, `README.md` | planned |
| Prometheus metrics | Не входит в обязательный scope | возможный `app/api/metrics.py` | optional |
| Frontend | Только после backend, отдельным решением | вне текущего scope | optional |

## 5. Неоднозначности, противоречия и решения

1. **Маршрут:** PDF требует `/api/contact`, расширенное ТЗ —
   `/api/v1/contact`. Канонический маршрут — версионированный. Алиас старого
   пути не добавляется без требования: он удваивает поверхность API.
2. **Хранилище:** PDF допускает файлы и не требует БД; расширенное ТЗ требует
   PostgreSQL и Redis. Используются PostgreSQL/Redis как более строгий вариант.
3. **Rate limiting:** PDF допускает env/файлы, что само по себе не является
   корректным распределённым счётчиком. Используется Redis counter с TTL и
   fail-open.
4. **Синхронный полный цикл и `BackgroundTasks`:** поток из девяти шагов можно
   прочитать как синхронный, но предпочтительный вариант требует `202` после
   сохранения и фоновых писем. AI выполняется до ответа, письма — после;
   финальные email/processing statuses обновляются фоновой задачей.
5. **SMTP-сбой и HTTP-ответ:** выбран предпочтительный `202`; сбой виден в
   статусах БД и логах, но уже не может изменить отправленный HTTP-ответ.
6. **Metrics без ключа:** из двух разрешённых вариантов выбран `404`, чтобы не
   раскрывать наличие административного endpoint.
7. **Readiness:** PostgreSQL — единственная критическая зависимость. Redis/AI/
   SMTP диагностируются, но их деградация совместима с приёмом обращения.
8. **Логи в файл и ephemeral hosting:** локально выполняются оба требования —
   stdout и rotating file. В production stdout является источником истины, а
   долговременное хранение передаётся внешней системе.
9. **IP hash и rate-limit identity:** Redis-ключ и сохраняемое значение строятся
   через HMAC-SHA256 с отдельной серверной солью; открытый IP не сохраняется и
   не логируется.
10. **Телефон:** «разумная» проверка не задаёт стандарт. Рекомендуется trim,
    удаление визуальных разделителей, разрешение ведущего `+` и 7–15 цифр по
    E.164; хранить нормализованное значение.
11. **AI-категория в ответе:** чтобы контракт был предсказуемым, поле допускается
    как nullable и не содержит summary или внутренний provider status.
12. **Срок из PDF:** указан организационный дедлайн, а не характеристика
    программного продукта; он не превращается в runtime-требование.

## 6. Ограничения scope

Без отдельного обоснования не добавляются Celery, Kubernetes, RabbitMQ, Kafka,
GraphQL, микросервисы, CQRS, event sourcing, сложный DDD, регистрация,
админ-панель или frontend. Реальный deploy и push запрещены без прямого
указания.

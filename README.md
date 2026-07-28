# AI Contact API

Backend-сервис формы обратной связи для портфолио. Принимает обращение,
нормализует и сохраняет его, классифицирует текст через OpenAI-compatible API
или безопасный fallback и в фоне отправляет два email-уведомления.

## Возможности

- точный маршрут из задания: `POST /api/contact`;
- строгая Pydantic-валидация и ограничение тела запроса;
- PostgreSQL, async SQLAlchemy и Alembic;
- Redis rate limit: по умолчанию 5 запросов за 15 минут;
- заменяемые AI- и email-провайдеры;
- единый JSON-контракт ошибок и `X-Request-ID`;
- health/readiness, защищённая продуктовая статистика, CORS allowlist;
- Docker Compose, Postman, pytest, Ruff, строгий mypy и GitHub Actions.

## Стек

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), PostgreSQL, Alembic,
Redis, httpx, SMTP, uv, pytest, Ruff, mypy и Docker Compose.

## Архитектура и поток запроса

Проект — модульный монолит со слоями API → services → repositories →
database/integrations. Подробности находятся в
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

`POST /api/contact` выполняет:

1. ограничение размера и валидацию/нормализацию;
2. Redis rate limit по HMAC-хэшу IP;
3. сохранение обращения со статусом `processing`;
4. AI-классификацию или детерминированный fallback;
5. сохранение результата;
6. постановку двух email в `BackgroundTasks`;
7. возврат `202 Accepted`; фон обновляет статусы отправки в БД.

## Быстрый запуск через Docker Compose

Требуются Docker и Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

В PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Compose поднимает PostgreSQL, Redis, локальную AI-модель llama.cpp и SMTP-сервер
Mailpit, выполняет `alembic upgrade head` отдельным контейнером и запускает
приложение. При первом запуске скачивается модель `SmolLM2-135M-Instruct`;
последующие
запуски используют Docker volume.

- интерфейс формы: `http://localhost:8000`;
- Swagger UI: `http://localhost:8000/docs`;
- перехваченные SMTP-письма: `http://localhost:8025`.

Mailpit не требует регистрации и не отправляет письма во внешний интернет:
оба уведомления можно безопасно посмотреть в его веб-интерфейсе.

Проверка:

```bash
curl http://localhost:8000/api/health/ready
```

Остановка: `docker compose down`. Данные сохраняются в именованных volumes;
для полного локального удаления данных применяется `docker compose down -v`.

## Локальный запуск

Нужны Python 3.12, [uv](https://docs.astral.sh/uv/), PostgreSQL и Redis.

```bash
cp .env.example .env
uv sync --frozen --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

PowerShell использует `Copy-Item .env.example .env`; остальные команды те же.
В `.env` нужно заменить `DATABASE_URL` и `REDIS_URL` под локальные сервисы.

## Конфигурация

Все настройки читаются из environment или `.env`.

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `APP_ENV` | `development`, `test` или `production` | `development` |
| `APP_HOST`, `APP_PORT` | адрес и порт приложения | `0.0.0.0`, `8000` |
| `APP_LOG_LEVEL`, `APP_LOG_FILE` | уровень и rotating-файл логов | `INFO`, `logs/app.log` |
| `REQUEST_BODY_MAX_BYTES` | максимум тела запроса | `16384` |
| `IP_HASH_SALT` | секрет HMAC для IP | только dev-значение |
| `TRUST_PROXY_HEADERS` | доверять `X-Forwarded-For` | `false` |
| `CORS_ALLOWED_ORIGINS` | JSON-массив разрешённых origins | localhost 3000/5173 |
| `DATABASE_URL` | DSN `postgresql+asyncpg` | локальная PostgreSQL |
| `REDIS_URL` | Redis DSN | `redis://localhost:6379/0` |
| `RATE_LIMIT_REQUESTS` | лимит обращений | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | окно лимита, секунды | `900` |
| `AI_ENABLED` | включить внешний AI | `false` |
| `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` | OpenAI-compatible provider | provider выключен |
| `AI_TIMEOUT_SECONDS` | timeout AI-запроса | `10` |
| `EMAIL_ENABLED` | включить SMTP | `false` |
| `SMTP_HOST`, `SMTP_PORT` | SMTP endpoint | порт `587` |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP-аутентификация | пусто |
| `SMTP_FROM_EMAIL`, `SMTP_OWNER_EMAIL` | отправитель и владелец | пусто |
| `SMTP_USE_TLS` | STARTTLS | `true` |
| `METRICS_API_KEY` | ключ статистики | endpoint скрыт |

При `APP_ENV=production` сервис запрещает dev DSN, короткий или стандартный
`IP_HASH_SALT`. Секреты нельзя коммитить; `.env.example` содержит только шаблон.

## Миграции

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade -1
```

Создание новой миграции после изменения моделей:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

В production миграция должна выполняться отдельным release/pre-deploy шагом.

## API

| Метод | Маршрут | Назначение |
|---|---|---|
| `POST` | `/api/contact` | создать обращение |
| `GET` | `/api/contacts` | последние 100 обращений и результаты обработки |
| `GET` | `/api/health` | сводное состояние |
| `GET` | `/api/health/live` | liveness |
| `GET` | `/api/health/ready` | readiness |
| `GET` | `/api/metrics` | защищённая продуктовая статистика |

Swagger UI: `http://localhost:8000/docs`; ReDoc:
`http://localhost:8000/redoc`; схема: `http://localhost:8000/openapi.json`.

### Создание обращения

```bash
curl -i -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "name": "Анна Иванова",
    "phone": "+7 (912) 345-67-89",
    "email": "anna@example.com",
    "comment": "Хочу обсудить разработку backend-сервиса."
  }'
```

Ответ `202`:

```json
{
  "request_id": "f5a881fd-4bee-4c83-91b9-f204619db856",
  "status": "accepted",
  "message": "Contact request accepted for processing",
  "category": "project_request"
}
```

Телефон сохраняется нормализованным; допустимы 7–15 цифр и один ведущий `+`.
Имя — 2–100, комментарий — 10–3000 символов. Неизвестные поля запрещены.

### Health и metrics

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/live
curl http://localhost:8000/api/health/ready
curl -H "X-API-Key: change-me" http://localhost:8000/api/metrics
```

PostgreSQL критичен для readiness. Redis и внешние интеграции отображаются в
диагностике, но поддерживают предусмотренную деградацию. Если
`METRICS_API_KEY` пуст, `/api/metrics` отвечает `404`; неверный ключ даёт `401`.

## Формат ошибок

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [],
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

Используются осмысленные статусы `400`, `404`, `413`, `422`, `429`, `500` и
`503`. При `429` возвращается `Retry-After`. Внутренние исключения и секреты
клиенту не раскрываются.

## AI и fallback

AI-провайдер вызывается через `httpx` по OpenAI-compatible API. Ответ допускает
только известные категории, sentiment, urgency и summary до 200 символов.
Повторы выполняются лишь для сетевых ошибок, `429` и `5xx`; timeout задаётся
через env. Пользовательский комментарий считается недоверенными данными.

В Docker Compose AI работает полностью локально через llama.cpp и модель
`SmolLM2-135M-Instruct`: ключ и внешний AI-сервис не нужны. При timeout, ошибке или
невалидном JSON используется результат
`other / neutral / low / null / unavailable`; обращение при этом не теряется.
Подробнее: [`docs/AI_USAGE.md`](docs/AI_USAGE.md).

## Email

SMTP-провайдер отправляет владельцу полные данные обращения и AI-результат, а
пользователю — нейтральное подтверждение. Письма plain-text; заголовки защищены
от CR/LF injection. Отправки независимы, их статусы и ошибки фиксируются в БД.
При `EMAIL_ENABLED=false` применяется безопасный disabled provider.

`BackgroundTasks` подходит для тестового задания, но не гарантирует доставку
после падения процесса. Для production нужен durable queue с retries и DLQ.

## Rate limiting

Redis Lua-скрипт атомарно увеличивает счётчик и устанавливает TTL. Identity —
HMAC-SHA256 от IP с серверной солью; исходный IP не хранится. При недоступности
Redis выбран документированный fail-open с warning, чтобы форма оставалась
доступной. Заголовкам proxy можно доверять только за доверенным reverse proxy.

## Логирование и наблюдаемость

Структурированные логи идут в stdout и rotating-файл. Записываются request ID,
метод, путь, статус, длительность и безопасный IP hash. Тело, полный
email/телефон/comment, API-ключи и SMTP-пароль не логируются.

Liveness проверяет процесс, readiness — PostgreSQL и состояние зависимостей.
`/api/metrics` — JSON-продуктовая статистика, а не Prometheus exposition.

## Тесты и качество

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app tests
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

PowerShell использует те же команды. Тесты работают на fakes/SQLite и не
обращаются к реальным AI или SMTP. Покрыты валидация, API success/error,
rate limit, AI fallback/retries, email, DB outage, request ID, health, metrics
и CORS.

GitHub Actions выполняет Ruff, строгий mypy, pytest и отдельно собирает Docker
image. Локальные сокращения доступны через `Makefile`; pre-commit включается
командой `uv run pre-commit install`.

## Postman

Импортируйте:

- `postman/AI Contact API.postman_collection.json`;
- `postman/Local.postman_environment.json`.

Выберите окружение `AI Contact API - Local`. Для metrics заполните локальную
переменную `metrics_api_key`. Коллекция содержит success/validation сценарии,
health, readiness и metrics с автоматическими проверками ответа.

## Безопасность

Основные меры: allowlist CORS, лимиты ввода, запрет extra-полей, HMAC IP,
rate limit, constant-time проверка metrics key, ограниченные timeout/retries,
защита AI prompt и email headers, безопасные ошибки и логи без PII/секретов.
Полная модель: [`docs/SECURITY.md`](docs/SECURITY.md).

## Компромиссы и production-улучшения

- `BackgroundTasks` заменить на Celery/RQ/Arq или broker-backed worker;
- добавить идемпотентность формы и transactional outbox;
- хранить секреты в secret manager, настроить TLS и trusted proxy;
- экспортировать Prometheus/OpenTelemetry и централизовать логи;
- добавить retention/удаление PII, backups и восстановление;
- запустить интеграционные тесты с настоящими PostgreSQL/Redis в CI;
- масштабировать rate limiting и добавить edge/WAF-защиту.

Архитектурные компромиссы описаны в
[`docs/DECISIONS.md`](docs/DECISIONS.md).

## Использование AI при разработке

Codex использовался для анализа PDF, проектирования, реализации, тестов,
документации и локальных проверок. Результат вручную сверялся с ТЗ, diff,
OpenAPI, тестами и Docker-конфигурацией. Конкретные проверки и исправления
перечислены в [`docs/AI_USAGE.md`](docs/AI_USAGE.md).

## Локальная демонстрация

Тестовое задание запускается одной командой `docker compose up --build`.
Публичный deployment URL не требуется: инструкция выше полностью описывает
локальный запуск API, базы данных, Redis, SMTP и тестового интерфейса.

## Дополнительная документация

- [`docs/REQUIREMENTS_ANALYSIS.md`](docs/REQUIREMENTS_ANALYSIS.md) — трассировка ТЗ;
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — этапы реализации;
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — компоненты и поток;
- [`docs/SECURITY.md`](docs/SECURITY.md) — угрозы и меры;
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — принятые решения;

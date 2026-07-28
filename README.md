# AI Contact API

Backend-сервис формы обратной связи для сайта-портфолио. Он принимает и
валидирует обращение, сохраняет его в PostgreSQL, запускает локальный
AI-анализ, отправляет два email через SMTP и возвращает результат обработки в
административный интерфейс.

## Возможности

- `POST /api/contact` с валидацией имени, телефона, email и комментария;
- классификация обращения, sentiment, urgency и краткое summary;
- fallback, при котором сбой AI не мешает принять обращение;
- письмо владельцу сайта и подтверждение пользователю;
- Redis rate limit: 5 обращений за 15 минут с одного IP по умолчанию;
- структурированные логи в stdout и ротируемый файл;
- единый формат ошибок и `X-Request-ID`;
- health/readiness и защищённая статистика;
- Swagger, ReDoc, Postman, Docker Compose и GitHub Actions;
- frontend для отправки формы и просмотра статусов обработки.

## Стек

- Python 3.12, FastAPI, Pydantic v2;
- async SQLAlchemy 2, Alembic, PostgreSQL;
- Redis;
- httpx и OpenAI-compatible API;
- llama.cpp и локальная `Qwen2.5-1.5B-Instruct Q4_K_M`;
- SMTP и Mailpit;
- uv, pytest, Ruff, mypy;
- Docker и Docker Compose.

FastAPI выбран из-за встроенной OpenAPI-документации и удобной асинхронной
модели. PostgreSQL и Redis не обязательны по исходному заданию, но позволяют
показать транзакционное хранение, миграции и атомарный rate limit.

## Архитектура

Проект реализован как модульный монолит:

```text
HTTP request
  -> middleware
  -> API endpoint + Pydantic schema
  -> service
  -> repository -> PostgreSQL
  -> integrations -> Redis / llama.cpp / SMTP
```

Основные каталоги:

```text
app/
  api/            HTTP-маршруты
  core/           конфигурация, ошибки, logging, security
  db/             SQLAlchemy и подключения
  integrations/   AI- и email-провайдеры
  middleware/     request ID, body limit, request logging
  repositories/   запросы к БД
  schemas/        Pydantic-схемы
  services/       сценарии обработки
  static/         тестовый frontend
alembic/          миграции
tests/            unit и integration/API тесты
```

Поток `POST /api/contact`:

1. Middleware ограничивает размер тела и назначает request ID.
2. Pydantic валидирует и нормализует поля.
3. Redis проверяет rate limit по HMAC-хэшу IP.
4. Обращение сохраняется со статусом `processing`.
5. API возвращает `202 Accepted`.
6. `BackgroundTasks` выполняет AI-анализ и сохраняет результат.
7. Владелец и пользователь получают независимые SMTP-письма.
8. Статусы меняются на `completed` или `partial`; frontend опрашивает API раз в
   две секунды.

Подробная схема находится в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Запуск через Docker Compose

Нужны Docker, Docker Compose и около 1.1 ГБ места для GGUF-модели.

Linux/macOS:

```bash
cp .env.example .env
make model
docker compose up --build
```

PowerShell:

```powershell
Copy-Item .env.example .env
.\scripts\download-model.ps1
docker compose up --build
```

Модель скачивается один раз в исключённый из Git каталог `models/`.
Compose поднимает API, PostgreSQL, Redis, llama.cpp, Mailpit и отдельный
контейнер миграций.

После запуска:

- frontend: <http://localhost:8000>;
- Swagger UI: <http://localhost:8000/docs>;
- ReDoc: <http://localhost:8000/redoc>;
- Mailpit: <http://localhost:8025>;
- readiness: <http://localhost:8000/api/health/ready>.

Для просмотра обращений на frontend используйте `admin` / `admin`. Эти
значения предназначены только для локального запуска.

Остановка:

```bash
docker compose down
```

PostgreSQL и Redis используют именованные volumes. Удалить локальные данные
можно командой `docker compose down -v`.

## Локальный запуск без Docker

Нужны Python 3.12, uv, PostgreSQL и Redis:

```bash
cp .env.example .env
uv sync --frozen --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

В `.env` укажите доступные `DATABASE_URL` и `REDIS_URL`. AI и email можно
оставить выключенными: приложение использует fallback и disabled email
provider. Для полноценной проверки удобнее Docker Compose.

## Переменные окружения

Настройки читаются централизованно через `pydantic-settings`.

| Переменная | Назначение | Локальное значение |
|---|---|---|
| `APP_ENV` | `development`, `test`, `production` | `development` |
| `APP_HOST`, `APP_PORT` | адрес и порт API | `0.0.0.0`, `8000` |
| `APP_LOG_LEVEL`, `APP_LOG_FILE` | уровень и файл логов | `INFO`, `logs/app.log` |
| `REQUEST_BODY_MAX_BYTES` | максимальный размер запроса | `16384` |
| `IP_HASH_SALT` | HMAC-соль для IP | заменить в production |
| `TRUST_PROXY_HEADERS` | доверять proxy-заголовкам | `false` |
| `CORS_ALLOWED_ORIGINS` | разрешённые origins | localhost |
| `DATABASE_URL` | PostgreSQL DSN | локальная БД |
| `REDIS_URL` | Redis DSN | `redis://localhost:6379/0` |
| `RATE_LIMIT_REQUESTS` | число запросов | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | окно rate limit | `900` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | доступ к `/api/contacts` | `admin`, `admin` |
| `AI_ENABLED` | включить AI provider | `false` вне Compose |
| `AI_API_KEY` | ключ OpenAI-compatible provider | пусто вне Compose |
| `AI_BASE_URL`, `AI_MODEL` | endpoint и модель | задаются Compose |
| `AI_TIMEOUT_SECONDS` | timeout AI | `10` |
| `EMAIL_ENABLED` | включить email | `false` вне Compose |
| `SMTP_HOST`, `SMTP_PORT` | SMTP endpoint | пусто, `587` |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP credentials | пусто |
| `SMTP_FROM_EMAIL`, `SMTP_OWNER_EMAIL` | отправитель и получатель | пусто |
| `SMTP_USE_TLS` | STARTTLS | `true` |
| `METRICS_API_KEY` | доступ к статистике | endpoint скрыт без ключа |

`.env` не коммитится. При `APP_ENV=production` приложение запрещает dev DSN,
короткую HMAC-соль и стандартные `admin` / `admin`.

## Миграции

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade -1
```

Новая миграция:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

## API

| Метод | Маршрут | Назначение | Доступ |
|---|---|---|---|
| `POST` | `/api/contact` | принять обращение | публичный |
| `GET` | `/api/contacts` | последние 100 обращений | HTTP Basic |
| `GET` | `/api/health` | состояние зависимостей | публичный |
| `GET` | `/api/health/live` | liveness | публичный |
| `GET` | `/api/health/ready` | readiness | публичный |
| `GET` | `/api/metrics` | статистика обращений | `X-API-Key` |

OpenAPI доступен по `/docs`, `/redoc` и `/openapi.json`.

### Создание обращения

```bash
curl -i -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Анна Иванова",
    "phone": "+7 (912) 345-67-89",
    "email": "anna@example.com",
    "comment": "Нужно разработать backend для интернет-магазина."
  }'
```

Ответ:

```http
HTTP/1.1 202 Accepted
```

```json
{
  "request_id": "f5a881fd-4bee-4c83-91b9-f204619db856",
  "status": "accepted",
  "message": "Contact request accepted for processing"
}
```

### Валидация

- `name`: после trim от 2 до 100 символов;
- `phone`: от 7 до 15 цифр, допустим один ведущий `+`;
- `email`: валидный адрес, сохраняется в нижнем регистре;
- `comment`: после trim от 10 до 3000 символов;
- неизвестные поля запрещены;
- тело запроса ограничено 16 КБ по умолчанию.

### Ошибки

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

Используются статусы `400`, `401`, `404`, `413`, `422`, `429`, `500` и `503`.
Ответ `429` содержит `Retry-After`; внутренние исключения клиенту не
возвращаются.

### Административные обращения

```bash
curl -u admin:admin http://localhost:8000/api/contacts
```

HTTP Basic добавлен только к списку обращений, потому что он содержит
персональные данные. В production стандартные credentials не принимаются.

### Health и статистика

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/live
curl http://localhost:8000/api/health/ready
curl -H "X-API-Key: your-local-key" http://localhost:8000/api/metrics
```

Без `METRICS_API_KEY` endpoint статистики отвечает `404`.

## AI-интеграция

Приложение использует OpenAI-compatible `POST /chat/completions` через
`httpx`. В Docker запросы идут в локальный llama.cpp с
`Qwen2.5-1.5B-Instruct Q4_K_M`; внешний аккаунт и API-ключ не нужны.

AI возвращает:

- category: `job_offer`, `project_request`, `collaboration`, `support`,
  `feedback`, `spam` или `other`;
- sentiment: `positive`, `neutral` или `negative`;
- urgency: `low`, `medium` или `high`;
- summary длиной до 200 символов.

Ответ ограничен JSON Schema и дополнительно проверяется Pydantic. Комментарий
передаётся как недоверенные данные отдельно от системной инструкции. Полный
runtime-промпт находится в
[app/integrations/ai/openai_compatible.py](app/integrations/ai/openai_compatible.py).

При timeout, сетевой ошибке, `429`, `5xx` или невалидном JSON применяется:

```json
{
  "category": "other",
  "sentiment": "neutral",
  "urgency": "low",
  "summary": null,
  "provider_status": "unavailable"
}
```

Обращение остаётся в БД, после чего стандартные письма всё равно отправляются.

## Email

SMTP-провайдер отправляет:

- владельцу: request ID, контакты, комментарий, AI-результат и дату;
- пользователю: подтверждение получения без обещания срока ответа.

Письма отправляются независимо. Результат каждого вызова сохраняется как
`pending`, `sent`, `failed` или `skipped`. Заголовки защищены от CR/LF
injection. В Docker письма перехватывает Mailpit и не отправляет их во внешний
интернет.

## Хранение данных, логов и статистики

- PostgreSQL хранит обращения, AI-результаты и статусы писем.
- Redis хранит rate-limit counters с TTL; исходный IP не сохраняется.
- `/api/metrics` считает агрегаты по таблице обращений: total/today,
  категории, sentiment, ошибки email и число AI fallback.
- Логи пишутся в stdout и `APP_LOG_FILE` через `RotatingFileHandler`.
- В логах есть request ID, метод, путь, HTTP-статус, длительность и HMAC IP.
- Тела запросов, комментарии, телефоны, email, пароли и ключи не логируются.

## Тесты и качество

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app tests
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

Тесты используют fakes, dependency overrides и SQLite, поэтому не обращаются к
реальному AI или SMTP. Покрыты validation, rate limit, AI fallback и JSON,
email, database failure, request ID, health, metrics authentication, CORS и
admin authentication.

GitHub Actions запускает Ruff, mypy, pytest и сборку Docker image. Makefile
содержит команды `install`, `run`, `test`, `lint`, `format`, `typecheck`,
`migrate`, `model`, `docker-up` и `docker-down`.

## Postman

Импортируйте:

- `postman/AI Contact API.postman_collection.json`;
- `postman/Local.postman_environment.json`.

Коллекция содержит успешное и невалидное обращение, health, readiness и
metrics.

## Что сделано с помощью AI

Codex использовался для:

- извлечения требований из PDF и составления плана;
- подготовки каркаса приложения, миграций, тестов и документации;
- реализации отдельных обработчиков, интеграций и Docker-конфигурации;
- поиска несоответствий между кодом, OpenAPI, README и исходным заданием.

Примеры рабочих промптов:

- «Раздели требования PDF на обязательные и дополнительные и составь
  трассировку».
- «Реализуй `POST /api/contact` с нормализацией, rate limit, сохранением и
  безопасными ошибками».
- «Добавь OpenAI-compatible классификатор со строгим JSON и fallback».
- «Добавь два SMTP-письма, сохрани независимые статусы и не логируй PII».
- «Сверь публичные маршруты, Postman и README с исходным PDF».

Вручную были проверены и исправлены:

- публичный маршрут `/api/contact`;
- границы DB-транзакций и отдельная сессия фоновой задачи;
- fallback при недоступности AI;
- защита email headers и отсутствие PII в логах;
- CORS, OpenAPI, Postman и Docker health checks;
- качество локальной модели: тестовые 135M и 0.5B заменены на Qwen2.5 1.5B;
- системный prompt после проверки на русскоязычных обращениях;
- удаление неиспользуемых конфигураций облачного деплоя.

Полный журнал приведён в [docs/AI_USAGE.md](docs/AI_USAGE.md). Утверждения о
проверках основаны на выполненных командах, а не на сгенерированных оценках.

## Безопасность и ограничения

- CORS работает по allowlist.
- Размеры запроса и строк ограничены.
- IP перед хранением хэшируется с серверной солью.
- Metrics key и HTTP Basic credentials сравниваются constant-time.
- AI и SMTP имеют timeout; AI повторяет только временные ошибки.
- Пользовательские HTML и Markdown не исполняются.
- Секреты и `.env` исключены из Git.

`BackgroundTasks` не является надёжной очередью: при остановке процесса после
ответа задача может потеряться. Для production понадобятся durable queue,
retry policy и transactional outbox. Для тестового задания выбран простой
вариант без отдельного broker.

Подробнее: [docs/SECURITY.md](docs/SECURITY.md) и
[docs/DECISIONS.md](docs/DECISIONS.md).

## Деплой

Публичный деплой не выполнялся. Исходное задание разрешает вместо ссылки
предоставить инструкцию локального запуска; она приведена в разделе
«Запуск через Docker Compose».

Для внешнего размещения необходимо:

1. заменить `admin` / `admin`, HMAC-соль и все credentials;
2. использовать управляемые PostgreSQL, Redis, SMTP и secret storage;
3. применить `alembic upgrade head`;
4. направить health check на `/api/health/live`;
5. писать логи во внешнюю систему, если файловая система эфемерна;
6. решить, где будет запущена модель или какой OpenAI-compatible provider будет
   использован.

## Дополнительная документация

- [docs/REQUIREMENTS_ANALYSIS.md](docs/REQUIREMENTS_ANALYSIS.md) — трассировка;
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — этапы работы;
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — компоненты и поток;
- [docs/AI_USAGE.md](docs/AI_USAGE.md) — использование AI;
- [docs/SECURITY.md](docs/SECURITY.md) — меры безопасности;
- [docs/DECISIONS.md](docs/DECISIONS.md) — принятые решения.

# Архитектура

## Стиль

AI Contact API — асинхронный модульный монолит. Для объёма тестового задания он
проще в сопровождении микросервисов, но оставляет внешние интеграции заменяемыми.

## Слои

- `app/api/v1` — HTTP-маршруты и dependency injection. Имя внутреннего пакета
  не влияет на публичный контракт: маршруты публикуются под `/api`.
- `app/schemas` — входные, публичные и AI Pydantic-схемы.
- `app/services` — orchestration и бизнес-правила.
- `app/repositories` — SQLAlchemy-запросы без HTTP-логики.
- `app/db` — модели, engine/session и миграции.
- `app/integrations` — AI и email providers за Protocol-контрактами.
- `app/middleware`, `app/core` — request context, лимиты, ошибки, конфигурация,
  безопасность и логирование.

## Поток contact

```text
client
  -> middleware (CORS, request id, body limit)
  -> schema validation
  -> Redis rate limit
  -> repository: INSERT + COMMIT
  -> HTTP 202 + BackgroundTasks
      -> AI provider -> validated result/fallback -> COMMIT
      -> owner email and user email
      -> repository: delivery/processing statuses
```

Обращение коммитится до ответа и внешнего AI-вызова, поэтому сбой AI не теряет данные.
AI и email выполняются после ответа и используют новую DB-сессию, не request-scoped
сессию. Две отправки независимы; итог может быть `completed` или `partial`.

## Зависимости и деградация

- PostgreSQL — источник истины и критическая readiness-зависимость.
- Redis — rate limiter; при сбое fail-open с warning.
- AI — необязателен; строгий fallback сохраняет контракт.
- SMTP — необязателен; disabled provider поддерживает локальную разработку.

## Данные

В `contact_requests` хранятся нормализованные контакты, комментарий,
AI-классификация, processing/email statuses, безопасный IP hash, user agent и
timestamps. Схему развивает Alembic. Raw IP, ключи и пароли не сохраняются.

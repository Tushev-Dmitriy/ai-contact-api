# Деплой

Рекомендуемый бесплатный стек для демонстрационного deployment:

- Koyeb Free — Docker web service;
- Neon Free — PostgreSQL;
- Upstash Free — Redis;
- Groq Free — OpenAI-compatible классификация;
- Brevo Free — SMTP через STARTTLS на порту 587.

Шаблон production-переменных находится в `deploy/koyeb.env.example`.

## Koyeb

1. Создайте бесплатные Neon и Upstash databases в одном близком регионе.
2. Создайте Groq API key.
3. В Brevo подтвердите sender и создайте SMTP key.
4. В Koyeb подключите GitHub-репозиторий `Tushev-Dmitriy/ai-contact-api`.
5. Выберите ветку `main`, builder `Dockerfile`, instance `Free`.
6. Опубликуйте порт `8000` как HTTP с route `/`.
7. Health check: порт `8000`, HTTP path `/api/health/live`.
8. Перенесите значения из `deploy/koyeb.env.example` в Environment variables.
   Все значения из секретной секции создайте как Koyeb Secrets.
9. Оставьте одну replica и включите автоматический deploy из `main`.

Container entry point выполняет `alembic upgrade head`, после чего запускает
Uvicorn. Повторное применение актуальной миграции безопасно и позволяет
восстанавливать free instance после сна без ручной команды.

Neon connection string нужно привести к драйверу
`postgresql+asyncpg://`. Если Neon добавил `channel_binding=require`, удалите
только этот параметр; TLS должен остаться включённым через `ssl=require`.

После deployment проверьте:

```text
GET  https://<service>.koyeb.app/api/health/live
GET  https://<service>.koyeb.app/api/health/ready
POST https://<service>.koyeb.app/api/contact
GET  https://<service>.koyeb.app/docs
```

## Ресурсы

1. Managed PostgreSQL.
2. Managed Redis.
3. Web service из `Dockerfile`, порт `8000`.
4. Миграции выполняются production entry point перед Uvicorn.

## Обязательная конфигурация

Установите `APP_ENV=production`, production `DATABASE_URL` с драйвером
`postgresql+asyncpg`, `REDIS_URL`, случайный `IP_HASH_SALT` длиной не менее 32
символов и точный `CORS_ALLOWED_ORIGINS`.

Для реального AI задайте `AI_ENABLED=true`, `AI_API_KEY`, `AI_MODEL` и при
необходимости `AI_BASE_URL`. Для email задайте `EMAIL_ENABLED=true`,
`SMTP_HOST`, `SMTP_FROM_EMAIL`, `SMTP_OWNER_EMAIL` и согласованные credentials.
Для статистики задайте сильный `METRICS_API_KEY`.

Не помещайте секреты в Docker image, репозиторий или build logs.

## Команды и проверки

```bash
docker build -t ai-contact-api .
docker run --rm --env-file .env -p 8000:8000 ai-contact-api
```

Health check: `GET /api/health/live`. После запуска отдельно проверьте
`GET /api/health/ready`, `POST /api/contact`, CORS нужного frontend origin и
SMTP/AI в контролируемом окружении.

## Production checklist

- миграция завершилась до переключения трафика;
- HTTPS завершается на доверенном proxy;
- `TRUST_PROXY_HEADERS=true` включён только за таким proxy;
- БД/Redis недоступны из публичной сети;
- настроены backups, alerts и централизованные stdout logs;
- файловый `APP_LOG_FILE` не считается долговременным на ephemeral disk;
- секреты ротируются, PII имеет retention policy;
- несколько replicas используют общий Redis;
- rollback приложения совместим с применённой схемой БД.

Для production email рекомендуется вынести BackgroundTasks в durable queue.
Публичный Swagger после разрешённого деплоя будет доступен по `/docs`.

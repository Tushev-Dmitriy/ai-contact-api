# Деплой

Проект готов к container-based платформе (Render, Railway или аналог), но
публичный deploy не выполнялся.

## Ресурсы

1. Managed PostgreSQL.
2. Managed Redis.
3. Web service из `Dockerfile`, порт из переменной платформы или `8000`.
4. Pre-deploy/release command: `alembic upgrade head`.

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

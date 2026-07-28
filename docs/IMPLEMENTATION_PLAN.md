# План и этапы реализации

Документ фиксирует фактически выполненные этапы. Архитектурные обоснования
находятся в `docs/DECISIONS.md`, трассировка требований — в
`docs/REQUIREMENTS_ANALYSIS.md`.

## Архитектура

Приложение — один FastAPI-сервис со слоями:

```text
middleware -> API/schemas -> services -> repositories/integrations
                                      -> PostgreSQL / Redis / AI / SMTP
```

Интерфейсы `Protocol` используются только для заменяемых AI- и
email-провайдеров. Общий repository base class, DI-контейнер, broker и
микросервисы не добавлялись.

## Выполненные этапы

| Этап | Результат | Проверка |
|---|---|---|
| Анализ | Разобраны PDF и расширенные требования | трассировка в `REQUIREMENTS_ANALYSIS.md` |
| Каркас | uv-проект, FastAPI factory, Ruff, mypy, pytest | локальные quality-команды |
| Конфигурация | pydantic-settings, request ID, body limit, safe logging | unit/API tests |
| Данные | async SQLAlchemy, PostgreSQL, Alembic | migration и repository tests |
| Contact API | `POST /api/contact`, validation, `202` | integration tests |
| Rate limit | Redis counter + TTL, hashed IP, fail-open | unit/API tests |
| AI | OpenAI-compatible adapter, JSON Schema, Pydantic, fallback | unit tests и local smoke test |
| Email | SMTP/disabled providers, два письма, независимые статусы | unit/API tests и Mailpit |
| Ошибки | единый error contract и global handlers | integration tests |
| Наблюдаемость | health, readiness, metrics, rotating log | integration tests |
| Контейнеры | non-root API image, Compose, migrations, health checks | Docker build и smoke test |
| Поставка | CI, Postman, README и дополнительная документация | JSON/CI/config checks |
| Demo UI | форма, HTTP Basic admin view, polling статусов | browser smoke test |

## Поток обработки

1. Запрос проходит body limit, request context и Pydantic validation.
2. Redis проверяет rate limit.
3. Обращение сохраняется в PostgreSQL как `processing`.
4. API возвращает `202 Accepted`.
5. `BackgroundTasks` в отдельной DB-сессии запускает AI и сохраняет результат.
6. Два SMTP-письма отправляются независимо.
7. Итоговый статус становится `completed` или `partial`.

## Финальные проверки

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app tests
uv run pytest
docker compose config --quiet
docker build -t ai-contact-api:check .
```

Реальные AI и SMTP не вызываются автоматическими тестами. Они проверяются
отдельным локальным smoke-сценарием через llama.cpp и Mailpit.

## Ограничение выбранного подхода

`BackgroundTasks` достаточно для тестового задания, но задача может потеряться
при остановке процесса после HTTP-ответа. Production-вариант потребует
durable queue или transactional outbox с worker.

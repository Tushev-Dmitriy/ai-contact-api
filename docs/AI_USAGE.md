# Использование AI

## Runtime AI

Приложение использует заменяемый `AIProvider`. OpenAI-compatible реализация
передаёт комментарий как недоверенные данные, требует только JSON и проверяет
ответ строгой Pydantic-схемой. Timeout и ограниченные retries применяются к
временным сбоям; прочие `4xx` не повторяются.

Допустимые категории: `job_offer`, `project_request`, `collaboration`,
`support`, `feedback`, `spam`, `other`. Допустимы sentiment
`positive|neutral|negative`, urgency `low|medium|high`, summary до 200 символов.

При отключённом или недоступном provider результат детерминирован:

```json
{
  "category": "other",
  "sentiment": "neutral",
  "urgency": "low",
  "summary": null,
  "provider_status": "unavailable"
}
```

## AI при разработке

Codex использовался как инженерный помощник:

- извлечение и декомпозиция требований `Тест.pdf`;
- проектирование модульного монолита и контрактов;
- реализация кода, миграций, тестов, Docker, CI, Postman и документации;
- запуск Ruff, mypy, pytest, Compose/Docker smoke checks;
- сверка публичных маршрутов и OpenAPI с исходным PDF.

Человек сохраняет ответственность за решения, секреты, внешний деплой и
финальный review.

## Что проверено и исправлено вручную

- маршрут изменён с промежуточного `/api/v1/contact` на точный `/api/contact`;
- проверены порядок DB commit, AI fallback и фоновая email-сессия;
- устранены утечки внутренних исключений и обеспечен request ID в ошибках;
- проверены отсутствие PII/ключей в логах и защита SMTP headers;
- исправлены пустые optional env из Docker Compose;
- настроены корректные test dependency overrides и транзакционная изоляция;
- проверены OpenAPI, CORS, Docker health path и валидность Postman JSON;
- устранены замечания `git diff --check` по концам файлов;
- восстановлена работа MemPalace после конфликта локального writer-процесса.

Реальные AI и SMTP в автоматических тестах намеренно не вызываются.

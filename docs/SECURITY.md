# Безопасность

## Защищаемые данные

Сервис обрабатывает имя, телефон, email, комментарий и технические метаданные.
Секретами являются AI/SMTP credentials, metrics key и `IP_HASH_SALT`.

## Меры

- тело запроса ограничено по размеру, строки — по длине;
- Pydantic запрещает неизвестные поля и нормализует вход;
- пользовательский HTML/Markdown нигде не исполняется;
- rate limit использует HMAC-SHA256 от IP, raw IP не хранится;
- `X-Forwarded-For` учитывается только при явном `TRUST_PROXY_HEADERS=true`;
- CORS разрешает только origins из allowlist;
- metrics key сравнивается constant-time; endpoint скрыт без настройки;
- AI comment отделён от system prompt, ответ — только валидированный JSON;
- внешние вызовы имеют timeout и ограниченные retries;
- email plain-text, CR/LF в заголовках запрещены;
- ошибки не раскрывают stack trace, DSN или provider response;
- логи не содержат body, полные контакты, ключи и пароли;
- production-конфигурация отклоняет небезопасные dev defaults;
- контейнер запускает приложение не от root.

## Эксплуатационные требования

Production должен использовать HTTPS, managed PostgreSQL/Redis, secret manager,
отдельные минимально привилегированные учётные записи, backup/restore, retention
для PII, ограниченный доступ к логам и своевременное обновление образов.

Fail-open Redis выбран ради доступности формы и должен компенсироваться edge
rate limit/WAF. `BackgroundTasks` не является durable queue; сбой процесса может
прервать email, поэтому production требует очередь, retry policy и DLQ.

О найденной уязвимости не следует писать с персональными данными в публичный
issue; используйте приватный канал владельца репозитория.

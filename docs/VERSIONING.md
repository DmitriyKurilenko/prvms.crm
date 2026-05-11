# Версионирование

## Формат версии
`MAJOR.MINOR.PATCH` (SemVer)

## Текущая версия
0.2.1

## Формат коммитов
```
тип(скоуп): описание

Тело (опционально)
```

### Типы
- `feat` — новая функциональность
- `fix` — исправление бага
- `refactor` — рефакторинг без изменения поведения
- `docs` — документация
- `chore` — сборка, зависимости, конфиг
- `test` — тесты

### Примеры
```
feat(tenants): add Tenant model with django-tenants
fix(auth): refresh token cookie not set with Secure flag
docs: update DECISIONS.md with DEC-005
```

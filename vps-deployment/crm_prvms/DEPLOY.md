# prvms.crm — пробный production deploy

Гайд под **существующий VPS** с уже работающими Traefik + Portainer (развёрнутыми по `for_sample_deploy/bootstrap-server.sh`). Деплой идёт через git pull в `/opt/crm_prvms` + полный compose-стек.

> Если сервер чистый — сначала запусти `for_sample_deploy/bootstrap-server.sh --domain crm.prvms.ru --email <ops>@<...>`. После этого вернись сюда.

## 0. Предварительные требования

- На VPS работают `traefik`, `portainer`, существует docker network `proxy` (проверка: `docker network ls | grep proxy`).
- `crm.prvms.ru` (DNS A-record) указывает на public IP VPS. Проверка: `dig +short crm.prvms.ru` → IP сервера.
- На VPS установлены Docker 24+ и плагин Compose v2 (проверка: `docker compose version`).
- Свободно ~3 ГБ диска под image-build (Python deps + node_modules) и ~5 ГБ под runtime данные.
- Откуда тянуть код: публичный репозиторий или репозиторий с deploy-key. Этот гайд предполагает SSH-доступ к репозиторию.

## 1. Клонирование репозитория

```bash
# На VPS под пользователем с доступом к docker (root или член docker-группы):
sudo mkdir -p /opt/crm_prvms /opt/crm_prvms/logs /opt/crm_prvms/media /opt/backups/crm_prvms
sudo chown -R "$USER":"$USER" /opt/crm_prvms /opt/backups/crm_prvms

cd /opt
git clone <REPO_URL> crm_prvms
cd /opt/crm_prvms
```

Compose-файл, deploy.sh и `.env.prod.example` для production живут внутри репозитория в `vps-deployment/crm_prvms/`. Чтобы не дублировать пути в командах — заведи симлинки в корне (это шаблон, его делаешь один раз):

```bash
cd /opt/crm_prvms
ln -sf vps-deployment/crm_prvms/docker-compose.yml docker-compose.yml
ln -sf vps-deployment/crm_prvms/deploy.sh deploy.sh
ln -sf vps-deployment/crm_prvms/.env.prod.example .env.prod.example
```

## 2. Подготовка `.env.prod`

```bash
cd /opt/crm_prvms
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

Открой `.env.prod` и заполни **все ключи с `CHANGE_ME`**. Сгенерируй секреты:

```bash
# Django SECRET_KEY (>= 64 символов)
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# DB / Redis пароли (>= 24 символа)
python3 -c "import secrets; print(secrets.token_urlsafe(24))"

# FIELD_ENCRYPTION_KEY (для зашифрованных tenant credentials)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Минимум, что обязан заполнить:

| Ключ | Что туда |
| --- | --- |
| `PUBLIC_HOSTNAME` | `crm.prvms.ru` |
| `DB_PASSWORD` | сильный пароль |
| `DATABASE_URL` | `postgres://platform:<DB_PASSWORD>@db:5432/platform_db` |
| `REDIS_PASSWORD` / `REDIS_URL` | `redis://:<REDIS_PASSWORD>@redis:6379/0` |
| `SECRET_KEY` | вывод первой команды выше |
| `FIELD_ENCRYPTION_KEY` | вывод третьей команды |
| `ALLOWED_HOSTS` | `crm.prvms.ru,*.crm.prvms.ru` |
| `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` | `https://crm.prvms.ru` |
| `FRONTEND_APP_URL` | `https://crm.prvms.ru` |
| `EMAIL_HOST*`, `DEFAULT_FROM_EMAIL` | реальный SMTP (для invite-ссылок и подписанных PDF) |
| `HERMES_API_KEY` / `HERMES_WEBHOOK_SECRET` | случайные строки (обмен с контейнером Hermes) |

Если YooKassa / amoCRM / Bitrix24 / Telegram-бот **не нужны для пробного деплоя** — оставь пустыми, они инициализируются ленивыми проверками и feature-gate-ами.

## 3. Проверка конфигурации (dry-run)

```bash
cd /opt/crm_prvms
./deploy.sh --dry-run
```

Скрипт делает:
- проверяет, что `.env.prod` содержит все обязательные ключи без `CHANGE_ME`-плейсхолдеров;
- проверяет, что compose-файл валидный (`docker compose config`);
- проверяет, что docker network `proxy` существует.

Если что-то падает — фикси и запускай снова. **Не переходи дальше пока dry-run не зелёный.**

## 4. Полный деплой

```bash
cd /opt/crm_prvms
./deploy.sh
```

Что произойдёт:
1. `git pull --ff-only` (если хочешь задеплоить уже локально лежащий коммит — `./deploy.sh --no-pull`).
2. `pg_dumpall` старого состояния БД в `/opt/backups/crm_prvms/db_<timestamp>.sql.gz` (если контейнер `db` уже работает).
3. `docker compose build --pull` — пересборка `web` (Python) и `frontend-app` (Node + nginx).
4. `compose run --rm migrate` — `migrate_schemas --shared`, `migrate_schemas --tenant`, `collectstatic`. Прогоняется явно, чтобы любая ошибка миграции была видна **до** перезапуска боевых контейнеров.
5. `docker compose up -d --remove-orphans` — поднимает db, redis, web, celery, celery-beat, frontend-app, hermes.
6. Ожидание health: web и frontend-app должны стать `(healthy)` за ≤ 3 минут.

## 5. Post-deploy smoke checks

```bash
# DNS + TLS
curl -sI https://crm.prvms.ru/ | head -5
curl -sI https://crm.prvms.ru/api/healthz | head -5
curl -s  https://crm.prvms.ru/api/healthz
# expected body: {"status": "ok"}

# Проверка отдачи SPA
curl -s https://crm.prvms.ru/ | grep -c '<div id="app"'   # ожидаем 1

# Проверка Django Admin static
curl -sI https://crm.prvms.ru/static/admin/css/base.css | head -3   # 200 OK

# Контейнеры
docker compose -f /opt/crm_prvms/docker-compose.yml --env-file /opt/crm_prvms/.env.prod ps
```

## 6. Создание первого администратора

```bash
cd /opt/crm_prvms
docker compose --env-file .env.prod run --rm web python manage.py create_test_users
# или собственного:
docker compose --env-file .env.prod run --rm web python manage.py createsuperuser
```

После этого можно зайти на `https://crm.prvms.ru/admin/` и далее — на `https://crm.prvms.ru/login`.

## 7. Логи и диагностика

```bash
# Все сервисы
docker compose -f /opt/crm_prvms/docker-compose.yml --env-file /opt/crm_prvms/.env.prod logs -f

# Только web (Django + ASGI)
docker compose -f /opt/crm_prvms/docker-compose.yml --env-file /opt/crm_prvms/.env.prod logs -f web

# Traefik: какие правила подцепились
docker logs $(docker ps -q -f name=traefik) 2>&1 | grep -i 'crm-' | tail -20

# Что внутри web-контейнера (проверка settings)
docker compose --env-file .env.prod exec web python manage.py check --deploy
```

## 8. Повторный деплой (после правок)

```bash
cd /opt/crm_prvms
./deploy.sh                # git pull + build + migrate + up
./deploy.sh --no-build     # только перезапуск (если правил только конфиги)
./deploy.sh --no-pull      # без git pull (если правишь напрямую на сервере)
```

## 9. Откат

```bash
cd /opt/crm_prvms

# 1. Восстановить БД из последнего бэкапа (он создаётся автоматически перед каждым деплоем)
ls -lah /opt/backups/crm_prvms/
gunzip -c /opt/backups/crm_prvms/db_<timestamp>.sql.gz | \
  docker compose --env-file .env.prod exec -T db psql -U platform -d postgres

# 2. Откатить код
git log --oneline -10
git checkout <previous_sha>

# 3. Пересобрать без pull
./deploy.sh --no-pull
```

## 10. Что НЕ включено в этот стек

- **FreeSWITCH / SIP** ([KNOWN_ISSUES #2](../../docs/KNOWN_ISSUES.md)). Включается через отдельный compose-файл (`docker-compose.telephony.yml`), требует SIP-портов 5060/5080 наружу.
- **CI** ([KNOWN_ISSUES #11](../../docs/KNOWN_ISSUES.md)). Сейчас деплой ручной по этому гайду. CI-workflow с `manage.py check`/тестами/typecheck — следующий шаг.
- **Внешние CRM в production** ([KNOWN_ISSUES #1](../../docs/KNOWN_ISSUES.md)) — требуют валидации на боевых аккаунтах amoCRM/Bitrix24.

## Структурная карта

```
/opt/
├── traefik/                           # установлен bootstrap-server.sh, не трогаем
├── portainer/                         # установлен bootstrap-server.sh, не трогаем
├── backups/crm_prvms/                 # автоматические pg_dumpall перед каждым деплоем
└── crm_prvms/                         # git checkout репозитория prvms.crm
    ├── docker-compose.yml             # symlink → vps-deployment/crm_prvms/docker-compose.yml
    ├── deploy.sh                      # symlink → vps-deployment/crm_prvms/deploy.sh
    ├── .env.prod                      # секреты (chmod 600, НЕ в git)
    ├── .env.prod.example              # symlink → vps-deployment/crm_prvms/.env.prod.example
    ├── Dockerfile                     # backend (Python 3.13 + WeasyPrint deps)
    ├── Dockerfile.frontend            # multi-stage Vite build → nginx:alpine
    ├── apps/, config/, frontend/, ... # код проекта
    ├── logs/                          # bind-mount /app/logs (web + celery)
    └── media/                         # bind-mount /app/media (logos, signed PDFs)
```

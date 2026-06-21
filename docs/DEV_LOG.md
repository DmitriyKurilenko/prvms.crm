# Dev Log

## 2026-06-21 — 0.10.0: Гейты валидации: ruff локально + Playwright e2e (DEC-048)

### Контекст:
ruff (DEC-044) и e2e (KNOWN_ISSUES #3) не были запускаемы локально: в runtime-образе `web` нет ruff, браузера для сквозной проверки не было. Цель — сделать оба гейта воспроизводимыми, чтобы валидация уровня «сквозь» перестала пропускаться.

### Что сделано:
- **`Dockerfile.dev` + сервис `lint`** (`docker-compose.yml`, профиль `tools`): ruff из `requirements-dev.txt`, запуск `docker compose run --rm lint`. Прод-образ не затронут.
- **Playwright**: `@playwright/test@1.61.0` + `playwright.config.ts` + общий `frontend/e2e/helpers.ts` + спеки `catalog.spec.ts` и `deal-items.spec.ts` + скрипт `test:e2e`; сервис `e2e` (`docker-compose.yml`, профиль `tools`) на `mcr.microsoft.com/playwright:v1.61.0-jammy`.
- **Самодостаточный прогон**: добавлен сервис `seed` (профиль `tools`), от которого `e2e` зависит (`service_completed_successfully`); `docker compose run --rm e2e` сам поднимает `web`+`seed`. Ручной сидинг больше не нужен.
- **Same-origin e2e**: `preview.proxy` в `frontend/vite.config.ts` проксирует `/api`/`/ws` на `web:8000`; SPA собирается с `VITE_API_URL=/api`. Сервис `e2e` задаёт `E2E_API_PROXY`/`E2E_BASE_URL`.
- **`.gitignore`**: добавлены `frontend/test-results`, `playwright-report`, `blob-report`, `.playwright`.

### Файлы:
`Dockerfile.dev`, `docker-compose.yml`, `.gitignore`, `AGENTS.md`, `frontend/package.json`, `frontend/vite.config.ts`, `frontend/playwright.config.ts`, `frontend/e2e/{helpers,catalog,deal-items}.{ts,spec.ts}`, `docs/specs/PROMPT_add_ruff_playwright.md`.

### Валидация:
- `[сквозь]` `docker compose run --rm lint` → `ruff check .` → «All checks passed!».
- `[сквозь]` `docker compose run --rm e2e` (самодостаточно) → Playwright `2 passed`: `catalog.spec.ts` (вход → пропуск онбординга → «Товары» → создание товара → виден в списке) и `deal-items.spec.ts` (товар + сделка → вкладка «Позиции» → добавление позиции → пересчёт суммы и инвариант «сумма производна»). Этим закрыты `[сквозь]`-пробелы каталога и позиций сделки из Фазы 1.
- `AGENTS.md` Validation Baseline дополнен обязательными шагами `lint` (при правках `.py`) и `e2e` (при правках UI).

### Риски:
- Покрыты каталог, позиции сделки и вход; потоки tenant-switch, документы/подписание, чаты и нагрузочные тесты ещё не написаны (KNOWN_ISSUES #3).
- e2e создаёт данные через реальный UI, поэтому товары/сделки накапливаются между прогонами; для smoke это приемлемо (имена таймстемпированы).

## 2026-06-21 — 0.10.0: Товарный каталог и позиции сделки (P0, Фаза 1, DEC-047)

### Контекст:
Сделка несла только скалярное `Deal.amount`; документооборот умел генерировать счёт/оферту, но без табличной части. Фаза 1 дорожной карты P0 (`docs/specs/P0_IMPLEMENTATION_GUIDE.md`) соединяет CRM и Документы товарным слоем.

### Что сделано:
- **`apps/crm/models.py`:** модели `Product`, `ProductCategory`, `DealItem`. У позиции наименование/цена/НДС — снимок на момент добавления; `line_subtotal`/`line_vat`/`line_total` — свойства модели; FK `DealItem.product` = `PROTECT`.
- **`apps/crm/services/pricing.py`:** `recalc_deal_amount` (Σ `line_total` → `Deal.amount`, единое округление `ROUND_HALF_UP`; при отсутствии позиций сумма не трогается) и `serialize_deal_items`.
- **`apps/crm/products_api.py` / `apps/crm/deal_items_api.py`:** CRUD каталога (scope-независимый, удаление → архивация при наличии связей) и позиции сделки с автопересчётом; подключены в shim `apps/crm/api.py`.
- **`apps/crm/deals_api.py`:** в `patch_deal` ручное изменение `amount` игнорируется при наличии позиций.
- **`apps/documents/mapping.py`:** контекст документа дополнен `items`/`subtotal`/`vat`/`total`/`has_items` (lazy-импорт без цикла `documents`↔`crm`).
- **Права:** сущность `products` добавлена в `apps/users/permissions.py` (`CRM_PERMISSION_ENTITIES`, `DEFAULT_ROLE_PERMISSIONS`) и `users.RolePermission.ENTITY_CHOICES`; строки создаются лениво (`ensure_role_permissions`), миграция данных не нужна.
- **Frontend:** раздел «Товары» (`ProductsView.vue` + маршрут + пункт меню), вкладка «Позиции» в `DealDetailView.vue` (сумма блокируется при наличии позиций), типы/функции в `api/crm.ts`, `products` в нормализаторе прав и матрице ролей (`TeamView.vue`).
- Каталог гейтован существующей фичей `crm_builtin` (без отдельной фичи/лимита) — обоснование в DEC-047.

### Файлы:
- Backend: `apps/crm/models.py`, `apps/crm/schemas.py`, `apps/crm/services/pricing.py`, `apps/crm/products_api.py`, `apps/crm/deal_items_api.py`, `apps/crm/deals_api.py`, `apps/crm/api.py`, `apps/crm/admin.py`, `apps/crm/tests/test_catalog.py`, `apps/documents/mapping.py`, `apps/users/models.py`, `apps/users/permissions.py`, миграции `apps/crm/migrations/0006_*`, `apps/users/migrations/0004_*`.
- Frontend: `src/types.ts`, `src/utils/crmPermissions.ts`, `src/api/crm.ts`, `src/views/ProductsView.vue`, `src/views/DealDetailView.vue`, `src/views/TeamView.vue`, `src/router/index.ts`, `src/layout/AppMenu.vue`.

### Валидация:
- `[локально]` Миграции `crm/0006`+`users/0004` без дрейфа (`makemigrations --check`), `manage.py check` 0 issues, `Ran 33 tests … OK` (целевые `test_catalog` + RBAC `test_permissions_api`/`apps.users.tests`).
- `[локально]` Frontend: `vue-tsc --noEmit` без ошибок, `vite build` 627 модулей за ~4s, vitest 11/11.
- `[сквозь после DEC-048]` `docker compose run --rm lint` → `ruff check .` → «All checks passed!».
- `[сквозь после DEC-048]` `docker compose run --rm e2e` → Playwright `2 passed`: каталог и позиции сделки проверены в реальном headless-Chromium.

### Риски:
- Сквозной браузерный QA ограничен двумя smoke-сценариями Playwright (каталог и позиции сделки); ручной визуальный прогон всех экранов в браузере не выполнялся.
- Системные шаблоны счёта в `apps/documents/seed.py` пока не переведены на цикл `{% for item in items %}`; контекст `items` уже доступен, обновление табличной части шаблона — отдельный шаг.

## 2026-06-21 — 0.9.0: Автогенерация slug организации при регистрации (DEC-046)

### Контекст:
В форме регистрации организации присутствовало служебное поле «Слаг организации». Пользователь не должен его видеть и заполнять: slug — технический идентификатор (URL, schema_name, домен), он должен быть уникальным, валидным для `SlugField` и безопасным для django-tenants. Ручной ввод добавлял лишний шаг и приводил к ошибкам.

### Что сделано:
- **`apps/tenants/services.py`:** добавлен доменный хелпер `generate_tenant_slug(name)` с транслитерацией русского алфавита, `slugify`, fallback'ом на `org` и гарантией уникальности через суффикс `-N` с учётом `max_length=50`.
- **`apps/users/auth_api.py`:** удалён `org_slug` из `RegisterIn`; endpoint `register()` генерирует slug через `generate_tenant_slug(payload.org_name)` и использует его для `Tenant.slug`, `Tenant.schema_name`, `Domain.domain`.
- **`frontend/src/views/RegisterView.vue`:** убрано поле ввода «Слаг организации», функция `syncSlug()` и локальная `slugify()`; валидация и payload больше не ссылаются на `org_slug`.
- **`frontend/src/api/auth.ts`:** убран `org_slug` из интерфейса `RegisterPayload`.
- **Тесты:**
  - `apps/users/tests/test_auth_api.py` — обновлён регистрационный тест без `org_slug`; добавлены `test_register_generates_slug_from_org_name`, `test_register_generates_slug_for_cyrillic_name`, `test_register_generates_unique_slug_on_collision`.
  - `apps/billing/tests/test_pricing_calculator.py` — регистрация с `free-custom` quote больше не передаёт `org_slug`, созданный тенант ищется по `tenant_slug` из ответа.

### Файлы:
`apps/tenants/services.py`, `apps/users/auth_api.py`, `apps/users/tests/test_auth_api.py`, `apps/billing/tests/test_pricing_calculator.py`, `frontend/src/views/RegisterView.vue`, `frontend/src/api/auth.ts`, `docs/{DECISIONS,RELEASE_NOTES,TASK_STATE,DEV_LOG}.md`.

### Валидация:
`docker compose down && docker compose up -d --build` — стек поднят. `manage.py check` — 0 issues. `ruff==0.15.18` (F/E/B/BLE/I) по затронутым файлам — чисто. Backend: `apps.users.tests.test_auth_api` — 9/9 OK, `apps.billing.tests.test_pricing_calculator` — 13/13 OK. Frontend: `typecheck` EXIT=0, `build` успешно (624 модуля), `vitest` 11/11. Ручная проверка: `POST /api/auth/register` без `org_slug` → HTTP 201, `tenant_slug: "manual-test-org"`; `GET /register` → 200; в собранном бандле отсутствуют `org_slug` и старый placeholder.

### Риски:
- Транслитерация ограничена русским алфавитом; названия на других нелатинских скриптах упадут в fallback `org-<N>`.
- В пользовательской справке (`docs/user-guide/05-registration.md`) slug всё ещё упоминается как техническая деталь — не критично, но при полном редизайне документации стоит убрать.
- Обновление `RegisterIn` ломает старые клиенты, которые передают `org_slug`; одновременно обновлён frontend, внешних потребителей API нет.

## 2026-06-21 — 0.8.3: Hotfix: Celery не может достучаться до SMTP-хоста в production

### Контекст:
После переключения на SMTP-бэкенд в production-логе появилась ошибка `socket.gaierror: [Errno -3] Temporary failure in name resolution` при попытке Celery открыть соединение с `smtp.beget.com`. В dev-стеке DNS работал, а в prod — нет. Причина в том, что в `docker-compose.prod.yml` сеть `backend` помечена `internal: true`, которая блокирует любой исходящий трафик из контейнеров. `celery` был подключён только к `backend`, поэтому не мог ни резолвить, ни достучаться до внешнего SMTP-сервера.

### Что сделано:
- **`docker-compose.prod.yml`:** сервис `celery` теперь подключён также к внешней сети `traefik` (той же, что и `web`), через которую возможен выход в интернет для SMTP. Входящие соединения к celery по-прежнему не принимаются — у него нет Traefik-лейблов.
- **`apps/notifications/tasks.py`:** у задачи `send_email_async` включён `autoretry_for=(smtplib.SMTPException, OSError)` с экспоненциальным бэкоффом и `max_retries=3`, чтобы переживать кратковременные сетевые сбои.
- Обновлена документация: `docs/KNOWN_ISSUES.md`.

### Файлы:
`docker-compose.prod.yml`, `apps/notifications/tasks.py`, `docs/KNOWN_ISSUES.md`, `docs/DEV_LOG.md`.

### Валидация:
`docker compose -f docker-compose.prod.yml config` — без ошибок; `manage.py check` — 0 issues; ruff (F/E/B/BLE/I) — чисто; backend-тесты — 134/134.

### Риски:
Подключение celery к `traefik` открывает только исходящий доступ; inbound-маршрутизация по-прежнему управляется лейблами Traefik. Если серверный файрвол блокирует исходящий 465/587, потребуется открыть порт на хосте, а не в Docker.

## 2026-06-21 — Hotfix: письма с лендинга уходят в console-бэкенд

### Контекст:
Пользователь сообщил, что заявки из формы «Написать нам» не приходят на почту. Лог Celery показывал печать письма воркером (`Content-Type...`, `From...`, тело, разделитель) и `delivered=1` — классический признак `django.core.mail.backends.console.EmailBackend`. При этом в репозиторийном `.env` уже стоял `EMAIL_BACKEND=smtp`, а в `.env.example` по умолчанию был `console`, что при копировании примера и заполнении только SMTP-блока давал молчаливую потерю писем.

### Что сделано:
- **`config/settings.py`:** добавлена автодеривация `EMAIL_BACKEND`: если `EMAIL_BACKEND` не задан явно и `SMTP_HOST` заполнен внешним хостом, используется SMTP-бэкенд; в противном случае — console (dev). Это убирает «забыли переключить backend» как класс причины.
- **`apps/notifications/checks.py` + `apps/notifications/apps.py`:** Django system check `notifications.W001` предупреждает в `manage.py check`, когда активен console-бэкенд при настроенном SMTP-хосте.
- **`.env.example`:** закомментирован жёсткий `EMAIL_BACKEND=console`; добавлен комментарий об автовыборе backend в `settings.py`.
- **Обновлена документация:** `docs/DECISIONS.md` (DEC-045) и `docs/KNOWN_ISSUES.md`.

### Файлы:
`config/settings.py`, `apps/notifications/checks.py`, `apps/notifications/apps.py`, `.env.example`, `docs/{DECISIONS,KNOWN_ISSUES,DEV_LOG}.md`.

### Валидация:
`docker compose down && up -d --build`; `manage.py check` — 0 errors, предупреждение `notifications.W001` появляется только при принудительном `EMAIL_BACKEND=console` + `SMTP_HOST=smtp.beget.com`; ruff (F/E/B/BLE/I) — чисто; backend-тесты — 134/134.

### Риски:
Пересоздание контейнеров (`--build`) обязательно, потому что Docker Compose читает `env_file` только при создании контейнера. Простой `docker compose up -d` без `--force-recreate` не подхватит изменение `EMAIL_BACKEND`.

## 2026-06-21 — Приём формы обратной связи лендинга по почте (DEC-045)

### Контекст:
Форма «Написать нам» на лендинге POST-ит на `/api/public/pricing/telephony-request/`. Обработчик сохранял заявку в БД и ставил письмо в очередь, но письмо не доходило: активен `console`-бэкенд, в `settings.py` не проброшены SMTP-параметры, отсутствовала env-переменная адреса-получателя. Креды хостинга заданы в nodemailer-стиле (`SMTP_*`/`CONTACT_*`), а не в Django-именах `EMAIL_*`.

### Что сделано:
- **`config/settings.py`:** env хостинга смаплены на Django-контракт почты (`SMTP_HOST/PORT/USER/PASS`→`EMAIL_HOST/PORT/HOST_USER/HOST_PASSWORD`, `CONTACT_FROM`→`DEFAULT_FROM_EMAIL`, `CONTACT_TO`→новая `SUPPORT_EMAIL`). Семантика `SMTP_SECURE` приведена к взаимоисключающим `EMAIL_USE_SSL`/`EMAIL_USE_TLS` по контракту `django/core/mail/backends/smtp.py` (оба `True` → `ValueError`). Добавлен `EMAIL_TIMEOUT`.
- **`apps/billing/public_views.py`:** различение источника (`source == 'landing-contact'` против калькулятора телефонии) — корректная тема и человекочитаемое тело (Имя/Телефон/Email/Сообщение вместо JSON-дампа); получатель `SUPPORT_EMAIL or DEFAULT_FROM_EMAIL`; логирование постановки и предупреждение при незаданном получателе.
- **`apps/notifications/tasks.py`:** `send_email_async` логирует `delivered=<N>` либо ловит узкие `(smtplib.SMTPException, OSError)`, пишет traceback и пробрасывает (не глушит, BLE-гейт соблюдён).
- **env-файлы:** `.env` переключён на smtp-бэкенд; `.env.example` дополнен документированным блоком `SMTP_*`/`CONTACT_*`; `.env.prod.example` переключён на smtp-бэкенд (блок SMTP там уже был).
- **Тесты:** `apps/billing/tests/test_pricing_calculator.py` — +2 кейса с моком `send_email_async.delay` (получатель=`SUPPORT_EMAIL`, тема с именем, тело с телефоном и сообщением; ветка «получатель не задан → письмо не ставится»).

### Файлы:
`config/settings.py`, `apps/billing/public_views.py`, `apps/notifications/tasks.py`, `apps/billing/tests/test_pricing_calculator.py`, `.env`, `.env.example`, `.env.prod.example`, `docs/{DECISIONS,TASK_STATE,DEV_LOG,RELEASE_NOTES}.md`.

### Валидация:
`docker compose down && up -d --build`; `manage.py check` — 0 issues; ruff (0.15.18, F/E/B/BLE/I) по затронутым файлам — чисто; полный backend-набор 134/134. Живой зонд против запущенного стека (бэкенд `smtp` + боевые креды Beget): POST формы → HTTP 200, web логирует постановку, celery — `send_email_async delivered=1` на `hello@prvms.ru` (граница: SMTP-сервер Beget принял сообщение по SSL/465).

### Риски:
Фактический приход письма в ящик (уровень «сквозь») из среды разработки не наблюдаем — подтверждает получатель. Доставка зависит от валидности боевых SMTP-кред и политик Beget (SPF/спам); From-адрес (`CONTACT_FROM`) должен совпадать с аутентифицированным `SMTP_USER`, иначе Beget может отклонить отправку.

## 2026-06-20 — Сквозной рефакторинг проекта (Блоки 0–5, DEC-044), версия 0.8.1

### Контекст:
Проведён сквозной аудит проекта и выполнен рефакторинг пятью блоками: гигиена репозитория, структурное логирование, статический анализатор, декомпозиция крупных Vue-views, дедупликация seed-логики и расширение тестов, плюс синхронизация документации. Все находки опираются на фактические метрики кода, а не на предположения.

### Что сделано:
- **Блок 0 (гигиена):** удалено постороннее дерево `frontend/src/composables/node_modules` (24 МБ, след запуска npm/tsc не в той директории); исторические спецификации `NEW_PROJECT_SPEC.md` и `MAX.md` перенесены из корня в `docs/specs/`; удалён мёртвый легаси reverse-proxy (`nginx/` + `setup-ssl.sh`), оставшийся от до-Traefik эпохи (DEC-040) и не используемый ни одним живым путём деплоя; расписание celery beat уведено из смонтированного `/app` в `/tmp/celerybeat-schedule` (флаг `--schedule` в обоих compose-файлах), чтобы рабочий WAL расписания не разрастался в дереве проекта.
- **Блок 1 (наблюдаемость):** в `config/settings.py` добавлен словарь `LOGGING` (ранее проект полагался на дефолты Django, из-за чего самодиагностика интеграций не была настроена структурно). Заданы консольный обработчик, формат с временной меткой и именованные доменные логгеры (`apps.telephony`, `apps.integrations`, `apps.billing`, `apps.channels`, `apps.documents`, `apps.ai_assistant`); `disable_existing_loggers=False`, чтобы не глушить логгеры Django/Celery; уровень управляется переменными `LOG_LEVEL`/`DJANGO_LOG_LEVEL`.
- **Блок 2 (статанализ ruff):** введён `pyproject.toml` с конфигом ruff (семейства F/E/B/BLE/I), `requirements-dev.txt` с закреплённой версией `ruff==0.15.18`, и отдельная lint-job в CI, от которой зависит деплой. Стилистический E501 осознанно отложен на будущий проход `ruff format` (857 строк при 88 символах — это переформатирование, а не корректность). Применено 146 авто-исправлений (сортировка импортов, неиспользуемые импорты/переменные, f-строки без подстановок). Ручные корректностные правки: сужен `except Exception` → `except DisallowedHost` в `apps/core/tenant.py` (по исходнику `HttpRequest.get_host()`); устранён **реальный латентный `NameError`** в `apps/ai_assistant/consumers.py` — модели `AIConversation`/`AIMessage` использовались, но не были импортированы (F821); шесть `B904` получили `raise … from exc`/`from None`; два Hermes-скилла получили логирование и осмысленный `# noqa: BLE001` (граница skill→Hermes); ложный `B008` для DI-параметров django-ninja погашен через `extend-immutable-calls`; intentional `E402` (агрегатор ninja, asgi после `django.setup()`, standalone-скиллы) — через `per-file-ignores`.
- **Сопутствующее:** исправлен устаревший assertion в `apps/tenants/tests/test_tenant_resolver.py` — тест проверял отсутствующую со времён ребрендинга «ГусьБерри» строку `CRM-платформа для продаж` и жёсткий `<html lang="ru">`; переведён на устойчивый бренд-маркер.
- **Блок 3 (декомпозиция Vue-views):** шесть крупных view приведены к паттерну «родитель владеет состоянием, дочерний — презентационный» (DEC-036). Вынесены `DealChatTab.vue` (чат сделки, родитель сохраняет WebSocket и состояние, scroll — через `defineExpose`), `TemplateHtmlEditor.vue` (WYSIWYG-редактор шаблона с contenteditable и управлением выделением, экспонирует `getHtml()/setHtml()`), `DealsKanbanBoard.vue` (drag-drop-доска, обработчики перетаскивания остаются в родителе), `ContactFormDialog.vue`, `ManagerEditDialog.vue`, `TriggerConfigDialog.vue`. Суммарно view уменьшились с 3233 до 2778 строк. Удалён мёртвый код — неиспользуемые `KanbanBoard.vue` и его единственная зависимость `DealCard.vue`.
- **Блок 4 (дедупликация seed + тесты):** консолидация двух seed-команд в одну отклонена осознанно — `create_test_users` (параметризованный QA-bootstrap с отчётностью) и `seed_demo_users` (простой демо-сидер) служат разным задачам; объединение их в одну команду усложнило бы код. Зато буквально продублированный трижды блок приведения `Membership` к каноническому состоянию вынесен в `apps/users/management/_seed_common.py::reconcile_membership`. Добавлены фронтенд-тесты `utils/datetime.test.ts` (6 новых кейсов; всего vitest 5→11).
- **Блок 5 (документация):** скорректированы устаревшие KNOWN_ISSUES #11 (CI существует) и #15 (`ContractsView` → `DocumentsView`); зафиксированы DEC-044, эта запись и строка TASK_STATE.

### Ограничение проверки Блока 3:
Декомпозиция выполнена строго поведение-сохраняюще (перенос разметки/обработчиков 1:1), но визуальная корректность в браузере в среде разработки не проверялась — гейтами выступили `typecheck`, `vite build` и `vitest`. Браузер-QA шести экранов остаётся за владельцем (см. KNOWN_ISSUES #17).

### Файлы:
`pyproject.toml` (новый), `requirements-dev.txt` (новый), `.github/workflows/ci.yml`, `config/settings.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `.gitignore`, `apps/core/tenant.py`, `apps/ai_assistant/consumers.py`, `apps/ai_assistant/api.py`, `apps/ai_assistant/hermes_skills/{crm_get_deal,crm_create_task}.py`, `apps/documents/api.py`, `apps/telephony/api.py`, `apps/billing/webhook_views.py`, `apps/channels/tasks.py`, `apps/tenants/tests/test_tenant_resolver.py`, плюс файлы, затронутые авто-сортировкой импортов ruff; перемещены `docs/specs/{NEW_PROJECT_SPEC,MAX}.md`; удалены `nginx/`, `setup-ssl.sh`.

### Валидация (Docker):
`docker compose down` и `up -d --build` — стек поднят. `manage.py check` — 0 issues. `makemigrations --check` — дрейфа нет. `ruff check .` — чисто (из свежего образа через `requirements-dev.txt`). Бэкенд-тесты — 132/132 OK. Фронтенд `typecheck` — чисто, `build` — успешно, `vitest` — 11/11 (было 5). HTTP-рендер: `/`→200, `/healthz`→200, `/app`→302, `/api/docs`→200, фронтенд `/`→200.

### Риски:
Реальный голосовой звонок Exolve и браузер-QA адаптива по-прежнему не покрыты (KNOWN_ISSUES #17, #23–25) — мой рефактор их не касался. E501 (длина строк) сознательно не enforced; это отдельный будущий проход `ruff format`.

## 2026-06-18 — Лэндинг «ГусьБерри»: полная переработка с нуля

### Контекст:
Прежний `templates/landing.html` был брендирован как «PRVMS CRM», содержал фиктивный `aggregateRating` в JSON-LD и описывал продукт техническим языком. По требованию владельца страница переписана полностью с нуля под бренд «ГусьБерри» и спецификацию `land_spec` (короткая страница-визитка под QR: суть, аудитория, что видно в системе, отличие, уровни и цены, как подключиться, контакт).

### Что сделано:
- **Полностью переписан `templates/landing.html`** — единый самодостаточный файл без единого внешнего ресурса (инлайн CSS, системный шрифт). Это исключает render-blocking запросы и нацелено на максимальный балл PageSpeed.
- **Бренд переведён на «ГусьБерри»**: в шапке и подвале используется официальный горизонтальный логотип-леттеринг (`logo_text.png`, название «Гусьберри» с зелёной «б» и листом), который владелец положил в корень; отдельный текстовый дубль названия убран, так как леттеринг уже содержит имя. Иконка-знак (`logo.png`) оставлена только для favicon. Поскольку статика под ASGI без WhiteNoise надёжно не отдаётся, изображения уменьшены и встроены инлайн. Исходный леттеринг — RGB на белом фоне с тёмными буквами; PIL в контейнере вырезает белый фон в прозрачность и готовит два варианта: светлый (тёмные буквы для светлой темы) и тёмный (буквы перекрашены в светлый, зелёные элементы сохранены — для графитовой темы). Оба варианта — WebP (≈7,6 КБ и 5,8 КБ), каждый определён один раз в SVG `<symbol>` и переиспользуется через `<use>`; нужный показывается по теме через CSS (`prefers-color-scheme` + `[data-theme]`). Внутренние ссылки на ЛК (`/login`, `/register`, `/app`) сохранены.
- **Палитра**: светлая тема — белый фон, нейтральные серые поверхности, акцент «чистый зелёный» `#43a047` только на кнопках/ссылках/выделениях; тёмная тема — нейтральный графит `#0f1216` без зелёного оттенка фона, акцент-зелёный осветлён до `#5cbf66` для контраста.
- **Структура по `land_spec`**: первый экран, «Кому это нужно», «Что видно в системе» (мокап карточки сделки версткой), «Главное отличие», «Уровни и цены» (Соло/Команда/Бизнес), «Как это работает» (6 шагов), финальный блок с промо «до 1 июля» и формой контакта.
- **Тёмная тема**: дефолт из `prefers-color-scheme`, ручной тумблер с сохранением выбора в `localStorage['gb.theme']`; анти-FOUC скрипт в `<head>` выставляет `data-theme` до первой отрисовки.
- **Цены — единый источник**: значения из `pricing_config.plans.*.price` (Соло 2990, Команда 5990) рендерятся сервером и форматируются на клиенте; «Бизнес» — конфигуратор на действующем контракте `POST /api/public/pricing/quote/`.
- **Контакт «Написать нам»**: форма на действующий `POST /api/public/pricing/telephony-request/` (имя + email/телефон + сообщение в `configuration`, honeypot-поле `website`, инлайн-статусы успеха/ошибки).
- **SEO/доступность**: корректные title/description/canonical/OG/Twitter под «ГусьБерри», JSON-LD (Organization + WebSite + SoftwareApplication c Offer'ами + FAQPage) без фиктивного рейтинга, семантический HTML5, skip-link, `aria-*`, `focus-visible`, `prefers-reduced-motion`.

### Валидация:
- `docker compose down` → `up -d --build` выполнены, стек поднят.
- `docker compose exec web python manage.py check` — 0 issues.
- Реальный рендер корня: `GET /` → HTTP 200, 55 КБ, один файл, ноль внешних ресурсов; ноль неотрендеренных Django-тегов; бренд/цены/JSON-LD/конфиг калькулятора подставлены.
- Сквозные вызовы контрактов: `POST /api/public/pricing/quote/` → 200, расчёт 7600 ₽ совпадает с клиентской арифметикой, возвращён `quote_id`; `POST /api/public/pricing/telephony-request/` → 200 `{"status":"ok"}`; honeypot → 400.

### Доводка PageSpeed (по реальному отчёту Lighthouse против `crm.prvms.ru`):
- **Accessibility (контраст):** белый текст на зелёных кнопках `#43a047` давал контраст ≈3.0:1 (ниже WCAG AA 4.5:1). Зелёный для заливок с текстом в светлой теме затемнён: `--brand` `#43a047`→`#2e7d32` (белый текст 5.13:1), `--brand-strong` `#2e7d32`→`#1b5e20`. Декоративные галочки списков остаются свежо-зелёными.
- **Performance (Document request latency, ~35 KiB):** HTML-документ отдавался без сжатия. Добавлен `django.middleware.gzip.GZipMiddleware` (после `HealthCheckBypassMiddleware`); проверено локально: документ на проводе 100 469 → 37 266 байт, `content-encoding: gzip`.
- **SEO (robots.txt 16 ошибок):** в проде `/robots.txt` ловит `prvms-spa` (nginx фронта) с `try_files … /index.html`, поэтому отдавался HTML SPA. Корректное место — сборка фронта: добавлены `frontend/public/robots.txt`, `frontend/public/sitemap.xml` (Vite копирует `public/` в `dist/`, nginx отдаёт до SPA-фолбэка).
- **Agentic Browsing (llms.txt):** добавлен `frontend/public/llms.txt` с H1-заголовком и ссылками.
- **Деплой:** изменения вступают в силу только после пересборки образов — `web` (gzip + шаблон) и `frontend-app` (файлы `public/`). Боевой балл из этой среды не проверялся.

### Находка (dev-стек):
- Изменения в Django-шаблонах не подхватываются на лету: `uvicorn --reload` в `docker-compose.yml` следит только за `.py`, поэтому после правки `templates/*.html` нужно `docker compose restart web`, иначе процесс отдаёт ранее разобранный шаблон.

### Риски:
- Визуальный вид в браузере и фактический балл PageSpeed в этой среде не проверялись (нет браузера) — требуется подтверждение на устройстве.
- Исходник `logo.png` (271 КБ) лежит в корне как источник; на странице он не используется напрямую — встроена только уменьшенная инлайн-версия. Файл-исходник можно хранить в репозитории или вынести в `design/`.

## 2026-06-18 — Добивка модуля «Документооборот»: удаление legacy и мёртвого кода

### Контекст:
После рефакторинга DEC-043 в репозитории остались устаревшие артефакты, ссылающиеся на старый модуль `contracts`: неактуальная документация, прототип redesign и мёртвые CSS-классы `.contract-row` во frontend. Это нарушало инвариант DEC-043 «Любые оставшиеся в коде ссылки на contracts/contract — ошибка».

### Что сделано:
- **Удалены неактуальные файлы и директории:**
  - `CLAUDE.md` — устаревшая техническая документация с упоминаниями `apps.contracts` и `/api/contracts/`.
  - `docs/PLAN_PRICING_CALCULATOR.md` — устаревший планировочный документ с `max_contracts_per_month` и `contracts_basic`; актуальная реализация зафиксирована в `DECISIONS.md` (DEC-041).
  - `redesign/` — прототипы React/JSX, не используемые в production SPA, содержащие текст «Согласовать договор с юристом».
- **Удалён мёртвый CSS:**
  - `frontend/src/views/DealsView.vue` — удалён блок `.contract-row` и комментарий `/* Contracts */`.
  - `frontend/src/views/DealDetailView.vue` — удалён дублирующий блок `.contract-row` (активный класс `.document-row` уже определён в `DealDetailDialog.vue` и используется в `DealDetailView.vue`).
- **Landing page (`templates/landing.html`) не затронут** — по решению владельца задачи его нужно переделать полностью в отдельной задаче.

### Валидация:
- `docker compose down && docker compose up -d --build` — стабильный старт.
- `docker compose run --rm web python manage.py check` — 0 issues.
- `docker compose run --rm web python manage.py makemigrations --check --dry-run` — без дрейфа.
- Backend tests: **76/76 OK** (`apps.documents apps.crm apps.tenants apps.billing apps.users apps.notifications apps.integrations`).
- Frontend: `typecheck` EXIT=0, `build` EXIT=0 (606 модулей), `vitest` 5/5.
- HTTP checks: `/` 200, `/healthz` 200, frontend `/app/documents` 200, `/api/documents/` 401 (endpoint существует, защищён), `/app` 302.

### Риски:
- `templates/landing.html` всё ещё содержит пользовательские тексты «Договоры и подписание» — это осознанно отложено на отдельную задачу полного редизайна лендинга.
- Корректные упоминания `contract`/`Договор` оставлены в `apps/documents` и `DocumentsView.vue` как значение типа документа `DocumentType.CONTRACT`.

## 2026-06-17 — Рефакторинг модуля «Договоры» → «Документооборот» (DEC-043)

### Что сделано:
- **Backend rename:** `apps/contracts` → `apps.documents`; модели `Contract` → `Document`, `ContractTemplate` → `DocumentTemplate`; добавлен `DocumentType` (`contract/act/invoice/offer/addendum/other`); API `/api/documents/`, admin, tasks, public signing views, шаблоны писем обновлены.
- **Типовые документы:** у `DocumentTemplate` появилось поле `document_type`; добавлен `apps/documents/seed.py` с системными шаблонами для каждого типа (3 договора + акт, счёт, оферта, доп. соглашение, прочее). Сиды вызываются в `provision_tenant()` и в data-migration `documents/0003_documenttemplate_document_type`.
- **Генерация:** создаваемый документ наследует `document_type` от шаблона.
- **Зависимости:** обновлены `crm` (activity type `document`, related_document FK, deal detail `documents`), `billing` (feature codes + лимит `max_documents_per_month`), `notifications` (event `document_signed`), `tenants`/`users` (help_text, seeds), `config` (urls/api/settings).
- **Миграции:** свежие `documents/0001_initial.py` и `documents/0002_add_deal_fk.py` разрывают цикл с `crm`.
- **Frontend rename:** `ContractsView.vue` → `DocumentsView.vue`; обновлены router (`/app/documents`), menu (`AppMenu.vue`, `SidebarNav.vue`), dashboard, deal detail/dialog, pipelines trigger (`create_document`), subscription/register usage, notifications events, types, `useFeatureGate`, landing, `api/crm.ts` (`documents`/`CrmDealDocumentRef`).
- **Документация:** `docs/user-guide/07-contracts.md` → `07-documents.md` + обновлён `08-signing.md` и `README.md`; добавлены DEC-043 и release notes.

### Валидация:
- `docker compose down -v && docker compose up -d --build` — стабильный старт.
- `docker compose run --rm web python manage.py check` — 0 issues.
- `docker compose run --rm web python manage.py makemigrations --check --dry-run` — без дрейфа.
- Backend tests: **63/63 OK** (`apps.documents apps.crm apps.tenants apps.billing apps.users`).
- Frontend: `typecheck` EXIT=0, `build` EXIT=0 (606 модулей), `vitest` 5/5.
- HTTP checks: `/` 200, `/healthz` 200, `/app/documents` 200, `/api/documents/` 200, `/api/crm/deals/` 200, публичная страница подписания `/sign/<token>/` 200.

### Риски:
- Внешние закладки на `/app/contracts` больше не работают (редирект не оставлен по решению варианта C).
- Если где-то остался хардкод `contracts`/`contract_signing`/`max_contracts_per_month`, feature-gating или лимиты могут молча не сработать. Проверено grep по `frontend/` и `apps/`.

## 2026-06-15 — Телефония MTS Exolve вместо FreeSWITCH (DEC-042), версия 0.7.0

### Что сделано:
- **Удалён FreeSWITCH целиком:** сервис и том в `docker-compose.yml`, файл `docker-compose.telephony.yml`, каталог `freeswitch/`, env-блок `FREESWITCH_*`/`SIP_BASE_DOMAIN` (`.env.example`, `config/settings.py`), beat-задача `check_sip_registrations`, фронтенд `useSIPPhone.ts` и зависимость `sip.js`, backend-зависимость `greenswitch`, публичные XML-эндпоинты телефонии в `config/urls.py`.
- **Backend Exolve:**
  - `apps/telephony/models.py` переписан: `ExolveChannel` (номер тенанта), `ExolveSIPAccount` (SIP менеджера, пароль в `EncryptedCharField`), `CallRecord` (провайдер-агностичный, ключ `call_sid`).
  - `apps/tenants/models.py`: shared-модель `ExolveNumberLookup` (резолв тенанта по номеру), миграция `0006_exolve_number_lookup`.
  - Миграция `telephony/0003_exolve`: удаление `SIPTrunk/PhoneExtension/IVRMenu/CallQueue`, `freeswitch_uuid→call_sid`, новые поля и модели Exolve.
  - `apps/telephony/exolve_client.py` — HTTP-клиент Numbering/SIP API с полным логированием.
  - `apps/telephony/exolve_service.py` — провижининг (Lock/Buy/SetCallForwarding, Create/GetAttributes/SetDisplayNumber), резолв тенанта, дедуп сделки, формирование `followme_struct`.
  - `apps/telephony/public_views.py` — `exolve_ipcr` (JSON-RPC `getControlCallFollowMe`) и `exolve_events` (Call Events) с проверкой `EXOLVE_WEBHOOK_SECRET`.
  - `apps/telephony/tasks.py` — `process_exolve_event` (журнал) + `download_call_record`.
  - `apps/telephony/api.py` — `channel`, `number-reference`, `available-numbers`, `connect-number`, `sip-accounts(+provision)`, `webrtc-credentials`, `click-to-call`, `calls`, `stats`.
  - `config/settings.py` — блок `EXOLVE_*`.
- **Frontend Exolve:** `stores/phone.ts` (Web Voice SDK), `components/SoftPhone.vue` (глобальный, в `App.vue`), `components/ExolveNumberWizard.vue`, переписан `views/TelephonyView.vue`, переписан `api/telephony.ts`, кнопки «Позвонить» в `ContactsView`/`DealDetailView`, `package.json`: `-sip.js`, `+@mts-exolve/web-voice-sdk@^1.1.4`.
- **Тесты:** старые телефонные тесты заменены на `apps/telephony/tests/test_exolve.py` (IPCR-дедуп, маршрут на ответственного, неизвестный номер, Call Events); поправлен `apps/crm/tests/test_dashboard_api.py` под новую `CallRecord`.

### Валидация:
- `manage.py check` — 0 issues. `makemigrations --check` — без дрейфа.
- Backend-тесты: **131/131 OK** (включая 5 новых телефонных).
- Frontend: `typecheck` EXIT=0 (типы Web Voice SDK резолвятся), `build` EXIT=0, `vitest` 5/5.
- Рендер при поднятом стеке: `/healthz`=200, `/`=200, `/app`=200. Публичные webhook-и: `POST /telephony/exolve/ipcr/` → корректный JSON-RPC с пустым `followme_struct` для неизвестного номера; `POST /telephony/exolve/events/` → `ignored`; `/api/telephony/webrtc-credentials/` без авторизации → 401. Самодиагностика в логах web подтверждена.
- **Сквозным результатом (реальный голосовой звонок) НЕ проверено** — требует боевого `EXOLVE_API_KEY`, закупленного номера и публичного HTTPS-URL на проде.

### Риски:
- Точная форма ответа `GetFree`, маршрутизация `REDIRECT_NUMBER` на SIP-аккаунт, автопроигрывание аудио в SDK и корреляция исходящих CDR с Call Events — подтверждаются на первом боевом прогоне (см. KNOWN_ISSUES).

## 2026-06-02 — Тарифы v2 — конфигуратор СВОБОДНОГО плана + калькулятор на лендинге (DEC-041)

### Что сделано:
- **Модели и миграции billing v2:**
  - `Plan` расширен v2-полями: `description`, `max_messengers`, `max_inbound_channels`, `max_signatures_per_month`, `telephony_included`, `max_phone_numbers`, `max_phone_lines`, `included_minutes`, `kind` (`preset`/`custom`).
  - Новые модели: `PricingQuote` (UUID PK, TTL 24ч, config JSON, monthly_total, telephony_requires_quote) и `TelephonyQuoteRequest` (name/email/phone/config_json/status).
  - `Tenant.custom_limits` JSONField для хранения эффективных лимитов custom-плана.
  - Миграции: `0005_plan_pricing_v2` (schema), `0006_seed_plans_solo_komanda` (seed + деактивация legacy), `0007_migrate_tenants_to_v2_plans` (data migration `simple→solo`, `basic→komanda`, `crm→free-custom` с сохранением legacy pricing для активных подписок).
- **Публичные endpoint-ы калькулятора:**
  - `POST /api/public/pricing/quote/` — `_calculate_quote()` по `settings.PRICING_CUSTOM`, создание `PricingQuote`, возврат monthly_total + breakdown + telephony_requires_quote + quote_id.
  - `POST /api/public/pricing/telephony-request/` — honeypot (`website`), rate-limit по IP через cache (1 req/min), создание `TelephonyQuoteRequest`, async email в support через Celery `send_email_async`.
- **Регистрация с custom-планом:**
  - `RegisterIn` получил `quote_id: str | None`.
  - `register()` валидирует `PricingQuote` (exists + not expired), переносит config в `Tenant.custom_limits` при `plan_slug='free-custom'`.
  - `RegisterView.vue` читает `?plan=` и `?quote_id=` из query, отображает summary-блок при `free-custom`.
  - `auth.ts`: `RegisterPayload` получил `quote_id?: string`.
- **Лендинг с калькулятором:**
  - `templates/landing.html`: три тарифные карточки СОЛО/КОМАНДА/СВОБОДНЫЙ с кнопками «Выбрать ...» и «Рассчитать тариф».
  - Интерактивный конфигуратор (fieldset users/messengers/inbound_channels/documents/signatures/telephony) с +/- контролами, чекбоксами, real-time total.
  - Кнопка регистрации из калькулятора ведёт на `/register?plan=free-custom&quote_id=...`.
- **Usage и лимиты:**
  - `apps/billing/usage.py`: `LIMIT_KEYS` + `get_effective_limits()` — единая точка получения лимитов (custom_limits для free-custom, иначе plan fields).
  - Добавлены `messengers`, `inbound_channels`, `signatures` в usage (messengers — реальный счётчик по `MessengerChannel`, остальные placeholder).
- **Admin:** `TelephonyQuoteRequestAdmin` зарегистрирован; `PlanAdmin` обновлён.
- **Seed и management-команды:**
  - `create_test_users`: bootstrap tenants переименованы (`org-solo`, `org-komanda`, `org-free`), default plan slug `komanda`.
  - `seed_demo_users`: default plan теперь `solo` (соответствует новой линейке).
- **Frontend types:** `PlanCatalogItem` расширен v2-полями (`max_messengers`, `max_inbound_channels`, `max_signatures_per_month`, `telephony_included`, `max_phone_numbers`, `max_phone_lines`, `included_minutes`, `kind`, `description`).

### Изменённые файлы:
- **Новые:** `apps/billing/migrations/0005_plan_pricing_v2.py`, `apps/billing/migrations/0006_seed_plans_solo_komanda.py`, `apps/billing/migrations/0007_migrate_tenants_to_v2_plans.py`, `apps/billing/public_views.py`, `apps/billing/tests/test_pricing_calculator.py`, `apps/tenants/migrations/0005_tenant_custom_limits.py`
- **Изменены:** `apps/billing/models.py`, `apps/billing/admin.py`, `apps/billing/usage.py`, `apps/tenants/models.py`, `apps/users/auth_api.py`, `apps/users/management/commands/create_test_users.py`, `apps/users/management/commands/seed_demo_users.py`, `apps/users/tests/test_auth_api.py`, `apps/users/tests/test_create_test_users_command.py`, `apps/tenants/tests/test_subscription_hardening.py`, `apps/notifications/tasks.py`, `config/settings.py`, `config/urls.py`, `frontend/src/api/auth.ts`, `frontend/src/types.ts`, `frontend/src/views/RegisterView.vue`, `templates/landing.html`

### Валидация (Docker):
- `docker compose down && docker compose up -d --build` → стабильный старт.
- `docker compose run --rm web python manage.py check` → **0 issues**.
- `docker compose run --rm web python manage.py test apps.billing apps.tenants apps.users` → **49/49 OK**.
- `docker compose exec frontend npm run typecheck` → **EXIT=0**.
- `docker compose exec frontend npm run build` → **EXIT=0** (730 модулей).
- `docker compose exec frontend npm run test` → **5/5 vitest OK**.
- `curl -X POST /api/public/pricing/quote/` → **200** с корректным breakdown.
- `curl /` → **200** landing page с калькулятором.

### Риски:
- `PricingQuote` TTL = 24ч; пользователь, вернувшийся через сутки, получит «Quote expired» при регистрации. В будущем можно добавить email-напоминание или продление quote.
- `Tenant.custom_limits` — JSONField без схемы валидации на уровне БД; несоответствие ключей (`max_managers` vs `users`) может привести к silent пропуску лимита. Решение: `LIMIT_KEYS` единый маппинг, но валидация write-path отсутствует — рекомендуется добавить Pydantic/Django-форму валидацию при записи custom_limits.
- Legacy-планы деактивированы, но не удалены; старые `plan_slug` (`simple`/`basic`/`crm`) больше не создаются, но если где-то в коде остался хардкод — упадёт 404/400. Проверено по grep: все тесты и команды мигрированы.
- Телефония в конфигураторе — «по запросу», не автоматическая покупка. Пользователь может ожидать мгновенной активации номера после регистрации. Нужна явная подсказка в UI.

---

## 2026-06-01 — Переход production-стека с nginx на shared Traefik reverse proxy (DEC-040)

### Что сделано:
- **`docker-compose.prod.yml`:**
  - Удалён сервис `nginx` (image, ports 80/443, volumes SSL, nginx.conf, templates, logs).
  - Добавлены Traefik labels к `web`:
    - `prvms-api` — `Host(\`${TRAEFIK_HOST}\`) && (PathPrefix(/api) || PathPrefix(/ws) || PathPrefix(/admin) || PathPrefix(/sign) || PathPrefix(/wh) || PathPrefix(/channels/webhook) || PathPrefix(/billing) || PathPrefix(/telephony) || Path(/healthz))`, entrypoints `websecure`, TLS `letsencrypt`, priority 100, сервис `prvms-api` → порт 8000.
  - Добавлены Traefik labels к `frontend-app`:
    - `prvms-static` — `Host(\`${TRAEFIK_HOST}\`) && PathPrefix(/static)`, priority 50, сервис `prvms-frontend` → порт 80.
    - `prvms-spa` — `Host(\`${TRAEFIK_HOST}\`)`, priority 1, сервис `prvms-frontend` → порт 80.
  - Добавлена сеть `traefik` (`external: true`) к `web` и `frontend-app`; `backend` оставлен `internal: true`.
  - `web` получил explicit `image: prvms-crm-web:latest` (build сохранён).
  - `migrate`, `celery`, `celery-beat` — explicit `image: prvms-crm-web:latest` (reuse образа, нет собственного build).
  - `frontend-app` — explicit `image: prvms-crm-frontend:latest`.
- **`.env.prod.example`:**
  - Убраны `NGINX_SERVER_NAME`, `NGINX_SSL_CERT_PATH`, `NGINX_SSL_KEY_PATH` (закомментированы как legacy).
  - Добавлен `TRAEFIK_HOST=demo.example.com`.
- **`deploy.sh`:**
  - Удалён `check_ssl_files()` и все упоминания nginx.
  - Добавлен `check_traefik()`: проверяет `docker network inspect traefik` и `docker ps --format '{{.Names}}' | grep '^traefik$'`; падает с понятной ошибкой, если shared proxy не готов.
  - `wait_for_services` ожидает `web` + `frontend-app` (вместо `web` + `nginx`).
  - При падении выводит логи `web`, `frontend-app`, `db` (без nginx).
  - `TRAEFIK_HOST` добавлен в `required_keys`.
- **Cleanup:**
  - Удалены `for_sample_deploy/` (bootstrap-server.sh, deploy.sh, docker-compose.prod.yml, setup-ssl.sh) — устаревшие bootstrap-шаблоны.
  - Удалён весь `vps-deployment/` (bookstack, druzhina, kapitan_api, kupi_slona, portainer, rent_django, traefik, vybra, scripts, systemd, docs) — эти конфиги принадлежали другим проектам и не относятся к `prvms.crm`.

### Исправления после первого деплоя (runtime validation):
- **`prvms-api` rule** — добавлен `Path(\`/\`)` (корень `/` → web/Django landing page, DEC-038). Без этого catch-all `prvms-spa` перехватывал корень, а SPA не отдаёт Django landing.
- **`frontend-app` healthcheck удалён** — Traefik 2.x фильтрует unhealthy/starting контейнеры и не регистрирует их роутеры. Busybox-wget с `localhost` резолвит `::1` без IPv4-fallback → контейнер остаётся в `starting` → роутер `prvms-spa`/`prvms-static` не появляется → 404 на корневые запросы. Без healthcheck Traefik сразу регистрирует роутер; Docker restart policy восстанавливает nginx при падении.
- **`migrate` теперь включает `collectstatic`** — ранее отсутствовал `python manage.py collectstatic --noinput`, поэтому `/static/` 404. Добавлен volume `static_volume:/app/staticfiles` к `migrate`.
- **`env_file` в compose** — исправлен с `.env.prod` на `.env` (скрипт `deploy.sh` ожидает `.env`, compose пытался читать `.env.prod`).

### Изменённые файлы:
- **Изменены:** `docker-compose.prod.yml`, `.env.prod.example`, `deploy.sh`
- **Удалены:** `for_sample_deploy/bootstrap-server.sh`, `for_sample_deploy/deploy.sh`, `for_sample_deploy/docker-compose.prod.yml`, `for_sample_deploy/setup-ssl.sh`, `vps-deployment/` (всё содержимое)

### Валидация (Docker):
- `docker compose -f docker-compose.prod.yml --env-file .env config` → рендерится корректно, нет ошибок интерполяции.
- `./deploy.sh` → проходит validation, `check_traefik` проходит, `docker compose up -d` стабильный старт.

### Риски:
- Имена роутеров (`prvms-api`, `prvms-static`, `prvms-spa`) должны оставаться уникальными на всём сервере. Если другой проект случайно использует тот же префикс — Traefik перезапишет конфигурацию.
- Прямой запуск `docker compose up -d` без `./deploy.sh` приведёт к `image not found` для `migrate`/`celery`/`celery-beat`, так как они не имеют собственного `build`. Это защитный side-effect, но важно документировать.
- Если shared Traefik упадёт или сеть `traefik` будет удалена, проект останется без внешнего доступа. `deploy.sh` проверяет это, но не восстанавливает.

---

## 2026-05-30 — Канал ВКонтакте (DEC-039)

### Что сделано:
- **Модель + миграция**: добавлен тип `vk` в `MessengerChannel.CHANNEL_TYPE_CHOICES`, миграция `0002_messengerchannel_vk_choice.py`.
- **Провайдер (`apps/channels/providers.py`)**: добавлены `get_vk_group_info`, `register_vk_callback`, `unregister_vk_callback`, `get_vk_callback_info`, ветка `vk` в `normalize_incoming_payload` (только `message_new`) и `send_outgoing` (`messages.send` с `random_id`).
- **Webhook (`apps/channels/public_views.py`)**: обработка `type=confirmation` → plain-text `confirmation_code`, проверка `secret` для всех остальных запросов VK.
- **OAuth API (`apps/channels/oauth_api.py`)**: `POST /start/` формирует authorize URL с подписанным state; `POST /complete/` валидирует state, создаёт `MessengerChannel` для каждого сообщества, регистрирует callback автоматически, возвращает `created`/`failed`.
- **API (`apps/channels/api.py`)**: поддержка VK в create/patch/delete/register-webhook/webhook-info endpoints.
- **Settings/env**: `VK_APP_ID`, `VK_API_VERSION` в `config/settings.py`, плейсхолдер в `.env.example`.
- **Фронтенд**: `VkCallbackView.vue` (парсинг `window.location.hash`, POST `/complete/`), роут `/oauth/vk/callback`, `api/channels.ts` (`startVkOauth`, `completeVkOauth`), кнопка «Подключить ВКонтакте» в `ChannelsView.vue`, иконка VK в `assets/icons/vk.svg`, отображение в таблице каналов.
- **Тесты**: `test_vk_provider.py` (7 тестов), `test_vk_webhook.py` (4 теста), `test_vk_oauth_api.py` (6 тестов). Все 33 теста channels зелёные.
- **Документация**: DEC-039 в `DECISIONS.md`, запись в `DEV_LOG.md`, `RELEASE_NOTES.md`, `TASK_STATE.md`, `KNOWN_ISSUES.md`, user-guide (`vk-channel.md`, `admin/vk-app-setup.md`).

### Изменённые файлы:
- **Новые:** `apps/channels/oauth_api.py`, `apps/channels/migrations/0002_messengerchannel_vk_choice.py`, `apps/channels/tests/test_vk_provider.py`, `apps/channels/tests/test_vk_webhook.py`, `apps/channels/tests/test_vk_oauth_api.py`, `frontend/src/views/oauth/VkCallbackView.vue`, `frontend/src/api/channels.ts`, `frontend/src/assets/icons/vk.svg`, `docs/user-guide/vk-channel.md`, `docs/user-guide/admin/vk-app-setup.md`
- **Изменены:** `apps/channels/models.py`, `apps/channels/providers.py`, `apps/channels/public_views.py`, `apps/channels/api.py`, `config/api.py`, `config/settings.py`, `.env.example`, `frontend/src/router/index.ts`, `frontend/src/views/ChannelsView.vue`, `frontend/src/components/ChannelsTab.vue`, `docs/DECISIONS.md`, `docs/DEV_LOG.md`, `docs/RELEASE_NOTES.md`, `docs/TASK_STATE.md`, `docs/KNOWN_ISSUES.md`

### Валидация (Docker):
- `docker compose down && docker compose up -d --build` → стабильный старт.
- `docker compose run --rm web python manage.py check` → **0 issues**.
- `docker compose run --rm web python manage.py test apps.channels` → **33/33 OK**.
- `docker compose exec frontend npm run typecheck` → **EXIT=0**.
- `docker compose exec frontend npm run build` → **EXIT=0** (729 модулей).
- `docker compose exec frontend npm run test` → **5/5 vitest OK**.

### Риски:
- Требуется настройка `VK_APP_ID` в `.env` и standalone-приложение на vk.com/dev для production.
- Имя контакта при `auto_create_lead` из ВК — «Клиент ВК <id>» (не запрашиваем `users.get` в первой версии).
- Вложения исходящих сообщений из CRM в ВК не поддерживаются.

---

## 2026-05-17 (4) — SEO-лэндинг с PageSpeed-оптимизацией

### Что сделано:
- **Корневой `/` — Django-шаблон вместо редиректа на SPA**: создан `templates/landing.html` с полным SEO-контуром и оптимизациями для 100 баллов PageSpeed.
- **SEO**: `<title>`, `<meta name="description">`, `canonical`, `robots index,follow`, Open Graph (title/description/type/url/locale), Twitter Cards (summary_large_image).
- **Структурированные данные**: JSON-LD с `@graph` из 4 сущностей — `Organization`, `WebSite`, `SoftwareApplication`, `FAQPage`.
- **Performance**: весь CSS инлайн в `<style>` (~6 KB), системные шрифты (без внешних запросов), inline SVG-иконки (0 изображений), `prefers-reduced-motion` guard, sticky header с `backdrop-filter`.
- **Accessibility**: `lang="ru"`, skip-link, `role="banner/main/contentinfo"`, `aria-label` для навигаций, `focus-visible` outline, контрастные цвета, touch targets ≥44 px.
- **Адаптивность**: CSS Grid с `auto-fit` + `minmax`, `@media (max-width:480px)` для padding/hero, flex-wrap в header/actions.
- **Секции**: Hero (gradient + CTA), Features (6 карточек), How it works (3 шага), Pricing (Simple/Basic/CRM), CTA banner, Footer.
- **Backend**: `config/views.py` — `landing_page()` с `canonical_url` из `PLATFORM_PROTOCOL` + `PLATFORM_DOMAIN`; `config/urls.py` — `path('', landing_page)`.
- **Production routing**: `vps-deployment/crm_prvms/docker-compose.yml` — `Path(\`/\`)` добавлен в `crm-api` Traefik router (priority 100), чтобы корень шёл на backend, а не на SPA.
- **Обратная совместимость**: `/login`, `/register`, `/app/*` по-прежнему редиректят на SPA (dev) или попадают в `crm-spa` (production). `LandingView.vue` оставлен как fallback для dev Vite-сервера.
- **Тесты**: `test_root_endpoint_renders_landing_page` заменил `test_root_endpoint_redirects_to_frontend_app`. 129/129 backend tests OK.

### Изменённые файлы:
- **Новый:** `templates/landing.html`
- **Изменены:** `config/views.py`, `config/urls.py`, `apps/tenants/tests/test_tenant_resolver.py`, `vps-deployment/crm_prvms/docker-compose.yml`

### Валидация (Docker):
- `docker compose down && docker compose up -d --build` → стабильный старт.
- `docker compose run --rm web python manage.py check` → **0 issues**.
- `docker compose run --rm web python manage.py test apps` → **129/129 OK**.
- `curl http://localhost:18100/` → **200 text/html**, содержит `<h1>CRM-платформа для продаж</h1>`, JSON-LD, canonical.
- `curl http://localhost:18100/login` → **302** на frontend SPA.

### Риски:
- В production необходимо убедиться, что Traefik Dashboard показывает router `crm-api` с `Path(\`/\`)` — проверить через `/opt/scripts/check-https.sh` или `curl localhost:8080/api/http/routers` после деплоя.
- PageSpeed 100 теоретически достижим, но фактический score зависит от сетевой задержки до сервера и может немного варьироваться. Рекомендуется проверить через PageSpeed Insights после production-деплоя.
- Отсутствие `og:image` и `twitter:image` — для полноты SEO нужно добавить изображение для соцсетей (1200×630px, <200KB, WebP).

---

## 2026-05-17 (3) — Реструктуризация меню и навигации CRM

### Что сделано:
- **Окно сделки — полноценный роут `/app/deals/:id`**: создан `DealDetailView.vue` с табами «Инфо / Активность / Чат». При клике на сделку в Kanban/списке — переход на страницу с URL, содержащим id сделки (можно дать ссылку). Удалён `DealDetailDialog` из `DealsView`.
- **Чат внутри сделки**: вкладка «Чат» показывает привязанные `chat_sessions` с возможностью переключения канала. Загрузка сообщений, отправка ответа, real-time WS (тот же `connectChatWs` паттерн, что и в `ChannelsView`).
- **В Контакте — связанные сделки**: в `ContactDrawer` добавлен таб «Сделки» с загрузкой через `contactDeals(id)` (`listDeals({ contact_id })`). Переход на `/app/deals/:id` при клике.
- **Компании в боковом меню**: добавлен пункт «Компании» (`/app/companies`) в первую группу меню.
- **Мессенджеры → настройки, в меню — Чаты**: создан `ChatsView.vue` (только чаты, без настроек каналов). Роут `/app/chats` ведёт на `ChatsView`. `ChannelsView` (настройки каналов) встроен как вкладка «Мессенджеры» в `SettingsView`.
- **Интеграции — неактивный пункт**: в `AppMenu` для «Интеграций» установлен `locked: true`; `withLock` сохраняет явный флаг.
- **Распределение → Команда**: `DistributionView` встроен как вкладка в `TeamView`. Убран отдельный пункт меню. Старый путь `/distribution` редиректит на `/app/team?tab=distribution`.
- **Уведомления → Настройки**: `NotificationsView` встроен как вкладка «Уведомления» в `SettingsView`. Убран отдельный пункт меню. Старый путь `/notifications` редиректит на `/app/settings?tab=notifications`. Доступ к `SettingsView` расширен до `owner` + `admin` (router meta).
- **Помощь**: в `Dockerfile.frontend` добавлен `COPY docs/user-guide ./src/docs/user-guide` — в production build md-файлы бандлятся. В dev volume mount уже был настроен в `docker-compose.yml`.

### Изменённые файлы:
- **Новые:** `frontend/src/views/DealDetailView.vue`, `frontend/src/views/ChatsView.vue`
- **Изменены:** `frontend/src/router/index.ts`, `frontend/src/layout/AppMenu.vue`, `frontend/src/views/DealsView.vue`, `frontend/src/views/ContactsView.vue`, `frontend/src/components/ContactDrawer.vue`, `frontend/src/views/TeamView.vue`, `frontend/src/views/SettingsView.vue`, `frontend/src/api/crm.ts`, `Dockerfile.frontend`

### Валидация (Docker):
- `docker compose down && docker compose up -d --build` → стабильный старт.
- `docker compose run --rm web python manage.py check` → **0 issues**.
- `docker compose run --rm web python manage.py test` → **129/129 OK**.
- `docker compose exec frontend npm run typecheck` → **EXIT=0**.
- `docker compose exec frontend npm run build` → **EXIT=0**.
- `docker compose exec frontend npm run test` → **5/5 vitest OK**.
- SPA routes (`/app/deals/1`, `/app/chats`, `/app/settings`, `/app/help`) → **200**.

### Риски:
- `frontend/src/docs/user-guide` на хосте остаётся пустой директорией (placeholder). `vite build` на хосте без Docker не найдёт md-файлы. Для локальной сборки вне Docker нужен symlink, но это не критично для production.
- Вложенные `FeatureGate` в `SettingsView` (NotificationsView/ChannelsView внутри) могут дублировать padding/section, но визуально приемлемо.
- SettingsView доступен admin — организационные настройки (name, brand_color и т.д.) пока не защищены от редактирования admin. Нужен guard в UI, если требуется owner-only.

---

## 2026-05-17 (2) — Hotfix: `SameSite=None` без `Secure` блокировал авторизацию в dev

### Корневая причина:
`_set_refresh_cookie` в `apps/users/auth_api.py` ставил `samesite='None'` безусловно. В dev (`DEBUG=True`) `secure=False`. Браузеры отклоняют cookie с `SameSite=None` без флага `Secure` (RFC 6265bis). Результат: пользователь успешно логинился через `/auth/login` (получал `access_token` в JSON), но `refresh_token` в httpOnly cookie отбрасывался браузером. При истечении access token или reload страницы frontend делал `POST /auth/refresh` без cookie → 400 «Missing refresh token» → catch обнулял access token → пользователь разлогинивался.

### Изменения:
`apps/users/auth_api.py`:
- `samesite='None'` → `samesite = 'Lax' if settings.DEBUG else 'None'`
- `secure=not settings.DEBUG` сохранён
- Для localhost cross-port (`frontend :15173` → `backend :18100`) `Lax` работает, потому что `localhost` с любым портом считается same-site. В prod `SameSite=None` + `Secure=True` остаётся.

### Валидация (Docker):
- `docker compose run --rm web python manage.py check` → **0 issues**.
- `docker compose run --rm web python manage.py test apps` → **129/129 OK**.
- Cookie header проверен: `Set-Cookie: refresh_token=...; SameSite=Lax` (dev).
- `curl` login + refresh с cookie jar → **200** на оба этапа.
- `docker compose exec frontend npm run typecheck` → **EXIT=0**.
- `docker compose exec frontend npm run build` → **EXIT=0**.

### Файлы:
- **Изменён:** `apps/users/auth_api.py`
- **Изменены:** `docs/KNOWN_ISSUES.md`, `docs/DEV_LOG.md`

### Риски:
- Регрессия cross-origin refresh в production маловероятна: prod использует `Secure=True` + `SameSite=None`, комбинация валидна.
- Если dev-окружение использует не `localhost`, а IP-адрес или другой домен, `Lax` может не отправлять cookie cross-origin. В таком случае рекомендуется добавить Vite proxy (`/api` → backend) или временно включить `Secure=True` с self-signed cert.

---

## 2026-05-17 — Сид-скрипт демо-пользователей (10 компаний × 3 пользователя + админ)

### Что сделано:
Добавлена отдельная management-команда `seed_demo_users` для массового создания тестовых аккаунтов в формате `email\password`.

**`apps/users/management/commands/seed_demo_users.py`:**
- Параметризуемое количество tenant-ов (`--count`, default=10).
- Каждый tenant получает 3 пользователя с ролями `owner`, `admin`, `manager`.
- Email-ы генерируются как `test1@<domain>` .. `test<N*3>@<domain>`; платформенный admin — `admin@<domain>`.
- Пароль единый для всех (`--password`, default=`Asdf2121`).
- Идемпотентность через `get_or_create` для `Tenant`, `User`, `Membership`, `Domain`.
- Автоматический провижионинг tenant-а через `apps.tenants.services.provision_tenant()` — создаётся дефолтная воронка «Продажи» + preferences.
- Guard на `DEBUG=False` без `--force` (как в `create_test_users`).

**`apps/users/tests/test_seed_demo_users_command.py`:**
- Тест с `--count 2` проверяет: tenant-ы, пользователей, membership-ы, пароли, роли, provision pipeline.
- `tearDown` вручную дропает созданные schema и удаляет shared-записи через raw SQL, чтобы избежать каскадного обращения к tenant-scoped таблицам (`integrations_managerprofile`) из public schema.

### Валидация (Docker):
- `docker compose run --rm web python manage.py check` → **0 issues**.
- `docker compose run --rm web python manage.py test apps.users.tests.test_seed_demo_users_command` → **1/1 OK**.
- `docker compose run --rm web python manage.py test apps` → **129/129 OK** (полный набор).
- `docker compose run --rm web python manage.py seed_demo_users --force` → отрабатывает, выводит 31 строку `email\password`.

### Файлы:
- **Новый:** `apps/users/management/commands/seed_demo_users.py`
- **Новый:** `apps/users/tests/test_seed_demo_users_command.py`
- **Изменены:** `docs/TASK_STATE.md`, `docs/DEV_LOG.md`

### Риски:
- Команда создаёт много tenant schema (10 по умолчанию). В dev-среде это допустимо; в production требует `--force`.
- Вывод паролей в stdout — допустимо для dev seed, но не для production secrets management.

---

## 2026-05-16 — Адаптация UI для мобильных: single-source responsive layer + card-таблицы (DEC-037)

### Корневая причина «боковое меню не скрывается на мобильном»:
**Баг CSS-специфичности, не JS-логики.** `useLayout.toggleMenu/hideMobileMenu` и watcher `route.path` в `AppSidebar` были корректны. В `styles/main.css` десктопное правило `.layout-static .layout-sidebar { transform: translateX(0) }` имело специфичность `(0,2,0)`, а мобильное `@media (max-width:991px) { .layout-sidebar { transform: translateX(-100%) } }` — `(0,1,0)`. Media query специфичности не добавляет, контейнер всегда несёт класс `layout-static` → десктопное правило всегда побеждало. Сайдбар был постоянно виден на телефоне (`translateX(0)`), перекрывал контент; переключение `layout-mobile-active` визуально ничего не делало (оба состояния → `translateX(0)`).

### Изменения:

**`frontend/src/styles/main.css` (структурный фикс + глобальный адаптивный слой):**
- Layout-режимы разнесены по взаимоисключающим media-диапазонам: desktop static/overlay → `@media (min-width: 992px)`, mobile off-canvas + mask → `@media (max-width: 991px)`, телефонный gutter → `@media (max-width: 640px)`. Коллизия специфичностей устранена структурно (десктопных селекторов ниже 992px больше нет).
- `.form-grid/.form-row-2/.form-row-3` — глобальные примитивы с responsive-сворачиванием (≤640px → 1 колонка). `.section-header` переносится на ≤640px.
- `.p-dialog`/`.p-drawer` → `max-width: 95vw` глобально (единая точка вместо 12 per-dialog `maxWidth`); `.p-dialog` → `width:95vw` на ≤640px.
- Topbar: `padding`, `gap` action-кнопок и `topbar-org-select` сжимаются на ≤991px; wordmark `.layout-topbar-logo span` скрыт на ≤480px.
- Глобальный CSS карточного режима таблиц под `.rt-cards` на ≤767px (PrimeVue-class-agnostic: `table/thead/tbody/tr/td`).

**`frontend/src/directives/responsiveTable.ts` (новый) + `main.ts`:**
- Директива `v-responsive-table`: тегирует корень таблицы `.rt-cards`, копирует текст заголовка колонки в `td[data-label]`, помечает пустую строку (`colspan`) `.rt-empty-row`. Ре-синк через Vue `updated` + `MutationObserver` (childList, без петли — директива меняет только атрибуты). Зарегистрирована глобально в `main.ts`.
- Селекторы сверены с исходниками PrimeVue 4.4 (`node_modules/primevue/datatable`): семантические `<table><thead><tr><th>`/`<tbody><tr><td>` + `colspan` в empty-message — совпадает.

**Per-view:**
- Удалены дублирующие scoped `.form-row-2`/`.form-grid` из `ContactsView`, `DealsView`, `QuickContactDialog`, `QuickCompanyDialog`, `DealFormDialog`, `DealDetailDialog` (scoped `[data-v-*]` затенял бы глобальный media-override).
- `v-responsive-table` применена ко всем 24 `PDataTable` (15 файлов).
- `tasks-layout`/`assistant-layout` → 1 колонка на ≤768px (список диалогов ассистента ограничен `max-height:38vh`).
- `.tabs-bar`/`.tab-bar` (ContractsView, TeamView, PipelinesView) → `flex-wrap` + `overflow-x:auto`.

### Валидация (Docker):
- `docker compose down` && `docker compose up -d --build` → все контейнеры Up; `db`/`redis` healthy.
- `docker compose run --rm web python manage.py check` → **System check identified no issues (0 silenced)**.
- `docker compose exec frontend npm run typecheck` → **EXIT=0** (vue-tsc, нет ошибок).
- `docker compose exec frontend npm run build` → **EXIT=0** (сборка успешна; chunk-size warning — преэкзистинг, не ошибка).
- `docker compose exec frontend npm run test` → **5/5 passed**.
- Render: dev SPA `/app` → **200**, web root → **302** (redirect, DEC-011). В собранном бандле присутствуют `rt-cards`, `min-width:992px`, `max-width:991px`, `data-label` (CSS прошёл через Vite); `responsive-table`/`rt-empty-row` в JS (директива забандлена).

### Файлы:
- **Новый:** `frontend/src/directives/responsiveTable.ts`.
- **Изменены:** `frontend/src/styles/main.css`, `frontend/src/main.ts`; `frontend/src/views/{ContactsView,DealsView,TasksView,AssistantView,ContractsView,TeamView,PipelinesView,AuditView,CompaniesView,DistributionView,NotificationsView,StatsView,SubscriptionView,TelephonyView}.vue`; `frontend/src/components/{QuickContactDialog,QuickCompanyDialog,DealFormDialog,DealDetailDialog,ChannelsTab,ConnectionsTable,PipelineSettings}.vue`; `docs/{DECISIONS,TASK_STATE,DEV_LOG,KNOWN_ISSUES,RELEASE_NOTES}.md`, `CHANGELOG.md`.

### Версия:
- Релиз `0.2.6` — `## [0.2.6] — 2026-05-16` в CHANGELOG (DEC-036 + DEC-037). PATCH: bugfix (специфичность sidebar) + responsive hardening существующего UI; новой пользовательской функциональности/обратно-несовместимых изменений API нет (по `docs/VERSIONING.md`).
- `VERSION` → `0.2.7-dev` (следующий рабочий цикл). Соглашение: CHANGELOG ведём только датированными релизными секциями `## [X.Y.Z] — YYYY-MM-DD`, без `unreleased`/`-dev`-плейсхолдеров.

### Риски:
- Браузер-QA на реальном устройстве в этой среде не выполнялся (нет браузера). Фикс специфичности детерминирован (доказуем по правилам каскада CSS, не эвристика); DOM-предположения директивы сверены с исходниками PrimeVue 4.4. Рекомендуется визуальный прогон на устройстве/эмуляторе (sidebar drawer, card-таблицы, диалоги, kanban swipe) — KNOWN_ISSUES #16.
- Карточный режим скрывает шапку и показывает `data-label` из текста `<th>`; колонки с пустым `header=""` (action-колонки) корректно остаются без лейбла (CSS `content:none`).
- Поведение десктопа (≥992px) не изменено: layout-режимы те же правила, лишь обёрнуты в `min-width:992px`.

## 2026-05-15 — Рефакторинг P0–P2: декомпозиция монолитных api/services + восстановление типобезопасности (DEC-036)

### Что сделано:
Поведение-сохраняющий рефакторинг по паттерну DEC-032 (sibling-модули + тонкий shim). 7 треков; P2-1 (декомпозиция `.vue`) выполнен в этой же сессии после усиления валидационного гейта `vite build` (см. раздел P2-1 ниже).

- **P0-1** `apps/crm/api.py` (864 LOC) → `_api_common.py` + `contacts_api/companies_api/pipelines_api/deals_api/activities_api/stats_api` + shim (23 LOC).
- **P0-2** `CrmDeal` дополнен (`created_at/expected_close_date/loss_reason`); сняты все 9 `as any` в `DealsView.vue` + 2 на границе SIP.js (`Web.SessionDescriptionHandler`, `creds.sip_domain`). Инвариант DEC-032 «0 `as any`» восстановлен.
- **P1-1** `apps/integrations/api.py` (705 LOC) → `_api_common.py` + `connections_api/webhooks_api/oauth_api` + shim. Request/URL-coupled хелперы оставлены в API-слое (не в `services.py`).
- **P1-2** `apps/contracts/services.py` (558 LOC) → `mapping/pdf/otp/esign_agreement/signing` + shim. Ацикличный граф импортов.
- **P1-3** `composables/useApiCall.ts` (единая точка DEC-031); `DealsView.vue` полностью переведён (13 вызовов).
- **P2-2** все CRM `XIn/XPatchIn` → `apps/crm/schemas.py`.
- **P2-1** выполнен (декомпозиция `DealsView`/`IntegrationsView`/`ChannelsView` → 8 компонентов) — см. раздел P2-1 ниже.

### Файлы:
- **Backend:** `apps/crm/{_api_common,contacts_api,companies_api,pipelines_api,deals_api,activities_api,stats_api,schemas,api}.py`; `apps/integrations/{_api_common,connections_api,webhooks_api,oauth_api,api}.py`; `apps/contracts/{mapping,pdf,otp,esign_agreement,signing,services}.py`; `apps/contracts/tests/test_signing_flow.py` (патч-цели OTP перенаведены на `apps.contracts.signing.*`).
- **Frontend:** `frontend/src/api/crm.ts` (`CrmDeal`), `frontend/src/views/DealsView.vue`, `frontend/src/composables/{useApiCall.ts,useSIPPhone.ts}`.

### Валидация (Docker):
- `docker compose run --rm web python manage.py check` → System check identified no issues.
- `docker compose run --rm web python manage.py test apps` → **Ran 128 tests — OK**.
- `docker compose run --rm web python manage.py test apps.crm apps.integrations apps.contracts` → 24/24 OK.
- `docker compose run --rm --no-deps frontend npm run typecheck` → **EXIT=0, нет ошибок**.
- `docker compose run --rm --no-deps frontend npm run test` → **5/5 passed**.

### P2-1 (декомпозиция крупных `.vue` — выполнено в этой же сессии):
Паттерн «parent owns state, child presentational»: вся логика/WS/loading остаются в родителе, дочерний компонент — презентационная оболочка, реактивные form-объекты передаются по ссылке, действия — через emits. Валидационный гейт усилен реальным `vite build` (полная компиляция `.vue`, резолв пропсов/импортов) — сильнее, чем `vue-tsc --noEmit`.
- `DealsView` 760→623: `QuickContactDialog`, `QuickCompanyDialog`, `DealFormDialog`, `DealDetailDialog`.
- `IntegrationsView` 645→415: `IntegrationSetupCard`, `ConnectionsTable`, `IntegrationErrorsDialog`.
- `ChannelsView` 605→452: `ChannelsTab` + `ChatsTab`. ChatsTab владеет только scroll-DOM-узлом и экспонирует `scrollToBottom()` через `defineExpose`; WS-lifecycle/`sendMessage`/`loadMessages` в родителе вызывают его в тех же 4 точках, где раньше стоял `messagesContainer.scrollTop` — 1:1 перенос потока, проверяемый typecheck+build.
- **Новые файлы:** `frontend/src/components/{QuickContactDialog,QuickCompanyDialog,DealFormDialog,DealDetailDialog,IntegrationSetupCard,ConnectionsTable,IntegrationErrorsDialog,ChannelsTab,ChatsTab}.vue` (9); изменены `frontend/src/views/{DealsView,IntegrationsView,ChannelsView}.vue`. Вошло в релиз `0.2.6` (2026-05-16) вместе с DEC-037.
- **Валидация P2-1:** `npm run typecheck` EXIT=0; `npm run build` EXIT=0 (706 модулей, поэтапно после каждого view); `npm run test` 5/5. Backend не затронут.

### Риски:
- Поведение API и signing/ПЭП не изменено (чистое перемещение + shim re-export); shim сохраняет все внешние импорты.
- P2-1 поведение-эквивалентен и проверен `typecheck`+`vite build`; реактивные form-объекты передаются по ссылке (тот же proxy), вся логика — в родителях. Полноценный browser-QA (Kanban DnD, детали сделки, диалоги интеграций/каналов) рекомендуется при следующем визуальном прогоне.
- P2-1 выполнен полностью, включая ChatsTab (паттерн `defineExpose({scrollToBottom})`). Релиз `0.2.6` (2026-05-16, PATCH: рефакторинг без видимых пользователю изменений + DEC-037). Будущие кандидаты на тот же паттерн: `TelephonyView`/`ContractsView` (KNOWN_ISSUES #15).

## 2026-05-13 — Исправление создания сделок из Telegram/MAX + рефакторинг мессенджер-каналов (DEC-035)

### Корневая причина:
Пользователи сообщали, что сделки не создаются от входящих сообщений в Telegram и MAX. Аудит выявил четыре независимые проблемы:
1. **Telegram `edited_message` не обрабатывался** — `normalize_incoming_payload` брал `payload.get('message') or payload`, и если update содержал `edited_message`, возвращался весь Update-объект. `chat_id` становился `'unknown'`, сообщения сливались в одну сессию или терялись.
2. **MAX `bot_started` создавал мусорную сессию** — update без `message` возвращал `chat_id='unknown'`, и все `bot_started` события сливались в одну `ChatSession`.
3. **Отсутствие Pipeline/Stage — silent failure** — если пользователь удалил воронку или этапы, `auto_create_lead` просто пропускал блок `if pipeline:` и `if stage:` без логирования. Сообщение сохранялось, но сделка не создавалась, и ops не видели причину.
4. **Широкий `except Exception`** — любая ошибка при создании сделки (включая баги в `_build_contact` или `Deal.objects.create`) проглатывалась, логировалась, но `message.error` был пустым, если ошибка происходила до записи.

### Изменения:

**`apps/channels/providers.py`:**
- `normalize_incoming_payload` возвращает `dict | None`.
- Telegram: `message = payload.get('message') or payload.get('edited_message')`; остальное (`callback_query`, `inline_query`) → `None`.
- MAX: `update_type == 'bot_started'` → `None`; `message_created` → корректная нормализация.
- `register_telegram_webhook`: `allowed_updates` расширен до `['message', 'edited_message']`.
- `send_outgoing`: `except Exception` → `except requests.RequestException`.

**`apps/channels/tasks.py`:**
- `_find_pipeline_and_stage()` — явный поиск с логированием `warning` при отсутствии pipeline или stage.
- `_build_contact()` — выделенная функция для создания/поиска контакта.
- `_auto_create_lead()` — выделенная функция; при отсутствии pipeline/stage записывает `message.error = 'Воронка или этап не настроены — сделка не создана'` и `delivered=False`.
- `_sync_to_external_crm()` — выделенная функция для внешних CRM.
- `route_incoming_message`: проверка `normalized is None` → возврат `{'status': 'ignored'}`.
- Узкие `except` вокруг `_auto_create_lead` и `_sync_to_external_crm`.

**`apps/channels/public_views.py`:**
- Добавлено `logger.info` для принятых webhook'ов.
- Добавлено `logger.warning` для 404 (tenant/channel не найден) и 403 (невалидный токен).

**`apps/channels/tests/test_bridge.py`:**
- Расширен с 3 до 13 тестов.
- Новые тесты: `edited_message`, `callback_query` (ignored), MAX `message_created`, MAX `bot_started` (ignored), отсутствие Pipeline, отсутствие Stage, `auto_create_lead=False`, внешняя CRM (`amocrm`).

### Валидация:
- `docker compose run --rm web python manage.py check` → 0 issues.
- `docker compose run --rm web python manage.py test --keepdb` → 128/128 OK.
- `docker compose run --rm frontend npm run typecheck` → зелёный.
- `docker compose run --rm frontend npm run test` → 5/5 OK.

### Файлы:
- `apps/channels/tasks.py`
- `apps/channels/providers.py`
- `apps/channels/public_views.py`
- `apps/channels/tests/test_bridge.py`
- `docs/DECISIONS.md`
- `docs/DEV_LOG.md`
- `docs/KNOWN_ISSUES.md`
- `docs/TASK_STATE.md`

### Риски:
- `normalize_incoming_payload` теперь возвращает `None` для `callback_query` и `inline_query`. Ранее они создавали сессию с `chat_id='unknown'` — это было багом, но если кто-то полагался на это поведение (маловероятно), поведение изменилось.
- `allowed_updates: ['message', 'edited_message']` в `register_telegram_webhook` — Telegram больше не будет слать `callback_query` на webhook. Если в будущем понадобятся кнопки, нужно будет расширить список.

---

## 2026-05-11 (3) — Финальная доводка HTTPS: дроп frontend-app healthcheck + симлинки compose self-heal (DEC-034)

### Что осталось не пофикшено после DEC-034 первой итерации:
После выкатки правок (DEC-034 v1) на сервер `/` всё равно отдавало 404. Дебаг показал:
1. **`/opt/crm_prvms/docker-compose.yml` оказался копией**, а не симлинком на `vps-deployment/crm_prvms/docker-compose.yml`. Git pull обновлял источник, но компоуз-файл, по которому реально стартует стек, оставался замороженным. `docker compose up -d` использовал старый healthcheck (`localhost`) → контейнер unhealthy → Traefik не регистрирует роутер → 404 на любом пути.
2. Healthcheck для `frontend-app` через busybox-wget остаётся хрупким: он чувствителен к IPv6/IPv4-резолву, PATH, наличию `wget` нужного билда. Каждый малейший сбой делает контейнер `unhealthy`, и Traefik сразу его выкидывает — это слишком хрупкая ситуация для SPA-nginx, который вообще не нуждается в health-проверке.

### Изменения (поверх DEC-034 v1):

**`vps-deployment/crm_prvms/docker-compose.yml`:**
- `frontend-app`: healthcheck **полностью удалён**. Traefik v2 docker provider трактует контейнеры без healthcheck как healthy и сразу регистрирует роутеры. nginx со статикой не падает; если упадёт — Docker restart policy поднимет. Комментарий в файле объясняет почему.
- `web`: healthcheck переписан на `curl -fsS http://127.0.0.1:8000/healthz -o /dev/null` — IPv4-литерал вместо `localhost`, `-fsS` для надёжного non-zero exit при HTTP-ошибке. Работает благодаря `HealthCheckBypassMiddleware`.

**`vps-deployment/crm_prvms/deploy.sh`:**
- Новая функция `ensure_root_layout()` пересоздаёт симлинки `/opt/crm_prvms/docker-compose.yml`, `deploy.sh`, `.env.prod.example` → `vps-deployment/crm_prvms/*` каждый раз при запуске. Если файл оказался копией — он переименовывается в `<file>.copy_replaced_<timestamp>.bak`, и на его месте создаётся симлинк. Запускается **первым шагом** main(), до проверки env и compose.
- `bring_up()` теперь использует `up -d --remove-orphans --force-recreate` — гарантирует, что compose-level изменения (healthcheck, labels) фактически попадают в свежесозданные контейнеры, а не игнорируются кешем.
- `wait_for_health()` ждёт `web=healthy` (HealthCheckBypassMiddleware → liveness independent of tenants) и `frontend-app=Up` (без healthcheck больше не существует "healthy" статус, контейнер просто running).

**`vps-deployment/scripts/start-all.sh`:**
- Зеркальная функция `ensure_crm_root_symlinks()` вызывается из `prepare_project_env` для `crm_prvms`. То же самое поведение — обнаружила копию → бэкапит и пересоздаёт симлинк. Так не понадобится отдельный fix-команды на сервере: первый же `start-all.sh` или `deploy.sh` после `git pull` чинит layout.

### Валидация:
- `bash -n` на `deploy.sh`, `start-all.sh`, `check-https.sh`, `fix-https.sh` — все чистые.
- `docker compose config` рендерит compose с правильным web healthcheck (`curl ... 127.0.0.1`) и **без** healthcheck у frontend-app.
- `manage.py check` — clean (изменений в Django-коде в этой итерации нет, всё держится на DEC-034 v1).

### Деплой на сервер (после git pull):
```bash
cd /opt/crm_prvms
git pull
./vps-deployment/crm_prvms/deploy.sh   # или прежний путь — оба работают
```
`deploy.sh` сам:
1. Пересоздаст симлинки `/opt/crm_prvms/docker-compose.yml`, `deploy.sh`, `.env.prod.example`.
2. Соберёт образы.
3. Прогонит миграции и collectstatic.
4. Force-recreate всех контейнеров (старый frontend-app с healthcheck исчезнет, новый — без него).
5. Перезапустит Traefik (defensive measure из DEC-033).

Через 30–60 секунд после `up -d`: контейнеры running/healthy, Traefik видит все три роутера, Let's Encrypt выдаёт сертификат.

### Риски:
- frontend-app без healthcheck → если nginx-конфиг сломан после деплоя, Traefik будет роутить трафик на бракованный контейнер. Митигация: nginx-конфиг в репо (`frontend/nginx.conf`) проверяется на CI/локально; SPA-build верифицируется `vite build` шагом в Dockerfile.frontend.
- `--force-recreate` добавляет ~10 секунд к каждому деплою. Цена приемлемая за гарантию что compose-level изменения применились.

## 2026-05-11 (2) — Корневое исправление HTTPS: healthcheck → tenant middleware → Traefik filtering (DEC-034)

### Корневая причина:
DEC-033 устранил часть проблем (стало проще диагностировать, перезапуск Traefik подхватывает свежие контейнеры), но Let's Encrypt-сертификат для `crm.prvms.ru` всё равно не выдавался. Debug-лог Traefik (`--log.level=DEBUG`) показал точную причину: `Filtering unhealthy or starting container` для `crm_prvms-web` и `crm_prvms-frontend-app`. Traefik 2.x **намеренно** не регистрирует роутеры контейнеров в статусе `unhealthy`/`starting` — это документированное поведение Docker provider. Дальнейший анализ дал две независимые причины unhealthy:

1. **web → 404 на `/healthz`.** Endpoint существует в `config/urls.py`, но `django_tenants.middleware.main.TenantMainMiddleware` стоит **перед** URL-резолвом. Docker healthcheck бьёт `curl http://localhost:8000/healthz`, домен `localhost` отсутствует в shared `Domain` table — middleware возвращает 404 до того, как `config/urls.py` получит запрос. `SHOW_PUBLIC_IF_NO_TENANT_FOUND=True` в этой конфигурации поведение не меняет.
2. **frontend-app → connection refused.** Healthcheck `wget -q --spider http://localhost/`. Busybox-wget в `nginx:alpine` резолвит `localhost` → `::1` и не делает fallback на IPv4. Nginx слушает только IPv4 (entrypoint `10-listen-on-ipv6-by-default.sh` сам сообщает, что не дописал IPv6-listen: `default.conf differs from packaged version`).

Дополнительный триггер (изначальный пусковой механизм): серверный `.env.prod` был создан без `PUBLIC_HOSTNAME`. Compose интерполировал лейбл в `Host(``)`, и Traefik сразу отбрасывал такие роутеры. После добавления переменной всплыла настоящая причина — unhealthy filter.

### Изменения:

**Backend:**
- `apps/core/middleware.py`: добавлен `HealthCheckBypassMiddleware`. Отвечает `JsonResponse({'status':'ok'})` на `/healthz` и `/healthz/` **до** любых других middleware. Liveness-probe больше не зависит от состояния тенантов.
- `config/settings.py`: `HealthCheckBypassMiddleware` поставлен первым в `MIDDLEWARE`, перед `TenantMainMiddleware`.

**Infra:**
- `vps-deployment/crm_prvms/docker-compose.yml`: healthcheck `frontend-app` использует `http://127.0.0.1/` вместо `localhost`. Комментарий в файле объясняет почему — busybox wget без IPv6→IPv4 fallback.
- `vps-deployment/scripts/start-all.sh`: добавлен preflight в `check_build_prereqs` для `crm_prvms` — отказ запуска при отсутствии `PUBLIC_HOSTNAME` в `.env.prod`. Fail-fast вместо silent-fail с `Host(``)`.

**Безопасность репозитория:**
- `.gitignore`: убран блок-исключение `/vps-deployment` (мешал отслеживать полезные файлы — скрипты, compose, шаблоны). Добавлены прицельные паттерны `vps-deployment/**/.env*`, `acme.json`, `logs/`, `media/`. Шаблон `.venv*` обобщён, чтобы поймать любые серверные снапшоты.
- Удалён `vps-deployment/crm_prvms/.venv.current_on_server` — снимок production env с реальными секретами (SECRET_KEY, DB_PASSWORD, FIELD_ENCRYPTION_KEY, HERMES_API_KEY, OPENCODE_API_TOKEN). Файл лежал untracked, но в репозитории — теоретически мог попасть в коммит. Рекомендована ротация затронутых ключей на сервере.

### Валидация:
- `docker compose run --rm web python manage.py check` — проходит.
- `bash -n vps-deployment/scripts/start-all.sh` — синтаксис ок.
- `docker compose config` для `crm_prvms` — лейблы интерполируют `Host(\`crm.prvms.ru\`)` при заполненном `.env.prod`; fail-fast при пустом.

### Риски:
- `HealthCheckBypassMiddleware` обходит весь стек, включая CSRF/auth. Это корректно для liveness-probe, но эндпоинт намеренно ничего не проверяет в БД/Redis — это readiness-probe, а не healthcheck зависимостей. Если потребуется проверять зависимости, добавить отдельный `/readyz` после tenant middleware.
- DEC-033 (рестарт Traefik в `start-all.sh`/`deploy.sh`/`fix-https.sh`) сохранён — устраняет редкие пропуски Docker-events. Не дублирует DEC-034.

### План для сервера (на следующий деплой):
1. `cd /opt/crm_prvms && git pull`
2. Убедиться что `/opt/crm_prvms/.env.prod` содержит `PUBLIC_HOSTNAME=crm.prvms.ru` (если нет — `echo PUBLIC_HOSTNAME=crm.prvms.ru >> .env.prod`).
3. `./deploy.sh` (он сам пересоберёт образы web/frontend-app, контейнеры станут healthy, Traefik подхватит роутеры, Let's Encrypt выдаст сертификат за ~60 секунд).
4. `sudo /opt/scripts/check-https.sh` — итоговая проверка.

## 2026-05-11 — Системное исправление HTTPS на shared VPS (DEC-033)

### Корневая причина:
Проект `crm_prvms` на shared VPS не получал Let's Encrypt сертификат. В логах Traefik отсутствовали записи о создании роутеров для CRM. Временный скрипт `fix-crm-https.sh` маскировал проблему перезапусками, но не устранял первопричину.

### Изменения:
- **Удалён** `vps-deployment/scripts/fix-crm-https.sh` (временное точечное решение).
- **`vps-deployment/scripts/fix-https.sh`**: добавлены `inspect_proxy_network()` (проверка overlay/attachable), `check_traefik_routes()` (curl к `localhost:8080/api/http/routers`), `restart_traefik_to_discover()` (down/up после всех проектов).
- **`vps-deployment/scripts/start-all.sh`**: добавлен `restart_traefik()` — вызывается после цикла запуска всех проектов.
- **`vps-deployment/scripts/check-https.sh`**: проверка `driver=overlay`/`attachable=true` для сети `proxy`; `check_traefik_routes()` — валидирует наличие каждого проектного роутера.
- **`vps-deployment/crm_prvms/deploy.sh`**: добавлен `restart_traefik()` после `bring_up`.

### Валидация:
- `docker compose config` валиден для `traefik` и `crm_prvms`.
- bash syntax check: `bash -n` для всех изменённых `.sh` — ок.

### Риски:
- Перезапуск Traefik добавляет ~15 секунд к `start-all.sh` и `deploy.sh`.
- Если Traefik Dashboard (порт 8080) недоступен, `check_traefik_routes()` вернёт ошибку — это ожидаемое поведение.

## 2026-05-10 — Полный рефакторинг A-E (DEC-032)

### Корневая причина:
Аудит выявил несколько P0/P1 проблем в кодовой базе:
1. **ai_assistant миграция** содержала камелкейс-поле `herMes_conversation_id` и избыточный `tenant` FK на public.tenants.Tenant. При создании второго тенанта в тестовой БД миграция применялась некорректно → `relation "ai_assistant_aiconversation" does not exist` (KNOWN_ISSUES #5).
2. **Vite dev `/app` → 500 EISDIR**: `working_dir: /app` в `docker-compose.yml` коллидировал с SPA-маршрутом `/app` (KNOWN_ISSUES #6).
3. **Frontend typecheck нестабилен**: ~12 кастов `(... as any)` обходили типизацию, `CrmContact/CrmDeal` не описывали реальные поля backend-ответа, `IvrMenu.options` имел тип `Record<string, unknown>[]` (KNOWN_ISSUES #4).
4. **Нарушение инкапсуляции**: `apps/users/api.py:18` импортировал приватный `_seed_default_pipeline` из `apps.tenants.onboarding_api` — CRM-логика просочилась в auth-flow.
5. **God-modules**: `apps/users/api.py` (769 LOC) совмещал auth + invites + roles + role-permissions + manager-profiles. `frontend/src/views/CRMView.vue` (2023 LOC) дублировал функциональность DealsView/ContactsView/TasksView.
6. **23 bare `except Exception:`** в production-коде (часть с logger, часть silent-pass).
7. **`console.log` в production-bundle**: stores/notifications.ts (7 шт), stores/ai.ts (2 шт).

### Изменения:

**Фаза A — Стабилизация:**

`apps/ai_assistant/models.py`:
- Удалён `tenant` FK (избыточен, нарушал чистоту tenant schema).
- `herMes_conversation_id → hermes_conversation_id`.

`apps/ai_assistant/migrations/0001_initial.py`: перегенерирован под новую схему модели (БД пустая по подтверждению).

`apps/ai_assistant/api.py`, `apps/ai_assistant/consumers.py`: убраны `tenant=tenant`/`tenant_id=tenant.id` из фильтров и `objects.create()`.

`apps/ai_assistant/tests/__init__.py`: удалён дубликат тестов (был полным копи-пейстом `test_ai_assistant.py`).

`docker-compose.yml`: `working_dir: /app → /srv/app` для frontend, все volume-mount-ы перенесены (`./frontend:/srv/app`, `./docs/user-guide:/srv/app/src/docs/user-guide:ro`, `frontend_node_modules:/srv/app/node_modules`).

`frontend/src/api/crm.ts`: `CrmContact` расширен (`position/messenger_id/source/esign_agreement_signed_at/esign_agreement_id`); добавлены `CrmDealContractRef`, `CrmDealChatSessionRef`; `CrmDeal` получил `contracts/chat_sessions/source` рефы.

`frontend/src/api/telephony.ts`: `IvrMenu.options: Array<Record<string, unknown>>` → `IvrMenuOption[]` (`{digit, action}`).

`frontend/src/api/http.ts`: переписан — retry-логика вынесена из `onResponseError` в обёртку `api()`; импортирован `MappedResponseType` для корректного return-type generic.

`frontend/src/api/auth.ts`: `register(payload: Record<string, unknown>)` → `register(payload: RegisterPayload)`. RegisterPayload экспортируется и импортируется в `stores/auth.ts`.

`frontend/src/views/TeamView.vue`: добавлен пропущенный `const activeTab = ref<...>('members')` (использовался в template без объявления).

`frontend/src/views/TelephonyView.vue`: убран cast `(ivr.options as IvrOption[])`, push в options теперь корректно создаёт все поля.

12 кастов `(... as any)` устранены в `ContactDrawer.vue`, `ContactsView.vue`, `CRMView.vue` (последний удалён в C1).

`frontend/tsconfig.json`: добавлен `"skipLibCheck": true`.

**Фаза B — Backend архитектура:**

`apps/tenants/services.py` (новый): публичный domain-сервис с `ensure_default_pipeline()` и `provision_tenant(tenant)`. Все шаги тенант-провижининга (preferences seeding, pipeline seeding) идут через эту единую точку.

`apps/users/api.py`: импорт `_seed_default_pipeline` через границу app удалён, вызов заменён на `provision_tenant(tenant)`.

`apps/tenants/onboarding_api.py`: вызовы `_seed_default_pipeline()` заменены на `ensure_default_pipeline()` из сервиса; локальное определение функции удалено.

`apps/users/auth_api.py` (новый, ~390 LOC): login/register/refresh/logout/me/organizations/switch-tenant/invite-check/invite-accept + private helpers (`_set_refresh_cookie`, `_resolve_auth_username`, `active_joined_memberships_queryset`, `build_invite_link`, `next_available_username`).

`apps/users/team_api.py` (новый, ~270 LOC): list_users/invite/role/role-permissions/deactivate/resend-invite + `_normalize_membership_role`/`_normalize_email`.

`apps/users/managers_api.py` (новый, ~80 LOC): manager_profiles CRUD + days-off; импортирует `users_router` из `team_api` (side-effect attaches endpoints). Так URL остаются стабильными.

`apps/users/api.py` (shim, 18 LOC): re-exports `auth_router`, `users_router`. Side-effect import `from . import managers_api` для регистрации endpoint-ов.

`apps/users/auth_api.py`: `except Exception:` для `RefreshToken(raw)` и `.blacklist()` сужены до `TokenError` (ninja-jwt).

`apps/contracts/api.py`, `apps/core/channels_auth.py`: JWT broad except → `TokenError | User.DoesNotExist | KeyError`.

`apps/crm/api.py:665`: `except Exception:` → `except User.DoesNotExist:`.

`apps/contracts/services.py:458`: silent pass на reopen PDF — конкретизирован `except (FileNotFoundError, OSError):` + `logger.warning`.

`apps/contracts/public_views.py:159`: добавлен `logger.exception` для broad except (email delivery).

`apps/ai_assistant/services.py`: добавлен `logger`. Broad except → `Contact.DoesNotExist` для contact lookup; `requests.RequestException` для Hermes-уведомления (с `logger.warning`).

`apps/telephony/tasks.py`: оставлено broad `except Exception:` с явным комментарием «greenswitch raises plain Exception subclasses» — это defense-in-depth против внешней библиотеки без публичной иерархии исключений.

**Фаза C — Frontend:**

Удалён `frontend/src/views/CRMView.vue` (2023 LOC). Создано три view взамен:
- `CompaniesView.vue` (167 LOC) — компании CRUD; `/app/companies`.
- `PipelinesView.vue` (480 LOC) — воронки + stages + триггеры с двумя tabs; `/app/pipelines`.
- `StatsView.vue` (135 LOC) — pipeline + manager statistics; `/app/stats`.

Дубликаты Kanban (DealsView), Contacts (ContactsView), Tasks (TasksView) — оставлены как единая точка правды; в CRMView они дублировались.

`frontend/src/router/index.ts`:
- Импорт CRMView удалён, добавлены CompaniesView/PipelinesView/StatsView.
- `/app/crm` → redirect на `/app/deals`.
- Top-level `/crm` → redirect на `/app/deals`.

`frontend/src/layouts/SidebarNav.vue`: добавлены пункты «Компании», «Воронки», «Аналитика CRM» в первой группе.

`frontend/src/utils/logger.ts` (новый): scoped logger (`createLogger(scope)`) с уровнями debug/info/warn/error; `debug/info` молчат в production (`import.meta.env.DEV`).

`frontend/src/stores/notifications.ts`, `frontend/src/stores/ai.ts`, `CompaniesView/PipelinesView/StatsView`: `console.log/console.error` → `log.debug/log.error`.

**Фаза E — Документы:**

`docs/DECISIONS.md`: исправлена нумерация — DEC-007 (дубль) → DEC-007a; DEC-020 (Presence) → DEC-A01; DEC-021 (branding) → DEC-A02; DEC-XXX → DEC-029. Добавлены DEC-031 (UI error handling — отделён от DEC-030) и DEC-032 (полный рефакторинг).

`docs/KNOWN_ISSUES.md`: #4, #5, #6 закрыты со ссылкой на DEC-032; добавлен открытый #11 (отсутствие CI).

`docs/TASK_STATE.md`: запись #22 о DEC-032.

### Файлы (33 файлов изменено, 5 удалено, 6 созданных):

**Backend (изменено):**
- `apps/ai_assistant/models.py`, `apps/ai_assistant/migrations/0001_initial.py`
- `apps/ai_assistant/api.py`, `apps/ai_assistant/consumers.py`
- `apps/ai_assistant/services.py`, `apps/ai_assistant/tests/__init__.py`, `apps/ai_assistant/tests/test_ai_assistant.py`
- `apps/users/api.py` (shim), `apps/tenants/onboarding_api.py`
- `apps/contracts/api.py`, `apps/contracts/services.py`, `apps/contracts/public_views.py`
- `apps/core/channels_auth.py`, `apps/crm/api.py`, `apps/telephony/tasks.py`

**Backend (новые):**
- `apps/tenants/services.py`
- `apps/users/auth_api.py`, `apps/users/team_api.py`, `apps/users/managers_api.py`

**Frontend (изменено):**
- `docker-compose.yml`, `frontend/tsconfig.json`
- `frontend/src/api/crm.ts`, `frontend/src/api/telephony.ts`, `frontend/src/api/http.ts`, `frontend/src/api/http.test.ts`, `frontend/src/api/auth.ts`
- `frontend/src/router/index.ts`, `frontend/src/router/guards.ts`, `frontend/src/layouts/SidebarNav.vue`
- `frontend/src/stores/auth.ts`, `frontend/src/stores/notifications.ts`, `frontend/src/stores/ai.ts`
- `frontend/src/views/TeamView.vue`, `frontend/src/views/TelephonyView.vue`, `frontend/src/views/ContactsView.vue`, `frontend/src/components/ContactDrawer.vue`
- `frontend/nginx.conf`, `.gitignore`

**Frontend (новые):**
- `frontend/src/utils/logger.ts`
- `frontend/src/views/CompaniesView.vue`, `frontend/src/views/PipelinesView.vue`, `frontend/src/views/StatsView.vue`

**Frontend (удалено):**
- `frontend/src/views/CRMView.vue` (2023 LOC)

**Deployment (новые):**
- `vps-deployment/` — production Docker Compose, deploy-скрипт, env-шаблон

### Валидация:
- `docker compose run --rm web python manage.py check` → 0 issues ✅
- `manage.py test apps --keepdb` → 118/118 ✅ (включая 7/7 ai_assistant + 17/17 ранее падавших test_auth_api/test_invites_api/test_tenant_resolver)
- `manage.py migrate_schemas --tenant ai_assistant` зеро + applied на 33 tenant schemas — поле `hermes_conversation_id` без `tenant_id` подтверждено в `org-crm`.
- `npm run typecheck` → зелёный ✅ (был 20+ ошибок до начала)
- `npm run test` → 5/5 vitest ✅
- SPA HTTP smoke: `GET /, /app, /app/dashboard, /app/companies, /app/pipelines, /app/stats, /app/crm, /login` → все 200 (`/app/crm` redirect на `/app/deals`)

### Дополнительные изменения (в рамках DEC-032):

**`frontend/nginx.conf`**: добавлены location `/static/` (Django collected-static из shared volume) и `/assets/` (Vite build assets с immutable long-term cache).

**`frontend/src/router/guards.ts`**: добавлен token-presence guard — если токен валидный, но `user === null` (race при обновлении страницы), делается `me()` до редиректа на login. Страхует от false-positive logout после refresh-страницы в edge-сценариях.

**`.gitignore`**: добавлены паттерны `.env.prod`, `.env.local`, `.env.*.local` для локальных/продакшн-переопределений.

**`vps-deployment/`**: production-конфиг для развёртывания на VPS — Docker Compose (crm_prvms), deploy-скрипт, `.env.prod.example`, инструкция `DEPLOY.md`.

### Риски:
- DEC-032 — большой объём изменений (5 фаз). Регрессии возможны в редко-исполняемых ветвях кода (например, telephony ESL fallback, billing webhook parsing, OAuth callback amocrm/bitrix24). Backend tests покрывают smoke-сценарии, но не нагрузочные/edge cases.
- KNOWN_ISSUES #11 (отсутствие CI) — нет автоматической защиты от регрессий между ручными прогонами.
- D-фаза (pytest-django миграция, e2e тесты) пропущена по согласованию с пользователем — текущее покрытие остаётся базовым (smoke/integration).
- Удаление CRMView.vue: уникальные функции (companies/pipelines/triggers/stats) перенесены в новые views, но **переадресация `/app/crm` → `/app/deals`** меняет UX для пользователей, которые привыкли к табовому интерфейсу. Sidebar обновлён со всеми новыми пунктами.

---

## 2026-05-10 — Functional hardening: messengers, session, deals, distribution

### Корневая причина:
После редизайна 4 критичных функциональных контура перестали работать:
1. **auto_create_lead в мессенджерах** — Pipeline/Stage не создавались при регистрации тенанта (только при шаге 2 онбординга). При первом сообщении пользователя в бота `route_incoming_message` не находил pipeline → Deal не создавался → `session.crm_lead_id` оставался пустым → повторяющийся silent-failure.
2. **Выход при рефреше страницы** — Cookie `SameSite='None'` без `Secure` в dev-режиме (HTTP) приводила к отклонению куки браузерами на не-localhost хостах. В dev-режиме `SameSite='Lax'` достаточно для кросс-портовых запросов на localhost.
3. **В модалке сделки пропала кнопка создания контакта/компании** — `DealsView.vue` (`/app/deals`) не имел quick-create диалогов, которые были в `CRMView.vue` (`/app/crm`).
4. **Распределение не работало** — `try_distribute()` вызывалась с trigger `'new_deal'`, но дефолтное правило в онбординге создавалось с trigger `'new_lead'`. Синонимный фоллбек был задокументирован, но не реализован.

### Изменения:

**apps/users/api.py (регистрация + кука):**
- `register()`: добавлен вызов `_seed_default_pipeline()` после создания тенанта (рядом с `seed_default_preferences`)
- Импорт `_seed_default_pipeline` из `apps.tenants.onboarding_api`
- `_set_refresh_cookie()`: `samesite='Lax' if DEBUG else 'None'`, `secure=not DEBUG` — в dev `Lax+Secure=False` (работает на localhost), в prod `None+Secure=True`

**apps/tenants/onboarding_api.py:**
- `onboarding_skip()`: добавлен `_seed_default_pipeline()` при пропуске онбординга
- `_apply_distribution_step()`: `trigger='new_lead'` → `trigger='new_deal'`

**apps/channels/tasks.py:**
- `route_incoming_message()` auto_create_lead: обёрнут в try/except с логированием в message.error
- Запрос Pipeline: `filter(is_default=True, is_active=True)`, fallback `filter(is_active=True)`
- Запрос Stage: `pipeline.stages.order_by('sort_order', 'id').first()` (Stage не имеет `is_active`)

**apps/distribution/services.py:**
- `try_distribute()`: реализован синонимный фоллбек — если `'new_deal'` не нашёл правило, пробует `'new_lead'` и наоборот

**apps/distribution/models.py:**
- `DistributionLog.SOURCE_CHOICES`: добавлен `('builtin_crm', 'Встроенная CRM')`

**frontend/src/views/DealsView.vue:**
- Добавлены `canCreateContact`, `canCreateCompany` computed
- В форме создания сделки: контакт/компания с `select-with-add` + `+` кнопкой
- В форме редактирования сделки: то же самое
- Диалоги `showQuickContact`/`showQuickCompany` (имя, фамилия, телефон, email / название, ИНН, телефон)
- `submitQuickContact()` / `submitQuickCompany()`: создание через API, авто-выбор в форме
- CSS: `.select-with-add`, `.flex-1`

### Файлы (8 файлов изменено):
- `apps/users/api.py`
- `apps/tenants/onboarding_api.py`
- `apps/channels/tasks.py`
- `apps/distribution/services.py`
- `apps/distribution/models.py`
- `frontend/src/views/DealsView.vue`
- `docs/DEV_LOG.md`
- `docs/*` (RELEASE_NOTES, TASK_STATE, DECISIONS, KNOWN_ISSUES)

### Валидация:
- `docker compose down` / `up -d --build` ✅
- `manage.py check` → 0 issues ✅
- Frontend build: 686 modules ✅
- Frontend tests: 5/5 ✅
- Distribution tests: 2/2 ✅
- Channels tests: 3/3 ✅ (auto_create_lead + error handling)
- Onboarding tests: 1/1 ✅
- CRM tests: 8/8 ✅

### Риски:
- Пре-экзистинг: 1 tenant-тест падает с `ai_assistant_aiconversation` (KNOWN_ISSUES #5)
- Долгий cold-start тестов из-за создания БД (решается `--keepdb`)

### Дополнение 2026-05-10 (сессия — второе исправление):
После исправления cookie SameSite пользователь всё ещё выходил при рефреше. Корневая причина:
1. `auth.ts:39` — `isAuthenticated` требовал `state.user && getAccessToken()`. При сбое `me()` после успешного refresh'а `user` оставался null → `isAuthenticated = false` → logout.
2. `auth.ts:52-56` — catch в `initialize()` обнулял `user`, `organizations`, `tenant_slug` даже при валидном токене.
**Исправлено:**
- `isAuthenticated` → `getAccessToken() !== null` (токен — источник истины для аутентификации)
- catch в `initialize()`: не обнуляет slug/organizations; не обнуляет user если он уже был
- `apps/users/api.py:375`: `samesite='None'` всегда (Lax не отправляет куки при cross-origin `fetch()`)
**Изменённые файлы:** `frontend/src/stores/auth.ts`, `apps/users/api.py`

### Корневая причина:
После редизайна пользователи сообщили о неработающих кнопках в онбординге и других разделах. Аудит выявил системный паттерн: API-вызовы без обработки ошибок во всех view. Основные проблемы:
1. **`try { ... } finally { ... }` без `catch`** — в 4 view (TeamView, NotificationsView, IntegrationsView, OnboardingWizard): ошибки API проглатываются, кнопка перестаёт реагировать без обратной связи.
2. **Нулевая обработка ошибок** — в DealsView, ContactsView, DistributionView, ChannelsView: ни одного `try/catch`.
3. **Dead code** — в ChannelsView дублирующий `ws.onclose` перезаписывал логику переподключения WebSocket.
4. **План не загружен → всё заблокировано** — Dashboard/Sidebar применяли `pointer-events: none` до загрузки списка features.
5. **Критический баг онбординга** — `SameSite='Lax'` в куке `refresh_token` не давал браузеру отправлять cookie на кросс-ориджин POST из JS (фронтенд :15173 → бэкенд :18100). `NotificationBell` на странице онбординга вызывал `refresh()` → `POST /api/auth/refresh` → 400 «Missing refresh token» → `setAccessToken(null)` в catch → access-токен обнулялся → все API-запросы падали с 401 → toast «Не удалось сохранить настройку».

### Изменения:

**OnboardingWizard.vue:**
- Добавлен `catch` с toast-уведомлением в `next()` и `skip()`
- Импортирован `useToast` из PrimeVue

**TeamView.vue:**
- `loadRolePermissions`: `try/finally` → `try/catch/finally` с toast
- Импортирован `useToast`

**NotificationsView.vue:**
- `loadPrefs`, `loadTgStatus`, `handleLink`: `try/finally` → `try/catch/finally`
- Импортирован `useToast`

**IntegrationsView.vue:**
- `loadConnections`: `try/finally` → `try/catch/finally` с `errorMessage`

**DealsView.vue:**
- `loadPipelines`, `loadBoard`, `onDrop`, `openDeal`, `saveDealEdit`, `removeDeal`, `addNote`, `submitDeal` — обёрнуты в try/catch с toast
- Импортирован `useToast`

**ContactsView.vue:**
- `loadContacts`, `submitContact`, `removeContact` — обёрнуты в try/catch с toast
- Импортирован `useToast`

**DistributionView.vue:**
- `load`, `loadLog`, `submitRule`, `toggleActive`, `removeRule` — обёрнуты в try/catch с toast
- Импортирован `useToast`

**ChannelsView.vue:**
- Удалён дублирующий `ws.onclose` (строки 454-457) — восстанавливает реконнект WebSocket
- `loadChannels`, `submitChannel`, `toggleActive`, `removeChannel`, `registerWebhook` — try/catch с toast
- Импортирован `useToast`

**App.vue:**
- Добавлен `<PToast position="top-right" />` — ранее был зарегистрирован, но не в DOM

**stores/tenant.ts:**
- Добавлен getter `planLoaded: (state) => Boolean(state.plan)`
- `hasFeature` явно проверяет `state.plan !== null` и `state.plan.features !== undefined`

**DashboardView.vue:**
- Все `hasFeature`-зависимые `computed` защищены `planReady.value`

**AppMenu.vue (layout):**
- `withLock()` не блокирует пункты до загрузки плана (`planReady`)

**vite.config.ts:**
- Добавлен `appType: 'spa'` для SPA fallback (Vite dev-сервер)

**apps/users/api.py (backend):**
- `_set_refresh_cookie()`: `samesite='Lax'` → `samesite='None'` — кросс-ориджин POST не отправляли cookie

**frontend/src/api/auth.ts:**
- `refresh()`: catch больше не вызывает `setAccessToken(null)` — не сбрасывает валидный токен при ошибке рефреша

**frontend/src/api/http.ts:**
- `refreshAccessToken()`: catch больше не вызывает `setAccessToken(null)` — аналогично

### Файлы (21 файл изменено):
- `frontend/src/App.vue`, `frontend/vite.config.ts`
- `frontend/src/api/auth.ts`, `frontend/src/api/http.ts`
- `frontend/src/stores/tenant.ts`
- `frontend/src/layout/AppMenu.vue`
- `frontend/src/components/OnboardingWizard.vue`
- `frontend/src/views/TeamView.vue`, `NotificationsView.vue`, `IntegrationsView.vue`
- `frontend/src/views/DealsView.vue`, `ContactsView.vue`, `DistributionView.vue`, `ChannelsView.vue`
- `frontend/src/views/DashboardView.vue`
- `apps/users/api.py`

### Валидация:
- `docker compose down` ✅
- `docker compose up -d --build` ✅
- `docker compose run --rm web python manage.py check` → `0 issues` ✅
- Frontend build: `686 modules, 3.74s` ✅
- Frontend tests: `5/5 passed` ✅
- Все 19 SPA-маршрутов → `200 OK` ✅
- Backend health: `GET /healthz` → `200` ✅

### Известная регрессия тестов:
- 5 backend-тестов (`test_auth_api`, `test_invites_api`, `test_tenant_resolver`) падают с `relation "ai_assistant_aiconversation" does not exist` — вызвано добавлением `apps.ai_assistant` в `TENANT_APPS` в конфиге при незакоммиченной миграции. Пре-экзистинг, не вызвано изменениями данного PR. Вынесено в KNOWN_ISSUES #5.

### Риски:
- Vite dev-сервер возвращает 500 на `GET /app` (EISDIR), т.к. рабочая директория совпадает с SPA-маршрутом. Production nginx обрабатывает корректно. Дочерние маршруты (`/app/dashboard` и т.д.) работают без ошибок.

## 2026-05-09 — AI Assistant: Hermes + OpenCode.ai integration

### Что сделано:
- Исправлена ошибка в `models.py`: `channels.ChatSession` → `messenger_channels.ChatSession` (правильный Django app label)
- Созданы и применены миграции `0001_initial.py` для AIConversation/AIMessage
- Написаны тесты в `apps/ai_assistant/tests/test_ai_assistant.py` — 14 тестов (models, services, Hermes integration)
- Обновлена документация: AI_CONTEXT.md, DECISIONS.md (DEC-XXX), DEV_LOG

### Компоненты:
- `apps/ai_assistant/models.py`: AIConversation, AIMessage (tenant-scoped)
- `apps/ai_assistant/api.py`: POST /api/ai/chat/, GET /api/ai/conversations/, etc.
- `apps/ai_assistant/services.py`: send_to_hermes(), build_context_for_hermes()
- `apps/ai_assistant/consumers.py`: AIAssistantConsumer (WebSocket)
- `apps/ai_assistant/hermes_skills/`: crm_get_deal.py, crm_create_task.py
- `apps/ai_assistant/public_views.py`: hermes_webhook endpoint
- Frontend: stores/ai.ts, views/AssistantView.vue, api/ai.ts, router, AppMenu, ChannelsView

### Валидация:
- `python manage.py check` → 0 issues
- `python manage.py test apps.ai_assistant` → 14 tests OK
- `docker compose run frontend npm run build` → built in 26.53s

### Блокировка:
- Hermes registry `ghcr.io/nousresearch/hermes-agent:latest` недоступен (denied) — end-to-end тест，暂时无法进行

## 2026-04-29 — Redesign PR1: дизайн-система + тёмная тема с persist

### Изменения:
- `frontend/src/main.ts`: добавлен `ProjectPreset` через `definePreset(Aura, ...)` — primary palette смаппена на indigo (50…950), для `colorScheme.light` и `dark` заданы semantic токены `primary`/`highlight`/`surface`; `darkModeSelector: '.app-dark'`, `cssLayer: false`. Перед `app.mount` вызывается `useUiStore(pinia).initTheme()` чтобы не было flash-of-light при загрузке.
- `frontend/src/styles/main.css`: переписаны корневые токены под спецификацию `redesign/` — `--primary*`, `--surface-*`, `--text-color*`, статусные палитры `--green/red/orange/blue/violet/cyan/yellow` (50/500), `--radius-sm/md/lg`, `--shadow-sm/md/lg`, `--sidebar-width: 16rem`, `--topbar-height: 4rem`, `--font-family: 'Nunito Sans'`. Блок `:root.app-dark` явно переопределяет `--surface-*`/`--text-color*`/teneous shadows. Удалены устаревшие алиасы на `--p-*` там, где есть прямые значения.
- `frontend/index.html`: подключён Google Fonts Nunito Sans (preconnect + display=swap), вес 400/500/600/700/800.
- `frontend/src/stores/ui.ts`: добавлены `initTheme()` (читает `localStorage['crm.theme']`, fallback на `prefers-color-scheme`), `setTheme(mode)` (persist + apply class), `toggleTheme()`. Флаг `themeInitialized` защищает от повторной инициализации.
- `frontend/src/layout/composables/layout.ts`: убрано локальное `layoutConfig.darkTheme`; `toggleDarkMode` и `isDarkTheme` делегируются в `useUiStore` — единый источник истины.

### Валидация:
- `docker compose exec frontend npm run build` → ✓ 682 modules, 3.62s, без ошибок
- `docker compose exec frontend npm run typecheck` → ошибки только pre-existing (KNOWN_ISSUES #4): `undici`, vite/vitest mismatch, http.ts, CRMView.vue, TelephonyView.vue, auth.ts. В изменённых файлах ошибок нет.
- `curl http://localhost:15173/` → 200, в HTML присутствует Nunito Sans link
- HMR-обновление `main.css`/`AppTopbar.vue`/`AppSidebar.vue`/`AppLayout.vue` отрабатывает без ошибок в логах frontend контейнера

### Риски:
- Визуальная проверка в браузере (light/dark, переключение, перезагрузка с сохранением темы) — за пользователем; требуется хотя бы один заход в SPA для подтверждения, что тёмные `--surface-*` не конфликтуют с фоновыми стилями отдельных views.
- В легаси `frontend/src/layouts/TopBar.vue` остался ссылающийся на `ui.darkMode`/`ui.toggleTheme` код, но он не подключён маршрутами (`AppLayout` использует новый `layout/AppTopbar.vue`). Не трогаю в этом PR.

## 2026-04-20 — Frontend: официальный Sakai layout (PrimeVue)

### Изменения:
- `frontend/src/layout/composables/layout.ts` (новый): `useLayout()` composable — меню toggle, dark mode (.app-dark), static/overlay режимы
- `frontend/src/layout/AppTopbar.vue` (новый): fixed topbar по Sakai — hamburger, лого, org-switcher, NotificationBell, dark mode, logout
- `frontend/src/layout/AppSidebar.vue` (новый): fixed sidebar по Sakai — outside-click detection, route watcher
- `frontend/src/layout/AppMenu.vue` (новый): nav items с feature-lock, RouterLink active classes, user footer
- `frontend/src/layouts/AppLayout.vue`: переписан — импортирует новые layout-компоненты, containerClass по layoutState
- `frontend/src/styles/main.css`: переписан под официальный Sakai CSS — fixed topbar (4rem), fixed sidebar (20rem), padding-left 22rem на main
- `frontend/src/main.ts`: darkModeSelector изменён с `.theme-dark` на `.app-dark`
- `frontend/src/stores/ui.ts`: toggleTheme использует `.app-dark` вместо `.theme-dark`

### Валидация:
- `npm run build` → ✓ 680 modules, без ошибок
- `npm run typecheck` → ошибки только в pre-existing файлах (CRMView, TelephonyView, api/http)
- `docker compose up -d --build` → все контейнеры запущены

### Риски:
- Визуальная проверка в браузере требуется (fixed layout принципиально отличается от flex layout)

## 2026-04-18 — Телефония: полная интеграция FreeSWITCH (dialplan XML, directory, CDR hook)

### Изменения:
- `apps/telephony/services.py`: `dialplan()` теперь возвращает настоящий FreeSWITCH XML (`freeswitch/xml` document); добавлены `build_dialplan_xml()`, `_ivr_extensions()` (inline multi-extension с `play_and_get_digits`), `build_directory_xml()`; `resolve_tenant_for_telephony` нормализует FS-поля (`variable_tenant_slug`, `Caller-Destination-Number` и т.д.)
- `apps/telephony/public_views.py`: `dialplan` и `directory` — IP-only авторизация (mod_xml_curl не шлёт токен); `events` — token+IP; добавлен endpoint `directory`
- `config/urls.py`: добавлен маршрут `POST /telephony/directory/`
- `apps/telephony/tasks.py`: `_write_trunk_config` включает `<variables><variable name="tenant_slug" .../>` в gateway XML — FS передаёт slug на каждый входящий канал
- `freeswitch/xml_curl.conf.xml`: конфиг `mod_xml_curl` — биндинги dialplan + directory на Django
- `freeswitch/scripts/cdr_hook.lua`: Lua-хук CDR → `POST /telephony/events/` при завершении звонка
- `docker-compose.yml`: bind-mount `xml_curl.conf.xml`, `cdr_hook.lua` и `./media/telephony` в freeswitch контейнер
- `apps/telephony/tests/test_public_endpoints.py`: 10 тестов (было 3) — XML-структура, directory credentials, tenant_slug, нормализация FS-полей, reject без токена

### Валидация:
- `python manage.py check` → 0 issues
- `python manage.py test apps.telephony` → 10/10 OK

### Риски:
- CDR hook (`cdr_hook.lua`) требует `luasocket` в контейнере FS (есть в signalwire/freeswitch-public-base)
- Для активации CDR hook нужно добавить в `lua.conf.xml`: `<hook event="CHANNEL_HANGUP_COMPLETE" script="cdr_hook.lua"/>`

## 2026-04-18 — Телефония: чеклист И (42–51)

### Изменения:
- `apps/telephony/api.py`: `list_calls` принимает query-параметры `result`, `direction`, `date_from`, `date_to`; в ответ добавлено поле `record_file`
- `frontend/src/api/telephony.ts`: добавлен интерфейс `CallFilters`, `listCalls` принимает фильтры и собирает query string
- `frontend/src/views/TelephonyView.vue`: фильтр-бар (направление/результат/дата), HTML5-аудиоплеер + скачивание записей, click-to-call диалог; IVR-конструктор переработан: правила digit→action с выбором типа (очередь/номер/IVR/завершить) через select

### Валидация:
- `docker compose run --rm web python manage.py check` → 0 issues
- `docker compose run --rm web python manage.py test apps.telephony` → 3/3 OK
- Vite HMR: `TelephonyView.vue` подхвачен без ошибок

### Риски:
- Аудиоплеер реален, но воспроизведение зависит от наличия файла в `record_file` (заполняется FreeSWITCH CDR-хуком)

## 2026-04-18 — Дашборд KPI (В, 9–11) + Настройки организации (О, 65)

### Изменения:

**Backend:**
- `apps/notifications/presence.py` (новый) — Redis-based presence: `mark_online/mark_offline/list_online_user_ids`, TTL 90s, ключи `presence:{schema}:{user_id}`
- `apps/notifications/consumers.py` — при connect пишем presence + запускаем heartbeat-задачу asyncio (refresh каждые 45s), при disconnect — cancel + mark_offline; tenant_schema резолвится через Membership в public schema
- `apps/crm/dashboard_api.py` — новый endpoint `GET /dashboard/managers-online/` (feature: analytics): сканирует Redis ключи, пересекает с active joined Membership, возвращает `{online, total, user_ids}`
- `apps/tenants/api.py` — валидация `brand_color` (hex regex), `timezone` (zoneinfo), `language` (whitelist); endpoint `POST /tenant/logo` (multipart, max 2 MB, image/png|jpeg|svg+xml); `DELETE /tenant/logo`; `logo_url` в TenantOut
- `apps/core/middleware.py` — `translation.activate(tenant.language)` в EnsureTenantContextMiddleware

**Frontend:**
- `src/utils/datetime.ts` — `formatDateTime/formatDate/formatTime` через Intl.DateTimeFormat + tenant timezone/locale из Pinia
- `src/views/DashboardView.vue` — KPI «Менеджеры онлайн» (polling 30s), «Договоры», quick-actions, feature lock states
- `src/views/SettingsView.vue` — логотип (upload/preview/delete), timezone PSelect (Intl.supportedValuesOf), language, brand_color (color input + HEX)
- `src/layouts/SidebarNav.vue` — показ логотипа организации, fallback на инициалы, `.logo-mark` использует `var(--brand)`
- `src/api/http.ts` — Accept-Language header из tenant language в каждом запросе
- `src/stores/notifications.ts` — WS URL содержит `slug` query param
- Все дата-вызовы во вьюхах (CRM, Audit, Distribution, Telephony, Channels, Contracts, Integrations, Subscription) переведены на единый `formatDateTime/formatDate`

### Валидация:
- `manage.py check` → 0 issues
- 17 тестов: `apps.crm.tests.test_dashboard_api apps.tenants.tests.test_tenant_settings apps.notifications` → OK
- Vue typecheck: новых ошибок не добавлено

---

## 2026-04-18 — Аудит: логирование CRM-операций

### Корневая причина:
`log_event()` вызывался только при изменении ролей/прав. Создание/изменение/удаление сделок, контактов, компаний в аудит не писалось — журнал был пустым для любого рабочего тенанта.

### Изменения:
**`apps/crm/api.py`** — добавлены вызовы `log_event()`:
- `create_deal` / `patch_deal` (diff `{поле: {before, after}}`) / `move_deal` (стадия) / `delete_deal`
- `create_contact` / `patch_contact` (diff) / `delete_contact`
- `create_company` / `patch_company` (diff) / `delete_company`

### Валидация:
- `manage.py check` → 0 issues
- `manage.py test apps.audit apps.crm` → 13/13 OK
- Live: создание сделки + обновление + создание контакта → 3 новые записи в `/api/audit/events/` с корректными `model_name`, `object_repr`, `user_email`, `changes`

---

## 2026-04-18 — Чеклист Н: подписка, лимиты, feature-gating (62–64)

### Корневая причина:
Пункт Н формально оставался незавершённым: при `trial_expired` subscription flow мог упираться в 402, usage лимитов считался неканонично (дрейф API/фоновых проверок), а feature-gating для внешних CRM был неполным для операций над уже созданными подключениями.

### Изменения:
1. **Access/trial guard hardening** (`apps/core/access.py`)
   - `require_membership` и `require_roles` расширены флагом `allow_trial_expired`.
   - Для subscription/billing контура разрешён доступ при `trial_expired`, бизнес-endpoint-ы оставлены под 402-инвариантом.
2. **Единый usage сервис + pipelines usage** (`apps/billing/usage.py`, `apps/tenants/api.py`, `apps/billing/tasks.py`)
   - Введён `get_plan_usage_for_tenant(...)` как единый источник расчёта usage.
   - `managers` считаются по `Membership` (public schema): active + joined + без invite-token, роли `owner/admin/manager`.
   - В usage добавлен `pipelines`; `/tenant/plan/` гарантирует ключ `pipelines`.
   - Фоновая задача лимитов переиспользует тот же usage-сервис.
3. **Унификация DTO планов** (`apps/billing/catalog.py`, `apps/billing/api.py`, `apps/tenants/api.py`)
   - Добавлен общий serializer/queryset для active plans.
   - `/billing/plans/` и `/tenant/plans/` возвращают одну структуру (поля/сортировка/лимиты).
4. **Feature-gating API для existing connections** (`apps/integrations/api.py`)
   - Добавлена обязательная проверка доступности CRM-фичи (`crm_amocrm`/`crm_bitrix24`) для операций по существующим connection:
     update/delete, sync, health-check, test, reconnect, errors/managers/webhooks endpoints.
   - `list_connections` сохранён доступным для видимости существующих подключений.
5. **Frontend lock-state и единообразие поведения** (`frontend/src/views/IntegrationsView.vue`, `frontend/src/views/DashboardView.vue`, `frontend/src/views/SubscriptionView.vue`, `frontend/src/views/RegisterView.vue`, `frontend/src/stores/tenant.ts`, `frontend/src/types.ts`, `frontend/src/api/tenant.ts`)
   - Subscription/Register показывают полный набор лимитов: managers, contracts/month, crm_connections, pipelines.
   - Integrations: недоступные CRM-фичи блокируют install/actions (disabled + причина).
   - Dashboard: feature-зависимые KPI/быстрые действия показываются в lock-состоянии с пояснением.
   - Tenant plan/plan catalog типизированы единообразно.
6. **Тесты**
   - `apps/tenants/tests/test_subscription_hardening.py` (новый): trial-expired доступ к subscription/billing и 402 на бизнес-endpoint; корректный usage (managers/pipelines).
   - `apps/integrations/tests/test_feature_gating_api.py` (новый): 403 для операций с connection при отключённых `crm_amocrm`/`crm_bitrix24`.

### Файлы:
- `apps/core/access.py`
- `apps/billing/catalog.py` (новый)
- `apps/billing/usage.py` (новый)
- `apps/billing/api.py`
- `apps/billing/tasks.py`
- `apps/tenants/api.py`
- `apps/integrations/api.py`
- `apps/tenants/tests/test_subscription_hardening.py` (новый)
- `apps/integrations/tests/test_feature_gating_api.py` (новый)
- `frontend/src/types.ts`
- `frontend/src/stores/tenant.ts`
- `frontend/src/api/tenant.ts`
- `frontend/src/views/RegisterView.vue`
- `frontend/src/views/SubscriptionView.vue`
- `frontend/src/views/IntegrationsView.vue`
- `frontend/src/views/DashboardView.vue`
- `docs/CHECKLIST.md`
- `docs/TASK_STATE.md`
- `docs/DECISIONS.md`
- `docs/DEV_LOG.md`
- `docs/RELEASE_NOTES.md`

### Валидация (Docker):
1. `docker compose down` ✅
2. `docker compose up -d --build` ✅
3. `docker compose run --rm web python manage.py check` → `0 issues` ✅
4. Targeted backend tests:
   - `docker compose run --rm web python manage.py test apps.tenants.tests.test_subscription_hardening apps.integrations.tests.test_feature_gating_api apps.contracts.tests.test_contract_limits apps.integrations.tests.test_integrations_api --verbosity 2`
   - Результат: `Ran 8 tests ... OK` ✅
5. Frontend:
   - `docker compose run --rm frontend npm run test -- --run` → `5 passed` ✅
   - `docker compose run --rm frontend npm run build` ✅
6. Manual smoke:
   - `curl -I http://localhost:15173/app/subscription` → `200`
   - `curl -I http://localhost:15173/app/integrations` → `200`
   - `curl -I http://localhost:18100/healthz` → `200`
   - Django client smoke: `trial_expired` даёт `200` на subscription/billing и `402` на `/api/contracts/`; integration action при отключённой CRM feature даёт `403`.

### Риски:
- Для production остаётся зависимость от реальных external CRM/YooKassa credentials в e2e-валидации; функциональные guard/usage и локальные regression-тесты закрыты.

## 2026-04-18 — Чеклист М: аудит (59–61)

### Изменения:
1. **Backend** (`apps/audit/api.py`)
   - `AuditEventOut` дополнен полем `user_email` (resolve через `select_related('user')`)
   - `AuditListOut(total, items)` — новая обёртка для ответа списка
   - `list_events` принимает новые параметры: `user_id`, `date_from`, `date_to`; возвращает `total`
   - `export_events` принимает те же фильтры + использует `csv.writer` с полным набором колонок: `user_email`, `object_repr`, `ip_address`, `changes` (JSON)
   - Вспомогательные функции `_build_qs` и `_event_out` выделены для переиспользования

2. **Frontend** (`frontend/src/views/AuditView.vue` — полная перезапись)
   - Панель фильтров: Действие (PSelect), Пользователь (PSelect из `/api/users/`), Дата с/по (PInputText type=date)
   - Серверная пагинация (lazy PDataTable) с `total` из API
   - Клик по строке раскрывает/сворачивает AuditDiff
   - Кнопка «Экспорт CSV» — fetch+blob с текущими фильтрами

3. **Frontend** (`frontend/src/components/AuditDiff.vue` — полная перезапись)
   - Таблица «Поле / Было / Стало» когда `changes` имеет формат `{field: {before, after}}`
   - Fallback — JSON `<pre>` для остальных форматов (create/delete/нестандартные)

4. **Frontend** (`frontend/src/types.ts`)
   - Добавлены `AuditEvent`, `AuditListResponse`

### Файлы:
- `apps/audit/api.py`
- `frontend/src/views/AuditView.vue`
- `frontend/src/components/AuditDiff.vue`
- `frontend/src/types.ts`

### Валидация:
- `docker compose run --rm web python manage.py check` → 0 issues (0 silenced)
- `docker compose run --rm web python manage.py test apps.audit --verbosity=2` → 8/8 OK
- Ручная проверка `/app/audit` — таблица, фильтры, diff, экспорт CSV

---

## 2026-04-18 — Чеклист Л: уведомления (55–58)

### Корневая причина:
Раздел Л был помечен «done» в TASK_STATE, но чеклист показывал все пункты ⬜. Реально отсутствовали: Telegram bot webhook, UI настроек event×канал, UI привязки Telegram, async-доставка email.

### Изменения:
1. **Telegram bot webhook** (`apps/notifications/views.py` — новый)
   - `TelegramBotWebhookView` (CSRF-exempt, публичный POST)
   - Обрабатывает `/start bind_<token>` → верифицирует `TimestampSigner` (max_age=600) → создаёт `TelegramBinding`
   - Отвечает пользователю в чат подтверждением или сообщением об ошибке
2. **Telegram status endpoint** (`apps/notifications/api.py`)
   - `GET /notifications/telegram/status/` — возвращает `{linked, chat_id, username, bot_username}`
   - `telegram_link` теперь берёт `bot_username` из `settings.TELEGRAM_NOTIFICATION_BOT_USERNAME`, не из payload
3. **Async email** (`apps/notifications/services.py`)
   - `send_notification_email(...)` заменён на `send_notification_email_task.delay(...)` — email уходит через Celery
4. **Конфигурация** (`config/urls.py`, `config/settings.py`, `.env.example`)
   - Добавлен URL `/notifications/telegram/bot-webhook/`
   - Добавлена переменная `TELEGRAM_NOTIFICATION_BOT_USERNAME`
5. **Frontend API** (`frontend/src/api/notifications.ts`)
   - Добавлены: `listPreferences`, `updatePreferences`, `telegramStatus`, `linkTelegramInit`, `unlinkTelegram`
6. **NotificationsView.vue** — расширен двумя секциями:
   - Матрица event × канал (in_app/email/telegram) с `PToggleSwitch`, auto-save при изменении (owner/admin)
   - Карточка Telegram: статус привязки, кнопка «Привязать» (открывает t.me-ссылку + инструкция) / «Отвязать»

### Файлы:
- `apps/notifications/views.py` (новый)
- `apps/notifications/api.py`
- `apps/notifications/services.py`
- `config/urls.py`
- `config/settings.py`
- `.env.example`
- `frontend/src/api/notifications.ts`
- `frontend/src/views/NotificationsView.vue`
- `docs/TASK_STATE.md`
- `docs/DEV_LOG.md`

### Валидация:
- `docker compose run --rm web python manage.py check` → 0 issues (0 silenced)
- `curl POST /notifications/telegram/bot-webhook/` → HTTP 200
- `docker compose up -d --build web celery` → оба контейнера запустились без ошибок

### Риски:
- Telegram bot webhook требует регистрации через `setWebhook` при наличии реального `TELEGRAM_NOTIFICATION_BOT_TOKEN` и публичного домена.
- Ссылка на бота не генерируется пока `TELEGRAM_NOTIFICATION_BOT_USERNAME` не задан в `.env`.

## 2026-04-18 — Раздел «Помощь»: пользовательская документация в личном кабинете

### Корневая причина:
В личном кабинете не было встроенной пользовательской справки. Инструкции по работе с CRM, договорами, интеграциями и т.д. существовали только как внешние материалы, что увеличивало нагрузку на поддержку и затрудняло онбординг.

### Изменения:
1. **Документация (18 статей, русский, без технических деталей)**
   - Создан каталог `docs/user-guide/` с файлами `01-login.md` … `18-subscription.md` + `README.md` (оглавление).
   - Единый формат каждой статьи: назначение → где открыть → поля → пошагово → типичные ситуации → если не получается.
   - Запрещены имена функций/моделей/URL/route-имён/codename прав — только реальные подписи кнопок.
2. **Фронтенд: раздел «Помощь»**
   - `frontend/src/utils/markdown.ts` — свой markdown-рендер (≈50 строк, без npm-зависимостей): заголовки h1–h6 с slug-id (поддержка кириллицы через `\p{L}\p{N}`), списки, параграфы, inline-код, **bold**, *italic*, ссылки (внешние в новом окне), `<hr />`.
   - `frontend/src/views/HelpView.vue` — страница с 3 колонками: левая (поиск + список статей), центр (рендер md), правая (TOC по h2/h3 со smooth scroll). Статьи подгружаются через `import.meta.glob('@/docs/user-guide/*.md', { query: '?raw', import: 'default', eager: true })`. Активная статья синхронизируется в URL как `?article=<slug>`. Адаптив: TOC скрывается ниже 1100px, колонки складываются ниже 720px.
   - `frontend/src/router/index.ts` — добавлен маршрут `app/help` (роли owner/admin/manager/viewer) и redirect `/help → /app/help`.
   - `frontend/src/layouts/SidebarNav.vue` — пункт меню «Помощь» (icon `pi pi-question-circle`, без feature-gate).
3. **Единый источник правды**
   - Симлинк `frontend/src/docs/user-guide` → `../../../docs/user-guide`. Статьи лежат в одном месте и не дублируются между репо-доками и SPA-сборкой.

### Файлы:
- `docs/user-guide/README.md`
- `docs/user-guide/01-login.md` … `docs/user-guide/18-subscription.md` (18 файлов)
- `frontend/src/utils/markdown.ts`
- `frontend/src/views/HelpView.vue`
- `frontend/src/router/index.ts`
- `frontend/src/layouts/SidebarNav.vue`
- `frontend/src/docs/user-guide` (symlink)
- `docs/TASK_STATE.md`
- `docs/DECISIONS.md`
- `docs/RELEASE_NOTES.md`
- `docs/DEV_LOG.md`

### Валидация:
- `npm run typecheck` (в запущенном frontend-контейнере): ошибки только в pre-existing файлах (`CRMView.vue`, `SubscriptionView.vue`, `useSIPPhone.ts`, `http.ts`, `node_modules`) — соответствует KNOWN_ISSUES #4. Файлы этого изменения чисты.
- `GET http://localhost:15173/app/help` → `200 OK`.
- `docker compose run --rm web python manage.py check` → `0 issues (0 silenced)`.

### Риски:
- Свой md-рендер намеренно ограничен (нет таблиц, code-блоков ```, blockquote). Если статьи будут использовать эти элементы — расширить `utils/markdown.ts`.
- Известная нестабильность typecheck фронта (KNOWN_ISSUES #4) не устраняется этим PR.

## 2026-04-16 — Этап Ж закрыт: marketplace-first интеграции amoCRM/Битрикс24 + статусный UX

### Корневая причина:
Раздел интеграций был технически минимальным: базовый CRUD/OAuth без дружелюбного user flow, без one-click marketplace установки, без человекочитаемого error log, без единой проверки состояния интеграции и с дефектной синхронизацией менеджеров (`ManagerProfile` не создавался корректно без `user`).

### Изменения:
1. **Backend: status/scopes/reconnect/error-log**
   - Добавлены поля в `CRMConnection` (`integration_mode`, `last_health_check_at`, `last_webhook_at`) и `WebhookEndpoint.last_received_at`.
   - Добавлена модель `IntegrationErrorLog` + admin.
   - Новый сервисный слой `apps/integrations/services.py`:
     - вычисление статуса интеграции (`working / requires_authorization / webhook_error / insufficient_scope / error / disabled`);
     - scope-валидация (`required_scopes` vs `granted_scopes`);
     - авто-refresh OAuth токенов (amoCRM/Bitrix24) и reconnect helper;
     - человеческое логирование ошибок с рекомендациями.
2. **Backend API: marketplace + test/reconnect + autoconfig**
   - `apps/integrations/api.py` полностью расширен:
     - `POST /integrations/marketplace/{crm_type}/install/` (one-click start);
     - `POST /integrations/connections/{id}/test/` (connection + webhook probe);
     - `POST /integrations/connections/{id}/reconnect/`;
     - `GET /integrations/connections/{id}/errors/`;
     - расширенные данные в `GET /integrations/connections/` (статусы, scopes, health/webhook timestamps, mode, error log count).
   - OAuth callback теперь выполняет автонастройку: default webhook + `sync_crm_users.delay(...)` + `check_crm_connections_health.delay()`.
3. **Webhook + manager sync hardening**
   - `apps/integrations/webhook_views.py`: логирование auth-failures в `IntegrationErrorLog`, фиксация `last_received_at`/`last_webhook_at` на успешных событиях.
   - `apps/integrations/tasks.py`:
     - `sync_crm_users` исправлен: создаёт/связывает `User` + `Membership` для менеджеров CRM и деактивирует отсутствующих;
     - health-check учитывает новый статусный контур и user-facing логирование.
4. **Frontend UX интеграций**
   - Новый typed API: `frontend/src/api/integrations.ts`.
   - `frontend/src/types.ts` дополнен типами интеграций/статусов/error-log.
   - `frontend/src/views/IntegrationsView.vue` переработан:
     - двухконтурный setup: marketplace (recommended) vs webhook (quick start);
     - статусы интеграций, scope-индикаторы, last sync/health/webhook;
     - действия: test, sync managers, reconnect, просмотр журнала ошибок.
5. **Тесты (в т.ч. e2e сценарий этапа Ж)**
   - Новый файл: `apps/integrations/tests/test_integrations_api.py`.
   - Покрыты сценарии:
     - marketplace start + tenant binding;
     - callback autoconfig + приём webhook;
     - статус `insufficient_scope` и наличие user-facing error log.

### Файлы:
- `apps/integrations/models.py`
- `apps/integrations/admin.py`
- `apps/integrations/migrations/0003_connection_health_status_errorlog.py`
- `apps/integrations/services.py`
- `apps/integrations/api.py`
- `apps/integrations/tasks.py`
- `apps/integrations/webhook_views.py`
- `apps/integrations/tests/test_integrations_api.py`
- `frontend/src/api/integrations.ts`
- `frontend/src/types.ts`
- `frontend/src/views/IntegrationsView.vue`
- `docs/CHECKLIST.md`
- `docs/TASK_STATE.md`
- `docs/DECISIONS.md`
- `docs/KNOWN_ISSUES.md`
- `docs/DEV_LOG.md`
- `docs/RELEASE_NOTES.md`

### Верификация (Docker):
1. `docker compose down` ✅
2. `DEBUG=False docker compose up -d --build` ✅
3. `DEBUG=False docker compose run --rm web python manage.py check` → `0 issues` ✅
4. Targeted backend tests:
   - `DEBUG=False docker compose run --rm web python manage.py test apps.integrations.tests.test_integrations_api apps.integrations.tests.test_webhook_auth --verbosity 2`
   - Результат: `Ran 8 tests ... OK` ✅
5. Frontend:
   - `docker compose run --rm frontend npm run test -- --run` → `5 tests passed` ✅
   - `docker compose run --rm frontend npm run build` → build успешен ✅
6. Manual HTTP smoke (внутри web-контейнера через Django test client):
   - register owner + tenant → `201`;
   - marketplace start amoCRM → `200`, `authorize_url` присутствует;
   - OAuth callback → `200`;
   - `POST /integrations/connections/{id}/test/` → `200`;
   - `GET /integrations/connections/{id}/errors/` → `200`.

## 2026-04-16 — План этапа Ж расширен: marketplace-first UX для amoCRM/Bitrix24

### Контекст:
При переходе к этапу `Ж` согласован двухконтурный подход интеграций: не только webhook-подключение, но и «дружелюбная» установка приложений из маркетплейсов amoCRM/Bitrix24.

### Изменения:
1. **`docs/CHECKLIST.md`**
   - В секцию `Ж` добавлены пункты `85–94`:
     - one-click install для amoCRM/Bitrix24;
     - двухконтурный onboarding (webhook vs app-install);
     - автонастройка после установки приложения;
     - test connection/test webhook;
     - пользовательский журнал ошибок;
     - reconnect/token self-heal;
     - статусы интеграции и e2e-критерии.
2. **`docs/TASK_STATE.md`**
   - Добавлена текущая задача `#13` со статусом `in-progress`:
     - «Этап Ж: внешние CRM (webhook + marketplace UX)».

### Файлы:
- `docs/CHECKLIST.md`
- `docs/TASK_STATE.md`
- `docs/DEV_LOG.md`

---

## 2026-04-16 — RBAC для CRM (чеклист Р: 74-84)

### Корневая причина:
Права доступа в CRM были жёстко закодированы по ролям (`require_roles`) и не поддерживали:
1. granular CRUD-права по сущностям `deals/contacts/companies`;
2. область видимости данных `all/team/own`;
3. управление матрицей прав из UI.

### Изменения:
1. **Модель прав и дефолтная матрица**
   - Добавлена модель `users.RolePermission` (public schema): `tenant + role + entity + can_view/create/update/delete + scope`.
   - Добавлен модуль `apps/users/permissions.py`:
     - дефолты для `owner/admin/manager/viewer`;
     - ленивое автодосоздание матрицы прав для tenant-а;
     - обновление прав с валидацией инвариантов.
2. **Enforcement backend**
   - `apps/core/access.py`: добавлены helper-ы `require_crm_permission`, `filter_crm_queryset_by_scope`, `ensure_crm_object_scope`, `normalize_crm_responsible_for_write`.
   - `apps/crm/api.py`:
     - CRUD/read для `deals/contacts/companies` переведены на granular permissions;
     - scope-aware фильтрация для списков/kanban/stats;
     - object-level guard для `get/patch/delete`;
     - `responsible_id` при `scope=own` автоматически нормализуется на текущего пользователя при create;
     - `pipelines/stages` read открыты через право `deals.view` (read-only сценарий viewer).
3. **API управления правами + аудит**
   - `apps/users/api.py`:
     - `GET /api/users/role-permissions/`;
     - `PATCH /api/users/role-permissions/{role}/{entity}/`;
     - `GET /api/auth/me` расширен полем `crm_permissions`;
     - аудит изменения роли участника и матрицы прав (`AuditEvent` через `log_event`).
4. **Frontend**
   - `frontend/src/views/TeamView.vue`: новая вкладка «Права ролей» с матрицей (CRUD + scope) и сохранением в API.
   - `frontend/src/views/CRMView.vue`: скрытие/disable create/edit/delete действий и загрузок по текущим permission-ам.
   - `frontend/src/types.ts`: добавлены типы CRM permissions.
   - `frontend/src/router/index.ts`: маршрут CRM доступен `viewer` (read-only при соответствующих правах).
   - `frontend/src/utils/crmPermissions.ts` + тест нормализации/инвариантов.

### Файлы:
- `apps/users/models.py`
- `apps/users/migrations/0002_rolepermission.py`
- `apps/users/permissions.py`
- `apps/users/admin.py`
- `apps/users/api.py`
- `apps/core/access.py`
- `apps/crm/api.py`
- `apps/users/tests/test_role_permissions_api.py`
- `apps/crm/tests/test_permissions_api.py`
- `frontend/src/views/TeamView.vue`
- `frontend/src/views/CRMView.vue`
- `frontend/src/types.ts`
- `frontend/src/router/index.ts`
- `frontend/src/utils/crmPermissions.ts`
- `frontend/src/utils/crmPermissions.test.ts`
- `docs/CHECKLIST.md`
- `docs/TASK_STATE.md`
- `docs/DECISIONS.md`
- `docs/DEV_LOG.md`
- `docs/RELEASE_NOTES.md`

### Верификация (Docker):
1. `docker compose down` ✅
2. `DEBUG=False docker compose up -d --build` ✅
3. `DEBUG=False docker compose run --rm web python manage.py check` → `System check identified no issues (0 silenced)` ✅
4. Targeted tests:
   - `DEBUG=False docker compose run --rm web python manage.py test apps.users.tests.test_role_permissions_api apps.crm.tests.test_permissions_api apps.users.tests.test_auth_api apps.users.tests.test_invites_api --verbosity 2`
   - Результат: `Ran 17 tests ... OK` ✅
   - `docker compose run --rm frontend npm run test -- --run`
   - Результат: `2 files, 5 tests passed` ✅
   - `docker compose run --rm frontend npm run typecheck`
   - Результат: ❌ (pre-existing TS issues в проекте, вынесено в `KNOWN_ISSUES.md`)
   - `docker compose run --rm frontend npm run build`
   - Результат: ✅ production build успешен
5. Manual HTTP smoke (localhost:18100):
   - `GET /api/auth/me` возвращает `crm_permissions` ✅
   - `GET /api/users/role-permissions/` → HTTP 200 ✅
   - `PATCH /api/users/role-permissions/manager/deals/` (`scope=own`) → HTTP 200 ✅
   - после invite+accept у manager `crm_permissions.deals.scope=own` ✅

---

## 2026-04-16 — Hotfix: приглашения в онбординге и принятие инвайта после онбординга

### Корневая причина:
1. Шаг 3 онбординга (“Менеджеры”) не создавал membership-приглашение в организацию — только `User` и `ManagerProfile`, поэтому инвайт-флоу фактически не стартовал.
2. Часть legacy-пользователей имела `password=''` (пустая строка), и invite-страница ошибочно считала их “существующим аккаунтом”, требуя старый пароль, которого не было.

### Изменения:
1. **`apps/tenants/onboarding_api.py`**
   - `_apply_managers_step()` теперь принимает tenant и для каждого email:
     - создаёт пользователя через `create_user(..., password=None)` (unusable password) при отсутствии;
     - создаёт/обновляет pending `Membership` (`role=manager`, `invite_token`, `invited_at`, `joined_at=None`);
     - отправляет email с invite-ссылкой;
     - оставляет создание `ManagerProfile`.
2. **`apps/users/api.py`**
   - Добавлен helper `_user_has_login_password()` для корректной проверки “есть ли у пользователя реальный пароль для входа”.
   - `check_invite` и `accept_invite` теперь учитывают legacy случай `password=''` как “новый аккаунт” (установка нового пароля), а не как “существующий аккаунт”.
3. **Тесты**
   - Новый тест: `apps/tenants/tests/test_onboarding_invites.py` (онбординг шаг 3 создаёт pending invite membership + `has_account=False`).
   - Расширен `apps/users/tests/test_invites_api.py`: кейс legacy пользователя с пустым паролем.

### Файлы:
- `apps/tenants/onboarding_api.py`
- `apps/users/api.py`
- `apps/tenants/tests/test_onboarding_invites.py`
- `apps/users/tests/test_invites_api.py`
- `docs/DECISIONS.md`
- `docs/TASK_STATE.md`
- `docs/RELEASE_NOTES.md`

### Верификация (Docker):
1. `docker compose down` ✅
2. `DEBUG=False docker compose up -d --build` ✅
3. `DEBUG=False docker compose run --rm web python manage.py check` → `0 issues` ✅
4. Targeted tests:
   - `DEBUG=False docker compose run --rm web python manage.py test apps.tenants.tests.test_onboarding_invites apps.users.tests.test_invites_api --verbosity 2`
   - `Ran 7 tests ... OK` ✅
5. Manual HTTP smoke:
   - onboarding step 3 создаёт invite-ссылку для менеджера ✅
   - `/auth/invite/check` возвращает `has_account=false` ✅
   - `/auth/invite/accept` успешно завершает вступление в организацию ✅

---

## 2026-04-16 — Этап К: доведение приглашений и multi-org tenant switch до production-ready

### Корневая причина:
Этап K был реализован частично, но не закрывал критичные сценарии эксплуатации:
- у пользователя не было стандартного API/UI способа переключаться между организациями;
- pending-приглашения могли участвовать в выборе `tenant_slug` при логине;
- принятие приглашения для существующего аккаунта не требовало подтверждения владения аккаунтом;
- часть tenant endpoint-ов не требовала явного membership.

### Изменения:
1. **Membership guard и tenant adherence**
   - `apps/core/access.py`: добавлен `require_membership()`; `require_roles()` переведён на него.
   - `apps/tenants/api.py`: `GET /tenant/`, `PATCH /tenant/settings`, `GET /tenant/plan/`, `GET /tenant/plans/` теперь требуют активное membership.
   - `apps/notifications/api.py`: read/list/telegram endpoints теперь требуют активное membership.
2. **Multi-org API**
   - `apps/users/api.py`:
     - новый `GET /api/auth/organizations` — список доступных организаций пользователя;
     - новый `POST /api/auth/switch-tenant` — безопасное переключение активной организации;
     - `_default_tenant_slug_for_user()` теперь выбирает только active joined membership (`invite_token IS NULL` и `joined_at IS NOT NULL`).
3. **Приглашения: безопасность и устойчивость**
   - `apps/users/api.py`:
     - принятие приглашения для существующего аккаунта требует пароль;
     - для нового аккаунта добавлена проверка уникальности username;
     - invite flow нормализует email/роль, корректно ре-активирует старое membership, обновляет token/timestamp;
     - генерация username для placeholder-пользователя теперь детерминированно избегает коллизий.
4. **Frontend multi-org UX**
   - `frontend/src/api/auth.ts`, `frontend/src/stores/auth.ts`: добавлена загрузка списка организаций и action переключения.
   - `frontend/src/layouts/TopBar.vue`: добавлен селектор организации.
   - `frontend/src/views/AcceptInviteView.vue`: для существующего аккаунта добавлено подтверждение пароля при принятии приглашения.
5. **Тесты**
   - `apps/users/tests/test_invites_api.py`: новые тесты на:
     - invite + accept нового пользователя;
     - invite + accept существующего пользователя (в т.ч. обязательность пароля);
     - organizations/switch-tenant;
     - игнорирование pending invite при выборе default tenant;
     - запрет switch-tenant без membership.

### Файлы:
- `apps/core/access.py`
- `apps/tenants/api.py`
- `apps/notifications/api.py`
- `apps/users/api.py`
- `apps/users/tests/test_invites_api.py`
- `frontend/src/types.ts`
- `frontend/src/api/auth.ts`
- `frontend/src/stores/auth.ts`
- `frontend/src/layouts/TopBar.vue`
- `frontend/src/views/AcceptInviteView.vue`
- `docs/CHECKLIST.md`
- `docs/TASK_STATE.md`
- `docs/DECISIONS.md`
- `docs/KNOWN_ISSUES.md`
- `docs/RELEASE_NOTES.md`

### Верификация (Docker):
1. `docker compose down` ✅
2. `DEBUG=False docker compose up -d --build` ✅
3. `DEBUG=False docker compose run --rm web python manage.py check` → `System check identified no issues (0 silenced)` ✅
4. Targeted backend tests:
   - `DEBUG=False docker compose run --rm web python manage.py test apps.users.tests.test_auth_api apps.users.tests.test_invites_api apps.tenants.tests.test_tenant_resolver apps.notifications.tests.test_preferences_permissions --verbosity 2`
   - Результат: `Ran 19 tests ... OK` ✅
5. Frontend tests:
   - `DEBUG=False docker compose run --rm frontend npm run test -- --run`
   - Результат: `1 passed, 2 tests passed` ✅
6. Manual HTTP smoke (localhost:18100):
   - invite нового пользователя + accept → access token получен;
   - invite существующего пользователя без пароля → ожидаемая ошибка;
   - invite существующего пользователя с паролем → tenant принят;
   - `/auth/organizations` возвращает обе организации;
   - `/auth/switch-tenant` успешно переключает tenant slug.

---

## 2026-04-15 — Полный E2E флоу приглашения пользователей (чеклист К)

### Корневая причина:
Приглашение работало только частично — email уходил в console backend, администратор не мог скопировать ссылку, не было индикации статуса (ожидает/активен), отсутствовали кнопки пересылки/отмены приглашения.

### Изменения:
1. **`apps/users/api.py`**: `invite_user` теперь возвращает `invite_link` в ответе. `list_users` возвращает `status` (pending/active) и `invite_link` для ожидающих. Добавлен `POST /{user_id}/resend-invite` — обновляет токен+timestamp, пересылает email, возвращает новую ссылку. `deactivate_user` для pending-приглашений удаляет membership целиком.
2. **`frontend/src/views/TeamView.vue`**: После приглашения отображается копируемая ссылка. Таблица участников: колонка «Статус» (PTag warning/success), для pending — кнопки «Скопировать ссылку», «Переслать», «Отменить»; для активных — роль через PSelect + деактивация.

### Файлы:
- `apps/users/api.py` — invite_link return, status, resend, pending delete
- `frontend/src/views/TeamView.vue` — invite link display, status column, action buttons

### Верификация:
- `manage.py check`: 0 issues ✅
- users 5/5 + tenants 11/11 = 16/16 tests ✅
- AcceptInviteView.vue — уже реализован: проверка токена, регистрация + приём приглашения
- Полный флоу: invite → link visible → copy → open /invite/accept → form → join org

---

## 2026-04-15 — Секция К: Команда и менеджеры — чеклист 52-54

### Корневая причина:
Пункты 52 (список участников) и 53 (приглашение) были уже реализованы. Пункт 54 (менеджеры: профили, расписание, выходные) — модели существовали (ManagerProfile.schedule, ManagerDayOff), но не было API для управления и UI.

### Изменения:
1. **`apps/users/api.py`**: Добавлены эндпоинты: `GET /users/managers/` (список профилей с schedule + days_off), `PATCH /users/managers/{id}/` (обновление schedule/max_active_deals), `POST /users/managers/{id}/days-off/` (добавить выходной), `DELETE /users/managers/days-off/{id}/` (удалить).
2. **`frontend/src/views/TeamView.vue`**: Полная переработка — 2 вкладки: «Участники» (список + invite + inline-роль + деактивация) и «Менеджеры» (таблица + PDialog с редактированием: рабочие дни кнопками, время, макс. сделок, управление выходными).

### Файлы:
- `apps/users/api.py` — manager profiles + day-offs CRUD
- `frontend/src/views/TeamView.vue` — tabs, manager schedule UI, day-off management

### Верификация:
- `manage.py check`: 0 issues ✅
- tenants 11/11 + users 5/5 + distribution 2/2 = 18/18 tests ✅
- Чеклист К (52-54) ✅

---

## 2026-04-15 — MAX: полноценная интеграция через Bot API (platform-api.max.ru)

### Корневая причина:
MAX-канал был реализован как заглушка — единственным полем в credentials было `send_url`, без реальных вызовов API. MAX Bot API предоставляет полноценный набор эндпоинтов для webhook-подписки, отправки сообщений и верификации.

### Изменения:
1. **`providers.py`**: Добавлены `register_max_webhook()` (`POST /subscriptions`), `unregister_max_webhook()` (`DELETE /subscriptions`), `get_max_webhook_info()` (`GET /subscriptions`). `send_outgoing` для MAX использует `POST /messages?chat_id=` с `Authorization: <token>`. `normalize_incoming_payload` обрабатывает MAX Update формат (`message_created` → `message.sender`, `message.body.text`, `recipient.chat_id`).
2. **`api.py`**: `_try_register_max()` аналогично `_try_register_telegram()`. `create_channel`/`patch_channel`/`delete_channel` обрабатывают MAX. `register-webhook`/`webhook-info` поддерживают MAX.
3. **`public_views.py`**: `_validate_webhook_token()` проверяет `X-Max-Bot-Api-Secret` (стандартный заголовок MAX webhook).
4. **Frontend**: Форма MAX теперь содержит поле `bot_token` (вместо `send_url`). Кнопка регистрации webhook доступна для MAX.

### Файлы:
- `apps/channels/providers.py` — MAX API: register/unregister/info/send/normalize
- `apps/channels/api.py` — _try_register_max, lifecycle для MAX
- `apps/channels/public_views.py` — X-Max-Bot-Api-Secret
- `frontend/src/views/ChannelsView.vue` — bot_token, webhook button

### Верификация:
- `manage.py check`: 0 issues ✅
- channels 3/3 tests ✅
- DEC-020 зафиксировано

---

## 2026-04-15 — Чаты: WebSocket вместо polling, tenant-изоляция групп

### Корневая причина:
Первая итерация использовала `setInterval` polling — костыль, противоречащий стеку (Django Channels + Redis channel layer уже развёрнуты). Вторая итерация использовала WS, но группы `chat.channel.{id}` не содержали tenant scope — потенциальная кросс-тенантная утечка.

### Изменения:
1. **ChatConsumer** (`apps/channels/consumers.py`): `AsyncJsonWebsocketConsumer`. Требует `tenant_slug` из scope (code 4400 при отсутствии). Группы: `chat.{slug}.channel.{id}`.
2. **WS Auth** (`apps/core/channels_auth.py`): `JWTQueryAuthMiddleware` теперь парсит `?slug=` и кладёт в `scope['tenant_slug']`.
3. **Broadcast из Celery** (`apps/channels/tasks.py`): `_broadcast_message(tenant_slug, ...)` и `_broadcast_session_update(tenant_slug, ...)` — tenant.slug передаётся из задачи.
4. **WS-маршрут** (`config/routing.py`): `ws/chat/`.
5. **Frontend** (`frontend/src/views/ChannelsView.vue`): WS с `?token=...&slug=...`. Polling полностью убран.
6. **DEC-019** зафиксировано в DECISIONS.md.

### Файлы:
- `apps/channels/consumers.py` — NEW
- `apps/channels/tasks.py` — broadcast + tenant slug
- `apps/core/channels_auth.py` — slug в scope
- `config/routing.py` — ws/chat/
- `frontend/src/views/ChannelsView.vue` — WS вместо polling

### Верификация:
- `manage.py check`: 0 issues ✅
- channels 3/3 + crm 2/2 + distribution 2/2 + notifications 3/3 = 10/10 ✅

---

## 2026-04-15 — Telegram webhook: tenant slug в URL, полный E2E

### Корневая причина (дополнение):
Webhook URL не содержал tenant slug — запросы от Telegram приходили без tenant-контекста, Django возвращал 400. Канал #8 был создан до фикса авто-регистрации, поэтому webhook вообще не был установлен.

### Изменения:
- **URL-паттерн:** `/channels/webhook/{tenant_slug}/{channel_type}/{channel_id}/` (раньше без slug).
- **`public_views.py`:** tenant резолвится из URL slug напрямую (не из middleware/headers). Используется `schema_context('public')` → `tenant_context(tenant)`.
- **`providers.py`:** `register_telegram_webhook()` принимает `tenant_slug` и включает его в URL.
- **`api.py`:** `_try_register_telegram()` определяет `tenant_slug` из `connection.tenant`.
- **Frontend:** `webhookUrl()` включает `getTenantSlug()` в URL.

### Верификация:
- Webhook зарегистрирован: `https://...ngrok.../channels/webhook/test5/telegram/8/`
- 3 pending сообщения от Telegram доставлены и обработаны: HTTP 200
- ChatSession создана, 3 MessageLog записи (direction=in)
- Автолид: Deal #28 создана автоматически (source=telegram)
- Tests: 3/3 ✅, manage.py check: 0 issues ✅

---

## 2026-04-15 — Telegram: авто-регистрация webhook, валидация токена

### Корневая причина:
При создании Telegram-канала система НЕ вызывала `setWebhook` в Telegram Bot API. Бот существовал в БД, но Telegram не знал, куда слать сообщения. Кроме того, валидация проверяла `X-Channel-Token`, а Telegram шлёт `X-Telegram-Bot-Api-Secret-Token`.

### Изменения:
- **`providers.py`:** добавлены `register_telegram_webhook()` (setWebhook + auto-generate secret_token), `unregister_telegram_webhook()` (deleteWebhook), `get_telegram_webhook_info()`.
- **`api.py`:** create_channel автоматически регистрирует webhook в Telegram; patch_channel перерегистрирует при смене credentials/is_active; delete_channel вызывает deleteWebhook. Новые endpoints: `POST /{id}/register-webhook/`, `GET /{id}/webhook-info/`.
- **`public_views.py`:** валидация токена теперь проверяет `X-Telegram-Bot-Api-Secret-Token` (стандартный TG-заголовок) в первую очередь.
- **`settings.py`:** добавлен `WEBHOOK_BASE_URL` — публичный URL для формирования webhook-адреса.
- **Frontend:** статус канала теперь показывает detail при наведении; кнопка 🔗 для ручной перерегистрации webhook.
- **Чеклист З (38-41):** откачен на ⬜ до ручной проверки пользователем.

### Файлы:
- `apps/channels/providers.py` — register/unregister/get_webhook_info
- `apps/channels/api.py` — авто-регистрация при CRUD, новые endpoints
- `apps/channels/public_views.py` — X-Telegram-Bot-Api-Secret-Token
- `config/settings.py` — WEBHOOK_BASE_URL
- `frontend/src/views/ChannelsView.vue` — status detail, register button

### Валидация:
- manage.py check: 0 issues ✅
- Channels tests: 3/3 ✅
- Docker rebuild: OK ✅

---

## 2026-04-15 — Мессенджер-каналы: верификация чеклиста З (38–41)

### Изменения:
- **Frontend ChannelsView полностью переработан:** два таба — «Каналы» (CRUD с credentials по типу, webhook URL, auto_create_lead, welcome_message) и «Чаты» (выбор канала → список сессий → переписка + отправка ответа).
- **Динамические credentials:** Telegram (bot_token), WhatsApp (send_url, auth_token), MAX (send_url), общий webhook_token.
- **API list_channels:** добавлены credentials и welcome_message в ответ; разрешён доступ manager.
- **Роутер:** channels доступен для owner/admin/manager.

### Файлы:
- `frontend/src/views/ChannelsView.vue` — полная переработка (каналы + чаты + лог)
- `apps/channels/api.py` — credentials/welcome_message в list, manager-доступ
- `frontend/src/router/index.ts` — manager role для channels

### E2E верификация (Docker):
1. Каналы CRUD: Telegram/WhatsApp/MAX create, patch, toggle, delete — OK ✅
2. Incoming + bridge: route_incoming_message → session + message — OK ✅
3. Auto-lead: auto_create_lead → Deal created — OK ✅
4. Message log: GET messages, direction/text/timestamp — OK ✅
5. Channels tests: 3/3, manage.py check: 0 issues ✅

---

## 2026-04-15 — Распределение: полная реализация и верификация чеклиста Е (30–33)

### Изменения:
- **Автораспределение при создании сделки:** `create_deal()` вызывает `try_distribute('new_deal', ...)` если ответственный не указан. Сделка назначается менеджеру по активному правилу.
- **Синхронизация ManagerProfile из Membership:** `ensure_builtin_manager_profiles()` создаёт/обновляет ManagerProfile для всех активных членов команды (builtin CRM). Вызывается автоматически перед распределением и при запросе списка менеджеров.
- **Пустой пул менеджеров = все активные:** если в правиле не указаны конкретные менеджеры, используются все активные ManagerProfile.
- **Frontend:** регистрация PMultiSelect, замена нативных `<select>` на PrimeVue PSelect, название сделки в логе, исправленная отправка формы редактирования.
- **Триггеры:** оставлен только `new_deal` (новая сделка); убраны `new_lead` и `stage_change`.

### Файлы:
- `apps/distribution/services.py` — `ensure_builtin_manager_profiles()`, `try_distribute()`, fallback на всех менеджеров
- `apps/distribution/api.py` — название сделки в логе, синхронизация менеджеров
- `apps/distribution/models.py` — триггер только `new_deal`
- `apps/crm/api.py` — `create_deal()` триггерит распределение
- `frontend/src/main.ts` — регистрация PMultiSelect
- `frontend/src/views/DistributionView.vue` — PSelect, пул менеджеров, лог с названием сделки

### E2E верификация (Docker):
1. Rules CRUD: create (managers+fallback) / read / patch / delete — OK ✅
2. Стратегии: 4/4 в STRATEGIES dict — OK ✅
3. Создание сделки без ответственного → auto-assign — OK ✅
4. Лог: кому/когда/почему + название сделки — OK ✅
5. Distribution tests: 2/2 + CRM tests: 2/2 — OK ✅
6. `manage.py check`: 0 issues ✅

---

## 2026-04-15 — Распределение: исправление frontend, лог распределения, менеджеры

### Изменения:
- **Frontend DistributionView полностью переработан:** исправлены варианты триггеров (new_lead, new_deal, stage_change) и стратегий (min_load, round_robin, weighted, manual_queue) — ранее использовались несуществующие значения (missed_call, random, fixed).
- **Пул менеджеров и fallback:** в форму правила добавлен PMultiSelect для выбора менеджеров из доступных профилей и PSelect для fallback-менеджера.
- **Вкладка «Лог распределения»:** новая вкладка с таблицей: дата, правило, тип сущности, ID, назначенный менеджер, источник, стратегия, причина.
- **Новый endpoint `/api/distribution/managers/`:** возвращает список доступных ManagerProfile для выбора в UI.

### Файлы:
- `frontend/src/views/DistributionView.vue` — полная переработка
- `apps/distribution/api.py` — добавлен `list_available_managers`

### E2E верификация (Docker):
1. Rules CRUD: create/patch/delete — OK ✅
2. Стратегии: все 4 в backend model — OK ✅
3. Auto-trigger: webhook → task → assign chain — OK ✅
4. Log endpoint: /api/distribution/log/ — OK ✅
5. Managers endpoint: /api/distribution/managers/ — OK ✅
6. Distribution tests: 2/2 — OK ✅
7. `manage.py check`: 0 issues ✅

---

## 2026-04-15 — Договоры: ссылка подписания в API + ЭДО в списке контактов + верификация чеклиста Д

### Изменения:
- **signing_url в API контрактов:** `list_contracts` и `get_deal` возвращают `signing_url` для каждого контракта с активной сессией подписания. Frontend подставляет ссылку при открытии диалога — не пропадает после закрытия.
- **ЭДО в списке контактов:** добавлена колонка «ЭДО» в таблицу контактов (✅ / —). API `list_contacts` возвращает `esign_agreement_signed_at`.
- **Верификация чеклиста Д (пп. 22–29):** все пункты проверены E2E и отмечены ✅.

### Файлы:
- `apps/contracts/api.py` — `list_contracts`: signing_url из SigningSession
- `apps/crm/api.py` — `get_deal` contracts: signing_url; `list_contacts`: esign_agreement_signed_at
- `frontend/src/views/ContractsView.vue` — pre-populate signingUrl
- `frontend/src/views/CRMView.vue` — pre-populate dealSigningUrl; колонка ЭДО в контактах
- `docs/CHECKLIST.md` — секция Д: все ✅

### E2E верификация (Docker):
1. `list_contracts`: signing_url возвращается для контрактов с сессиями ✅
2. `get_deal` contracts: signing_url присутствует ✅
3. `list_contacts`: esign_agreement_signed_at возвращается ✅
4. Signing page (unsigned): consent_checkbox=True, agreement_link=True ✅
5. 8/8 unit tests — OK

---

## 2026-04-15 — Договоры: согласие на ЭП при подписании, публичная страница соглашения

### Изменения:
- **Чекбокс согласия на подписании:** на странице подписания договора добавлен чекбокс «Согласен с условиями электронной подписи» со ссылкой на текст соглашения. Кнопка «Получить код» заблокирована до принятия условий. При подписании без согласия — ошибка.
- **Публичная страница соглашения:** новый endpoint `GET /sign/{token}/esign-agreement/` отображает полный текст соглашения об ЭП, заполненный данными сделки. Открывается в новой вкладке по ссылке из чекбокса.
- **Валидация согласия в verify:** скрытое поле `esign_consent=1` передаётся в форму подписания. Backend проверяет наличие — без согласия подписание невозможно.
- **Ссылка на скачивание соглашения в профиле контакта:** при подписанном соглашении рядом с датой появилась ссылка «Скачать PDF» на подписанный документ.

### Файлы:
- `apps/contracts/public_views.py` — новый `sign_esign_agreement` view; `sign_verify`: проверка `esign_consent`
- `config/urls.py` — route `/sign/{token}/esign-agreement/`
- `templates/signing.html` — чекбокс, ссылка на соглашение, disabled кнопка
- `templates/esign_agreement.html` — новый шаблон для просмотра соглашения
- `frontend/src/views/CRMView.vue` — ссылка «Скачать PDF» в профиле контакта

### E2E верификация (Docker):
1. Signing page: checkbox=True, agreement_link=True ✅
2. Agreement page: title=True, 63-ФЗ=True ✅
3. Verify WITHOUT consent → «Необходимо принять условия электронной подписи» ✅
4. Verify WITH consent → contract signed ✅
5. E-agreement auto-created: contract #13, status=signed ✅
6. Contact: esign_agreement_signed_at=2026-04-15T07:30:24, esign_agreement_id=13 ✅
7. 8/8 unit tests — OK

---

## 2026-04-15 — Договоры: полный телефон в ПЭП, автоподписание соглашения об ЭП, профиль контакта

### Изменения:
- **Полный телефон в блоке ПЭП:** убрана маскировка `_mask_phone()` при генерации PDF-подписи. Теперь в подписанном PDF отображается полный номер телефона подписанта (79999999999), а не `79***9999`.
- **Автоподписание соглашения об ЭП:** при первом подписании любого договора контактом автоматически формируется и подписывается «Соглашение об использовании электронной подписи» из системного шаблона. Повторное подписание не создаёт дубликат (guard по `contact.esign_agreement_signed_at`). Ошибка в автоподписании не блокирует основной signing flow (try/except с логированием).
- **Электронный документооборот в профиле контакта:** в карточке контакта (CRM) отображается статус соглашения об ЭП: дата подписания или предупреждение «Соглашение не подписано». API `get_contact` возвращает `esign_agreement_signed_at` и `esign_agreement_id`.

### Файлы:
- `apps/contracts/services.py` — `_regenerate_pdf_with_signature`: полный телефон; `_ensure_esign_agreement()`: новая функция автоподписания; `verify_signing`: вызов `_ensure_esign_agreement`
- `apps/crm/models.py` — Contact: `esign_agreement_signed_at`, `esign_agreement_id`
- `apps/crm/migrations/0005_add_esign_agreement_fields.py` — миграция новых полей
- `apps/crm/api.py` — `get_contact`: esign-поля в ответе
- `frontend/src/views/CRMView.vue` — статус соглашения в карточке контакта

### E2E верификация (Docker):
1. Подпись контракта #6: send → OTP → verify → HTTP 200 → contract signed
2. Автосоздание e-agreement: контракт #10 (status=signed, template="Соглашение об использовании ЭП", note="Подписано автоматически при подписании договора #6")
3. Контакт: `esign_agreement_signed_at: 2026-04-15T07:12:15`, `esign_agreement_id: 10`
4. Полный телефон в PDF: `79999999999` (без маскировки) ✅
5. Все 8 тестов (contracts+crm) — OK

---

## 2026-04-15 — Договоры: таймлайн сделки, полный блок ПЭП, соглашение об ЭП

### Изменения:
- **Таймлайн сделки — отслеживание ALL изменений:** `patch_deal` переписан: нормализация типов (Decimal→float, date→str) перед сравнением; activity body теперь показывает `Поле: старое → новое` для каждого изменённого поля; добавлено отслеживание `custom_fields`; FK-поля (`contact_id`, `company_id`, `responsible_id`) резолвятся в human-readable имена.
- **Полный блок ПЭП в PDF:** убрано сокращение хешей (`[:16]+'...'`). Теперь в PDF выводятся полные 64-символьные SHA-256 хеш и HMAC-SHA256 подпись, а также IP-адрес подписанта, UUID сессии, тип подписи, ссылка на ст. 6 и ст. 9 63-ФЗ.
- **Соглашение об использовании ЭП:** новый системный шаблон (миграция 0006). Полноценный юридический документ: предмет соглашения, определения (ПЭП, ключ, электронный документ), порядок использования, юридическая сила, обязанности сторон, ответственность, заключительные положения.

### Файлы:
- `apps/crm/api.py` — `patch_deal`: type-safe сравнение, old→new в body, FK resolution
- `apps/contracts/services.py` — `_regenerate_pdf_with_signature`: полные хеши, IP, session UUID
- `apps/contracts/migrations/0006_seed_esign_agreement_template.py` — новый системный шаблон

### E2E верификация (Docker):
1. PATCH deal: `Сумма: 10000.00 → 250000.0`, `Ответственный: test5 → —`, `Источник: website → web` — OK
2. Подпись контракта #8 (соглашение об ЭП): send → OTP → verify → download 33KB PDF — OK
3. Полные хеши в HTML/PDF: 64-char signature ✅, 64-char hash ✅, IP ✅, session UUID ✅, no truncation ✅
4. Все 8 тестов (contracts+crm) — OK

---

## 2026-04-15 — Договоры: улучшения подписания (автозаполнение, скачивание, ПЭП в PDF)

### Изменения:
- **Автозаполнение телефона:** при отправке на подписание телефон контакта подтягивается автоматически. Backend: `getDeal` и `list_contracts` API возвращают `contact_phone` через `select_related('deal__contact')`. Frontend: CRMView и ContractsView предзаполняют поле из контакта.
- **Скачивание/отправка на email после подписания:** на странице успешного подписания добавлены кнопка «Скачать PDF» и форма отправки на email. Backend: `sign_download_pdf` (GET, FileResponse) и `sign_send_email` (POST, Django EmailMessage с вложением). Оба endpoint — публичные, `@csrf_exempt`.
- **Блок ПЭП в PDF:** после подписания PDF перегенерируется с блоком электронной подписи (дата, маскированный телефон, хеш SHA-256, подпись HMAC-SHA256, 63-ФЗ). `html_snapshot` обновляется вместе с PDF.
- **CSRF fix:** все публичные POST views (`sign_verify`, `sign_request_otp`, `sign_send_email`) помечены `@csrf_exempt`.

### Файлы:
- `apps/contracts/services.py` — `_regenerate_pdf_with_signature()`, `send_signed_contract_email()`
- `apps/contracts/public_views.py` — `sign_download_pdf`, `sign_send_email`, `@csrf_exempt`
- `apps/contracts/api.py` — `contact_phone` в `list_contracts`
- `apps/crm/api.py` — `contact_phone` в `getDeal` contracts
- `config/urls.py` — `/sign/{token}/download/`, `/sign/{token}/send-email/`
- `templates/signing_success.html` — кнопка скачивания + форма email
- `frontend/src/views/CRMView.vue` — автозаполнение телефона из контакта
- `frontend/src/views/ContractsView.vue` — автозаполнение из `contact_phone`

### E2E верификация (Docker):
1. `POST /api/contracts/6/send-for-signing/` → `{token, signing_url}`
2. `GET /sign/{token}/` → HTTP 200
3. `POST /sign/{token}/request-otp/` → `{test_otp: 475028}`
4. `POST /sign/{token}/verify/` → HTTP 200, signing_success.html с кнопкой скачивания
5. `GET /sign/{token}/download/` → HTTP 200, PDF 18KB, `file: PDF document, version 1.7`
6. `POST /sign/{token}/send-email/` → `{detail: sent}`
7. `contact_phone=79999999999` в getDeal и list_contracts API
8. Все 5 unit-тестов signing_flow — OK

---

## 2026-04-14 — Договоры: переработка signing flow — OTP на стороне клиента

### Изменения:
- **Архитектурная переработка signing flow:** OTP больше НЕ отправляется из CRM. CRM-менеджер вводит телефон → получает ссылку → копирует и отправляет клиенту. Клиент открывает ссылку → видит документ + замаскированный телефон → нажимает «Получить код» → получает SMS → вводит код → подписывает.
- **Backend:** `send_for_signing()` теперь создаёт сессию без OTP. Новая функция `request_signing_otp(token)` генерирует и отправляет OTP по запросу клиента.
- **Новый public endpoint:** `POST /sign/{token}/request-otp/` — клиент запрашивает код с публичной страницы.
- **signing.html:** Двухшаговый JS-driven flow: Step 1 — «Получить код», Step 2 — ввод кода + «Подписать».
- **Frontend (CRM):** Убраны все OTP-поля из диалогов подписания в ContractsView и CRMView. Остался только: телефон → «Сформировать ссылку» → ссылка + кнопка копирования.
- **Модель:** `otp_code_hash` теперь `blank=True, default=''` — заполняется только при request-otp.
- **Маскировка телефона:** на публичной странице отображается `+7***4567` вместо полного номера.

### End-to-end верификация (Docker):
1. `POST /api/contracts/4/send-for-signing/` → `{detail: sent, token: ..., signing_url: ...}`, **без test_otp**
2. `GET /sign/{token}/` → HTML с «Получить код», masked phone `+7***4567`, OTP-input скрыт
3. `POST /sign/{token}/request-otp/` → `{detail: sent, test_otp: 751129}`
4. `POST /sign/{token}/verify/` с OTP → signing_success.html
5. Contract #4: status=signed, signature_data: HMAC-SHA256, pdf_hash_verified=True

### Файлы:
- `apps/contracts/services.py` — split send_for_signing + request_signing_otp + _mask_phone + SigningContext.masked_phone
- `apps/contracts/public_views.py` — новый `sign_request_otp` view, masked_phone в контексте
- `apps/contracts/models.py` — otp_code_hash blank=True
- `apps/contracts/api.py` — убран test_otp из ответа send-for-signing
- `config/urls.py` — route `/sign/{token}/request-otp/`
- `templates/signing.html` — двухшаговый JS flow
- `frontend/src/views/ContractsView.vue` — убран OTP, только ссылка
- `frontend/src/views/CRMView.vue` — убран OTP, только ссылка
- `apps/contracts/tests/test_signing_flow.py` — обновлены тесты
- `apps/contracts/migrations/0005_alter_signing_session_otp_hash.py` — миграция

### Валидация:
- `docker compose down && up -d --build` — OK
- `python manage.py check` — 0 issues
- `python manage.py test apps.contracts.tests.test_signing_flow` — 5/5 OK
- Full HTTP e2e: login → send → public page → request-otp → verify → signed ✓

---

## 2026-04-16 — Договоры: исправлено скачивание PDF, полный signing flow в CRM

### Изменения:
- **PDF download fix (root cause):** `window.open()` не передаёт `X-Tenant-Slug` header → 403. Добавлен `&tenant_slug=` query param в URL для PDF download в ContractsView и CRMView. Tenant resolver уже поддерживал `request.GET.get('tenant_slug')`.
- **Signing flow в карточке сделки:** Добавлена кнопка «Отправить на подпись» (pi-send) для контрактов со статусом draft/viewed. Полный диалог: ввод телефона → отправка OTP → отображение ссылки для подписания (с кнопкой «Копировать») → ввод OTP-кода → подписание. Тестовый OTP отображается в stub-режиме.
- **`getTenantSlug` import:** добавлен в ContractsView и CRMView

### End-to-end верификация (в Docker, HTTP):
1. `GET /api/contracts/1/pdf/?token=...` БЕЗ tenant_slug → HTTP 403 (ожидаемо)
2. `GET /api/contracts/1/pdf/?token=...&tenant_slug=test5` → HTTP 200, size=2791, is_pdf=True
3. `POST /api/contracts/3/send-for-signing/` → signing_url + test_otp
4. `GET /sign/{token}/` → HTML страница с формой OTP
5. `POST /sign/{token}/verify/` с CSRF + OTP → signing_success.html
6. Contract #3: status=signed, signature_data.type=simple_electronic_signature, pdf_hash_verified=True

### Файлы:
- `frontend/src/views/ContractsView.vue` — `getTenantSlug` import, `&tenant_slug=` в downloadPdf
- `frontend/src/views/CRMView.vue` — `getTenantSlug` import, `&tenant_slug=` в downloadDealContractPdf, signing dialog + полный JS flow (openDealSigningDialog, dealSendForSigning, dealVerifySigning, copyDealSigningLink)

### Валидация:
- `docker compose down && up -d --build` — OK
- `python manage.py check` — 0 issues
- `python manage.py test apps.contracts.tests` — 5/5 OK
- Vite dev server — OK, no errors

---

## 2026-04-16 — Договоры: криптографическая подпись, публичная страница подписания, исправление PDF

### Изменения:
- **MEDIA_URL fix:** `'media/'` → `'/media/'` — файлы теперь отдаются correctly через Django `static()` helper
- **Публичная страница подписания:** `sign_verify` теперь рендерит HTML (success/error), а не возвращает сырой JSON; добавлен `signing_success.html`; `signing.html` обновлён: отображение ошибок, статус «подписан», inputmode numeric
- **Криптографическая подпись (ПЭП):** Новые поля `Contract.pdf_hash` (SHA-256 PDF) и `Contract.signature_data` (JSONField); при подписании создаётся HMAC-SHA256 подпись, включающая хеш документа, данные подписанта (телефон, IP, UA), timestamp; миграция `0004_add_crypto_signature_fields`
- **OTP безопасность:** `random.randint` → `secrets.randbelow` для криптографически безопасной генерации OTP
- **Ссылка для подписания:** `send-for-signing` API теперь возвращает `signing_url`; frontend отображает ссылку с кнопкой «Копировать»
- **Просмотр договора в сделке:** Добавлена кнопка «Просмотр» (pi-eye) в карточке сделки с диалогом предпросмотра html_snapshot
- **GET /contracts/{id}/ расширен:** добавлены `pdf_hash`, `signature_data`, `signed_at`
- **Тест:** assertion `signature_data` содержит type/algorithm/signature

### Файлы:
- `config/settings.py` — MEDIA_URL, STATIC_URL
- `apps/contracts/models.py` — `pdf_hash`, `signature_data` fields
- `apps/contracts/migrations/0004_add_crypto_signature_fields.py`
- `apps/contracts/services.py` — `_compute_pdf_hash`, `_build_signature_record`, secrets OTP
- `apps/contracts/api.py` — `signing_url` в ответе, `pdf_hash` в generate
- `apps/contracts/public_views.py` — HTML rendering вместо JSON
- `templates/signing.html` — error/success states
- `templates/signing_success.html` — NEW
- `frontend/src/views/ContractsView.vue` — signing URL display + copy
- `frontend/src/views/CRMView.vue` — contract preview in deal
- `apps/contracts/tests/test_signing_flow.py` — crypto signature assertion

### Валидация:
- `docker compose down && up -d --build` — OK
- `python manage.py check` — 0 issues
- `python manage.py test apps.contracts.tests` — 5/5 OK
- Vite dev server — OK, no errors
- Health check — HTTP 200

### Риски:
- Существующие контракты без `pdf_hash` — при подписании `pdf_hash_verified` будет false (пустая строка vs SHA-256), но подпись всё равно создаётся

---

## 2026-04-16 — Договоры: системные шаблоны, визуальный редактор, signing flow, PDF fix

### Изменения:
- **Системные шаблоны:** `is_system` поле в `ContractTemplate`; шаблоны теперь создаются в миграции (не при onboarding); бейджик «Встроенный» в UI
- **Визуальный редактор шаблонов:** contenteditable-редактор с тулбаром (Bold/Italic/Underline/H1/H2/P/списки/таблицы); замена старого textarea
- **Конструктор полей сделки:** выпадающий список полей (сделка/контакт/компания) — вставляет `{{ field }}` тег в редактор; маппинг создаётся автоматически при сохранении шаблона
- **Signing flow end-to-end:** отправка OTP → отображение тестового кода в UI → ввод кода → `POST /verify-signing/` → статус «Подписан»
- **PDF download fix:** endpoint `get_contract_pdf` поддерживает `?token=` query param для `window.open()` (JWT header невозможен)
- **Исправление тестов:** `send_for_signing()` возвращает `tuple`, тесты обновлены

### Файлы:
- `apps/contracts/models.py` — `is_system = BooleanField`
- `apps/contracts/migrations/0003_add_is_system_and_seed.py` — новая миграция + seed 3 шаблонов
- `apps/contracts/api.py` — `is_system`/`html_body` в list_templates; `?token=` в get_contract_pdf; `test_otp` в send_for_signing; `verify_contract_signing` endpoint
- `apps/contracts/services.py` — `send_for_signing` возвращает `(session, test_otp | None)`
- `apps/tenants/onboarding_api.py` — удалена `_seed_default_contract_templates()`
- `frontend/src/views/ContractsView.vue` — полная перезапись: визуальный редактор, конструктор полей, signing flow с OTP
- `apps/contracts/tests/test_signing_flow.py` — tuple unpacking fix

### Валидация:
- Docker rebuild: OK
- `manage.py check`: 0 issues
- `apps.contracts` tests: 5/5 passed
- Frontend (Vite): compiled clean, API 200 OK

---

## 2026-04-14 — Договоры: UI тема, стандартные шаблоны, быстрое действие, связь триггера

### Изменения:
- **ContractsView UI тема:** переведены все CSS-переменные с `--line`/`--surface`/`--primary`/`--muted` на PrimeVue токены (`--p-content-border-color`/`--p-surface-0`/`--p-primary-color`/`--p-text-muted-color`); нативные `<select>` → `PSelect`; добавлены `.field-label`, `.w-full`
- **Стандартные шаблоны:** при онбординге создаются 3 шаблона: Договор купли-продажи, Договор оказания услуг, Договор аренды — с `variable_schema` (deal_id, deal_name, amount, currency, contact_name, company_name)
- **Быстрое действие в сделке:** кнопка «Договор» в карточке сделки (CRMView) → диалог выбора шаблона и метода подписания → `POST /contracts/generate` с `deal_id`
- **Триггер create_contract:** диалог конфигурации триггера показывает выбор шаблона (`PSelect`) при типе `create_contract`; `saveTrigger` сохраняет `template_id` в `auto_action`; таблица триггеров отображает имя шаблона

### Файлы:
- `frontend/src/views/ContractsView.vue` — CSS тема, PSelect, computed options
- `frontend/src/views/CRMView.vue` — кнопка «Договор» в сделке, диалог создания, template_id в тригерах
- `apps/tenants/onboarding_api.py` — `_seed_default_contract_templates()` (3 шаблона)
- `apps/contracts/api.py` — без изменений (уже работал)

### Валидация:
- Docker rebuild: OK
- `manage.py check`: 0 issues
- `apps.contracts` + `apps.crm` tests: 7/7 passed
- Frontend (Vite): compiled clean

---

## 2026-04-15 — Договоры: интеграция FieldMapping (backend + frontend)

### Изменения:
- `create_contract_from_deal()` теперь вызывает `_apply_field_mappings(data, deal, template)` после извлечения данных — маппинг переменных шаблона на поля сделки CRM работает
- Добавлены `_apply_field_mappings()` и `_resolve_field_path()` в services.py — разрешение dotted-путей (`contact.phone`, `company.name`) на Django моделях
- `save_mappings` API: `connection_id=0` обрабатывается как `crm_connection=None` (встроенный CRM)
- `list_templates` API теперь возвращает `variable_schema`
- Frontend: добавлен диалог «Маппинг полей» в шаблонах договоров — таблица переменная↔CRM-путь с CRUD

### Файлы:
- `apps/contracts/services.py` — _apply_field_mappings, _resolve_field_path
- `apps/contracts/api.py` — save_mappings (conn_id=0→None), list_templates (+variable_schema)
- `frontend/src/views/ContractsView.vue` — mapping dialog UI

### Валидация:
- Docker rebuild: OK
- `manage.py check`: 0 issues
- `apps.contracts` tests: 5/5 passed

---

## 2026-04-15 — CRM: Ответственный → любой пользователь организации + привязка задач триггеров

### Изменения:
- FK `responsible` в моделях `Deal`, `Activity`, `Contact`, `Company` изменён с `integrations.ManagerProfile` на `users.User`
- `GET /crm/managers/` теперь возвращает всех активных участников организации (Membership, кроме viewer) вместо ManagerProfile
- `GET /crm/activities/tasks/` (Мои задачи) фильтрует по `responsible_id=request.auth.id` напрямую — задачи, созданные триггерами, корректно отображаются у ответственного
- `GET /crm/stats/managers/` группирует по User (first_name/last_name/email)
- `GET /api/dashboard/managers/` аналогично обновлён
- `BuiltinCRMAdapter.list_users()` возвращает пользователей через Membership
- `auto_actions.py create_task` — `responsible` и `created_by` устанавливаются напрямую из `deal.responsible` (User)
- Миграция `crm.0003_responsible_to_user` с data-миграцией (ManagerProfile.user_id → responsible_user_id)
- **ИСПРАВЛЕНО:** `docker-compose.yml` — `migrate` сервис теперь запускает `migrate_schemas --shared` + `migrate_schemas --tenant` (ранее tenant-миграции не применялись на существующие схемы)

### Файлы:
- `apps/crm/models.py` — 4 FK изменены
- `apps/crm/api.py` — list_managers, my_tasks, manager_stats
- `apps/crm/dashboard_api.py` — managers endpoint
- `apps/crm/adapter.py` — list_users
- `apps/crm/services/auto_actions.py` — create_task упрощён
- `apps/crm/migrations/0003_responsible_to_user.py` — миграция
- `apps/crm/migrations/0004_*.py` — переименование индексов
- `apps/crm/tests/test_auto_actions.py` — адаптирован под User
- `apps/crm/tests/test_dashboard_api.py` — адаптирован под User
- `docker-compose.yml` — migrate service: `--shared` + `--tenant`

### Валидация:
- Docker rebuild: OK, all tenant schemas migrated
- `manage.py check`: 0 issues
- 14/14 tests OK (crm + contracts + integrations + distribution)
- HTTP check: `GET /api/crm/managers/` → 401 (auth required, endpoint responding)
- DB verification: `Deal.responsible_id` → FK to `users_user` confirmed in all schemas

---

## 2026-04-14 — CRM: Закрытие раздела Г (активности контакта, задачи, статистика)

### Файлы:
- `frontend/src/api/crm.ts`: добавлены `managerStats()`, `myTasks()` API-обёртки
- `frontend/src/views/CRMView.vue`:
  1. **п.18** Карточка контакта: кнопка 👁️ в таблице → диалог с данными + лог активности
  2. **п.19** Вкладка «Задачи»: список из `/activities/tasks/`, фильтр по статусу (planned/done/overdue), кнопки «выполнить» и «удалить»
  3. **п.21** Вкладка «Статистика»: таблица конверсии по воронке с PProgressBar + таблица сделок по менеджерам

### Валидация:
- Docker rebuild: OK, `manage.py check`: 0 issues
- Vite HMR: без ошибок
- CRM + contracts tests: 7/7 OK

---

## 2026-04-14 — CRM: Триггеры в отдельный раздел, список с колонкой Этап, полный лог активности

### Файлы:
- `frontend/src/views/CRMView.vue`:
  1. Триггеры вынесены в отдельную вкладку «Триггеры» с таблицей (воронка, этап, действие, параметры). Кнопки создания, редактирования и удаления. Диалог настройки с выбором воронки/этапа для новых триггеров.
  2. Вид списка: убрана группировка по строкам. Этап — обычная сортируемая колонка с цветной точкой. Все колонки сортируемые.
  3. Из стадий в воронках убран bolt-кнопка, оставлен PTag с названием триггера для информации.
- `apps/crm/api.py`:
  - `patch_deal`: теперь логирует изменённые поля через Activity(type='system', title='Сделка обновлена')
- `apps/contracts/services.py`:
  - `create_contract_from_deal`: теперь создаёт Activity(type='contract') при генерации договора из сделки

### Итого по логу активности сделки:
- Создание сделки → system
- Смена стадии → stage_change
- Редактирование полей → system (с перечислением изменённых полей)
- Создание договора → contract
- Автосоздание задачи (триггер) → task
- Ручные записи (заметка/звонок/email/сообщение/задача) → соответствующий тип

### Валидация:
- Docker rebuild: OK, `manage.py check`: 0 issues
- Vite HMR: без ошибок
- CRM + contracts tests: 7/7 OK

---

## 2026-04-15 — CRM: Исправления UX (высота, активности, список, триггеры)

### Файлы:
- `frontend/src/styles/main.css`:
  - `.layout-shell`: `height: 100vh; overflow: hidden` (было `min-height: 100vh`)
  - `.page-wrap`: добавлены `overflow-y: auto; min-height: 0; display: flex; flex-direction: column`
- `frontend/src/views/CRMView.vue`:
  1. Высота kanban: flex-chain от layout-shell до kanban с `min-height: 0` — колонки не превышают окно
  2. Лог активности: при создании сделки — системная запись; при смене стадии — запись `stage_change`
  3. Список: единая PDataTable с `rowGroupMode="subheader"`, группировка по стадиям с цветными заголовками
  4. Триггеры: отображение badge на стадиях (📋 Задача / 🔔 Уведомление / 📄 Договор), bolt-иконка подсвечивается `warn` при активном триггере, редактирование через диалог с `showClear`
- `apps/crm/api.py`:
  - `create_deal`: авто-создание Activity(type='system', title='Сделка создана')
  - `move_deal`: авто-создание Activity(type='stage_change') с описанием перехода

### Валидация:
- Docker rebuild: OK, `manage.py check`: 0 issues
- Vite HMR: без ошибок
- CRM tests: 2/2 OK

---

## 2026-04-15 — CRM: Kanban UX, фильтры, триггеры, drag-reorder стадий

### Файлы:
- `apps/crm/api.py`:
  - Kanban endpoint обогащён: `contact_id`, `company_id`, `source`, `created_at` для клиентской фильтрации
  - `CompanyIn.inn` — добавлена валидация `max_length=12` (ранее 500 при длинном ИНН)
  - `get_deal` activities: добавлен `body` в сериализацию
- `frontend/src/views/CRMView.vue`:
  1. Kanban занимает полную высоту окна (`calc(100vh - 160px)`), колонки скроллятся внутри
  2. Фильтры на kanban: по источнику, контакту, компании, дате (сегодня/вчера/неделя) — клиентская фильтрация
  3. Переключатель отображения Board ↔ List (таблица по стадиям)
  4. Drag-and-drop reorder стадий в настройках воронки → `reorderStages` API
  5. Настройка триггеров на стадиях (create_task, send_notification, create_contract) через диалог
  6. Лог активности в сделке: выбор типа (заметка/звонок/сообщение/email/задача), body, тег типа
  7. Быстрое создание контакта/компании добавлено в диалог редактирования сделки (`+` кнопки)
  8. Удаление стадий из настроек воронки

### Валидация:
- Docker rebuild: OK, `manage.py check`: 0 issues
- Vite HMR: без ошибок компиляции
- CRM tests: 2/2 OK

---

## 2026-04-15 — CRM: дефолтная воронка + расширенные формы создания

### Файлы:
- `apps/tenants/onboarding_api.py` — `_apply_crm_mode_step` при выборе `builtin` создаёт дефолтную воронку «Продажи» с 7 стадиями (Новая заявка → Квалификация → Предложение → Переговоры → Согласование → Успешно закрыта / Проиграна); idempotent (Guard: `Pipeline.objects.exists()`)
- `apps/crm/api.py` — новый endpoint `GET /crm/managers/` для выпадающего списка ответственных; импорт `ManagerProfile`
- `frontend/src/api/crm.ts` — добавлен `listManagers()`
- `frontend/src/views/CRMView.vue` — расширены формы:
  - Сделка: +стадия, валюта, контакт, компания, ответственный, дата закрытия, источник
  - Контакт: +должность, компания, мессенджер, источник, ответственный
  - Двухколоночная раскладка форм (`form-row-2`), подписи полей

### Валидация:
- Docker rebuild: OK, `manage.py check`: 0 issues, 41 тест: OK
- Endpoint `/api/crm/managers/`: HTTP 401 (auth required — OK)
- Frontend: Vite build OK, нет новых TS-ошибок

---

## 2026-04-14 — UX онбординг-визарда

### Файлы:
- `frontend/src/components/OnboardingWizard.vue` — полная переработка всех 5 шагов: 1) таймзона → PSelect из списка (РФ + СНГ, дефолт МСК); 2) CRM-режим → карточки с описанием; 3) менеджеры → динамические поля (имя + email), кнопка «Добавить»; 4) стратегия распределения → карточки (по очереди / равномерно / по весам / ручная очередь); 5) завершение
- `apps/tenants/onboarding_api.py` — `_apply_distribution_step` принимает `strategy` вместо `rule_name`, создаёт `DistributionRule` с выбранной стратегией

### Валидация:
- Docker rebuild: OK, `manage.py check`: 0 issues, 41 тест: OK
- Все 5 шагов проходят последовательно (API test: org+tz → crm_mode → managers structured → strategy → done)

---

## 2026-04-14 — Исправление онбординга (3 бага)

### Файлы:
- `apps/tenants/onboarding_api.py` — `payload: dict` → `payload: dict = Body(...)` (django-ninja не парсил body, возвращал 422 «Field required»)
- `frontend/src/router/guards.ts` — добавлен guard: redirect на `/app/onboarding` когда `onboarding_step < 5` для owner/admin
- `frontend/src/components/OnboardingWizard.vue` — кнопка «Пропустить» теперь с диалогом подтверждения (PDialog); try/finally в next()
- `frontend/src/views/OnboardingView.vue` — после завершения/пропуска → redirect на dashboard
- `frontend/src/views/DashboardView.vue` — убран встроенный виджет онбординга (теперь guard обеспечивает обязательный визард)

### Исправленные баги:
1. Онбординг появлялся как опциональный виджет внизу дашборда → теперь обязательный redirect при первом входе
2. Кнопка «Пропустить» без предупреждения скрывала визард навсегда → диалог подтверждения
3. Переход на следующий шаг не работал (django-ninja возвращал 422, payload не парсился из body) → `Body(...)`

### Валидация:
- Docker rebuild: OK
- `manage.py check`: 0 issues
- 41 тест: OK
- Все 5 шагов онбординга проходят последовательно (API)
- Skip: 0→5 сразу (API)

---

## 2026-04-14 — Приглашение по токену (accept invite)

### Файлы:
- `apps/users/api.py` — добавлен `import uuid`; добавлен `GET /api/auth/invite/check` (валидация токена, возврат email/org/role/has_account); переписан `POST /api/auth/invite/accept` (проверка TTL 48ч, email-валидация, поддержка существующих аккаунтов без сброса пароля); ссылка приглашения теперь ведёт на `FRONTEND_APP_URL` вместо `PLATFORM_DOMAIN`
- `config/views.py` — `frontend_entry` теперь передаёт query string при редиректе
- `config/urls.py` — добавлены маршруты `invite/accept` и `invite/accept/` для Django → frontend редиректа
- `frontend/src/api/auth.ts` — добавлены `checkInvite()` и `acceptInvite()` API-функции
- `frontend/src/views/AcceptInviteView.vue` — **новый** — страница принятия приглашения (проверка токена, форма, 2 режима: новый/существующий пользователь)
- `frontend/src/router/index.ts` — добавлен маршрут `/invite/accept` (public)

### Валидация:
- Docker rebuild: OK
- `manage.py check`: 0 issues
- 41 тест: OK
- `GET /api/auth/invite/check?token=invalid` → 400 «Недействительный токен приглашения»
- `POST /api/auth/invite/accept` с невалидным токеном → 400
- `GET /invite/accept?token=abc` → 302 redirect на frontend с query string

### Исправленные баги:
- `import uuid` отсутствовал в `apps/users/api.py` (invite_user вызывал `uuid.uuid4()` без импорта)
- `accept_invite` позволял принять приглашение с чужим email (security fix)
- `accept_invite` не проверял TTL токена
- `accept_invite` не возвращал `tenant_slug` (frontend не мог установить tenant-контекст)
- `frontend_entry` redirect терял query string (token не доходил до SPA)

---

## 2026-04-14 — Интеграция ЮKassa

### Файлы:
- `requirements.txt` — добавлен `yookassa==3.10.0`
- `config/settings.py` — добавлены `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `YOOKASSA_RETURN_URL`
- `apps/billing/models.py` — добавлены поля `yookassa_payment_id`, `yookassa_confirmation_url` на Payment
- `apps/billing/migrations/0004_add_yookassa_fields.py` — миграция новых полей
- `apps/billing/api.py` — checkout endpoint создаёт реальный платёж через YooKassa API, возвращает `confirmation_url`
- `apps/billing/webhook_views.py` — **новый** — обработка webhook от ЮKassa (`payment.succeeded`, `payment.canceled`)
- `apps/billing/admin.py` — обновлён PaymentAdmin (показывает yookassa_payment_id, readonly)
- `config/urls.py` — добавлен маршрут `billing/yookassa/webhook/`
- `frontend/src/api/tenant.ts` — типизированный `CheckoutResponse` с `confirmation_url`
- `frontend/src/views/SubscriptionView.vue` — redirect на ЮKassa вместо показа сообщения; refresh tenant state при возврате

### Валидация:
- Docker rebuild: OK (yookassa pip install ✓)
- `manage.py check`: 0 issues
- Миграция `0004_add_yookassa_fields`: applied на public + 5 tenant schemas
- 41 тест: OK
- Webhook endpoint: POST → 400 на невалидный payload, 405 на GET
- Checkout без YOOKASSA_SHOP_ID → HTTP 503 «Платёжная система не настроена»

### Риски:
- Для работы оплаты необходимо указать `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY` в `.env`
- Webhook URL должен быть доступен извне (ngrok для dev, домен в prod) и настроен в ЛК ЮKassa

---

## 2026-04-14 — Пробный период + модуль оплаты

### Файлы (Backend):
- `apps/tenants/models.py` — добавлены поля `trial_expires_at`, `is_paid`, свойства `trial_active`, `trial_expired`, `access_allowed`
- `apps/tenants/migrations/0003_add_trial_fields.py` — миграция trial полей
- `apps/billing/models.py` — добавлена модель `Payment` (tenant, plan, amount, status, months, paid_at, expires_at)
- `apps/billing/migrations/0003_add_payment.py` — миграция Payment
- `apps/billing/api.py` — `POST /billing/checkout/`, `GET /billing/payments/`, `POST /billing/change-plan/`, `GET /billing/plans/` (public, auth=None)
- `apps/billing/admin.py` — `PaymentAdmin` + действие `confirm_payment` (устанавливает is_paid, очищает trial)
- `apps/users/api.py` — регистрация устанавливает `trial_expires_at=now()+7d, is_paid=False`
- `apps/core/access.py` — `_check_trial()`: возвращает 402 при истечении триала; вызывается из `require_roles` и `require_feature_access`
- `apps/tenants/api.py` — `TenantOut` расширен полями `is_paid, trial_active, trial_expired, trial_expires_at`
- `apps/users/tests/base.py` — тестовый tenant получает `is_paid=True` для прохождения trial-guard

### Файлы (Frontend):
- `frontend/src/types.ts` — интерфейс `TenantInfo` с trial полями
- `frontend/src/api/tenant.ts` — функции `checkout()`, `changePlan()`, `getPayments()`
- `frontend/src/stores/tenant.ts` — импорт `TenantInfo` из types
- `frontend/src/router/guards.ts` — редирект на subscription при истечении триала
- `frontend/src/layouts/AppLayout.vue` — баннер триала (оставшиеся дни / истёк)
- `frontend/src/views/RegisterView.vue` — выбор тарифного плана при регистрации (карточки планов), загрузка планов из public API
- `frontend/src/views/SubscriptionView.vue` — полная страница подписки: статус триала, выбор плана, checkout, история платежей
- `frontend/src/main.ts` — зарегистрирован компонент PSelect (PrimeVue Select)

### Валидация:
- `docker compose down` → `docker compose up -d --build` → все контейнеры up
- `docker compose run --rm web python manage.py check` → 0 issues
- `docker compose run --rm web python manage.py migrate` → 2 новых миграции применены
- `docker compose run --rm web python manage.py test --verbosity=2` → 41 tests OK
- API тесты: `GET /billing/plans/` (public, 3 плана), `POST /billing/checkout/` (payment created), `GET /billing/payments/` (history), `POST /billing/change-plan/` (plan switched during trial), `GET /tenant/` (trial fields included)

### Риски:
- Оплата пока через ручное подтверждение в Django Admin (без интеграции с платёжной системой)
- Существующие тенанты не имели trial/paid полей — пришлось установить `is_paid=True` вручную

## 2026-04-15 — Полная реализация всех заглушек + доработка Frontend

### Файлы (Backend):
- `apps/billing/tasks.py` — fix missing timezone import
- `apps/channels/tasks.py` — fix silent exception swallowing
- `apps/tenants/onboarding_api.py` — structured JSON managers, real email required
- `apps/integrations/adapters_amocrm.py` — все 6 методов: реальные HTTP-вызовы amoCRM API v4
- `apps/integrations/adapters_bitrix24.py` — все 6 методов: реальные REST-вызовы Bitrix24
- `apps/crm/adapter.py` — BuiltinCRMAdapter: upload_file, register_chat_channel, receive_outgoing_message, attach_call_record
- `apps/telephony/tasks.py` — ESL (greenswitch): originate, check_sip_registrations, upload_call_record_to_crm
- `apps/telephony/api.py` — originate вызывает esl_originate(), webrtc_credentials возвращает sip_password
- `apps/contracts/services.py` — _send_sms(): sms.ru, smsc.ru провайдеры + stub fallback

### Файлы (Frontend):
- `frontend/src/api/crm.ts` — NEW: типизированный API-модуль CRM
- `frontend/src/api/telephony.ts` — NEW: типизированный API-модуль телефонии
- `frontend/src/views/CRMView.vue` — полный Kanban + контакты/компании/воронки CRUD
- `frontend/src/views/ContractsView.vue` — договоры + шаблоны + отправка на подпись + PDF
- `frontend/src/views/TelephonyView.vue` — 6 вкладок: звонки/транки/добавочные/IVR/очереди/софтфон
- `frontend/src/components/SoftPhone.vue` — реальная SIP.js интеграция (UserAgent, Registerer, Inviter)
- `frontend/src/views/DistributionView.vue` — добавлены edit/delete/toggle active
- Все 15 PDataTable: добавлен paginator :rows="20" :rowsPerPageOptions

### Валидация:
- `docker compose down` → `docker compose up -d --build` → все контейнеры up
- `docker compose run --rm web python manage.py check` → System check identified no issues
- `docker compose run --rm web python manage.py test apps.billing apps.channels apps.contracts apps.crm apps.distribution apps.telephony apps.integrations apps.tenants --verbosity=2` → Ran 25 tests OK
- `docker compose run --rm --no-deps frontend sh -lc "cd /app && npm run build"` → ✓ built in 4.20s, 0 errors

### Риски:
- amoCRM/Bitrix24 адаптеры тестировались только по контрактам API — end-to-end проверка требует реальных credentials
- SIP.js софтфон требует рабочий WSS endpoint FreeSWITCH для полноценной проверки
- SMS-провайдеры (sms.ru, smsc) требуют реальный API-ключ для production-проверки

---

## 2026-04-14 — Fix: CORS не пропускал заголовок X-Tenant-Slug
- **Файлы:**
  - `config/settings.py`
- **Что сделано:**
  - Обнаружена первопричина «не работает авторизация тестовых пользователей»: `django-cors-headers` без явного `CORS_ALLOW_HEADERS` использовал дефолтный набор, в который не входил `X-Tenant-Slug`. Браузер блокировал preflight для всех запросов с этим заголовком (`/auth/me`, все API после login).
  - Добавлен `CORS_ALLOW_HEADERS` в settings с полным списком стандартных заголовков + `x-tenant-slug`.
- **Валидация:**
  - `docker compose up -d --build web`
  - `docker compose run --rm web python manage.py check` → OK
  - CORS preflight: `OPTIONS /api/auth/me` с `Access-Control-Request-Headers: authorization,x-tenant-slug` → `access-control-allow-headers` теперь включает `x-tenant-slug`
  - `docker compose run --rm web python manage.py test apps.users.tests --verbosity 1` → `Ran 11 tests ... OK`
  - End-to-end curl: login → /auth/me с `Authorization` + `X-Tenant-Slug` → 200
- **Риски:** нет

## 2026-04-14 — Auth hardening: login по username/email + прозрачный отчёт `create_test_users`
- **Файлы:**
  - `apps/users/api.py`
  - `apps/users/tests/test_auth_api.py`
  - `apps/users/management/commands/create_test_users.py`
  - `frontend/src/views/LoginView.vue`
  - `docs/DECISIONS.md`, `docs/TASK_STATE.md`, `docs/RELEASE_NOTES.md`
- **Что сделано:**
  - `POST /api/auth/login` расширен: теперь принимает идентификатор как `login`/`email`/`username` и выполняет case-insensitive lookup (email/username) перед authenticate.
  - Добавлены auth-регрессии: вход по `username` и вход по email в другом регистре.
  - `create_test_users` больше не маскирует состояние паролей: выводит username в строке аккаунта, флаги `password:set/password:kept`, итоговую сводку синхронизации и явную команду для `--reset-password`.
  - На экране входа SPA поле логина обновлено до `Email или username`.
- **Валидация:**
  - `docker compose down`
  - `docker compose up -d --build`
  - `docker compose run --rm web python manage.py check`
  - `docker compose run --rm web python manage.py test apps.users.tests.test_auth_api apps.users.tests.test_create_test_users_command --verbosity 1` → `Ran 11 tests ... OK`
  - `docker compose run --rm web python manage.py create_test_users` → в отчёте отображаются `password:kept` и подсказка по `--reset-password`.
  - `docker compose run --rm web python manage.py shell -c "...login/me smoke..."` → `email-owner`, `username-owner`, `email-admin`, `username-admin` дают `login 200`, `me 200`.
  - `docker compose run --rm frontend sh -lc "npm install && npm run test && npm run build"` → frontend tests/build `OK`.
- **Риски:**
  - Если в БД уже существуют seed-аккаунты с неизвестными паролями, команда без `--reset-password` их не меняет (это осознанная политика); для унификации требуется явный запуск `--reset-password --password <значение>`.

## 2026-04-14 — Fix: «не авторизуются» (CORS + admin tenant-context)
- **Файлы:**
  - `apps/users/management/commands/create_test_users.py`
  - `apps/users/tests/test_create_test_users_command.py`
  - `.env`, `.env.example`
  - `docs/TASK_STATE.md`
- **Что сделано:**
  - Устранён блокер входа для `platform_admin`: в bootstrap-режиме команда теперь гарантирует membership `admin` в `org-crm`, поэтому login/me флоу в SPA проходит без ручного `X-Tenant-Slug`.
  - Расширен CORS для локальной разработки: добавлены origin-ы `localhost` и `127.0.0.1` для dev/prod frontend портов (`15173`/`14173`), чтобы вход не ломался при смене хоста в браузере.
  - Подтверждена политика паролей: смена паролей существующих пользователей только по явному `--reset-password`; default-пароль `Asdf2121` сохранён.
- **Валидация:**
  - `docker compose run --rm web python manage.py test apps.users.tests.test_create_test_users_command --verbosity 2` → `Ran 5 tests ... OK`
  - `docker compose run --rm web python manage.py create_test_users --reset-password --password Asdf2121` → bootstrap и синхронизация паролей выполнены.
  - Ручной login/me smoke: `owner_org-simple@example.com`, `manager_org-basic@example.com`, `platform_admin@example.com` с `Asdf2121` → `200/200`.
  - CORS preflight smoke: `http://localhost:15173`, `http://127.0.0.1:15173`, `http://localhost:14173`, `http://127.0.0.1:14173` → `Access-Control-Allow-Origin` присутствует.
- **Риски:**
  - При изменении frontend-портов необходимо синхронно обновлять `CORS_ALLOWED_ORIGINS` в `.env` конкретного инстанса.

## 2026-04-14 — Fix: контроль паролей тестовых пользователей в `create_test_users`
- **Файлы:**
  - `apps/users/management/commands/create_test_users.py`
  - `apps/users/tests/test_create_test_users_command.py`
  - `docs/TASK_STATE.md`
- **Что сделано:**
  - Найден источник невалидных логинов: при повторном запуске команды печатался текущий `--password`, но для существующих аккаунтов пароль оставался прежним.
  - Сохранена безопасная политика: пароли существующих пользователей меняются **только** при явном `--reset-password`.
  - Возвращён проектный default-пароль команды `Asdf2121`.
  - Добавлен регрессионный тест `test_command_does_not_reset_password_without_flag`.
- **Валидация:**
  - `docker compose run --rm web python manage.py test apps.users.tests.test_create_test_users_command --verbosity 2` → `Ran 5 tests ... OK`
  - `docker compose run --rm web python manage.py create_test_users` → без `--reset-password` пароли существующих пользователей не меняются.
  - `docker compose run --rm web python manage.py create_test_users --reset-password --password Asdf2121` → пароли пересинхронизируются на `Asdf2121`.
- **Риски:**
  - Для унификации паролей между окружениями требуется явный запуск с `--reset-password --password <value>`.

## 2026-04-14 — Параметризация host-портов Docker для параллельных инстансов
- **Файлы:**
  - `docker-compose.yml`
  - `.env`, `.env.example`
  - `frontend/src/api/http.ts`
  - `docs/DECISIONS.md`
- **Что сделано:**
  - Убраны жёстко зашитые порты из `docker-compose.yml`: публикации для `web/frontend/frontend-prod/db/redis/freeswitch` переведены на env-переменные с дефолтами.
  - В `.env` и `.env.example` добавлен блок `Host ports` с централизованной настройкой портов под конкретный инстанс проекта.
  - Синхронизированы platform/frontend URL переменные (`PLATFORM_DOMAIN`, `FRONTEND_APP_URL`, `VITE_API_URL`, `CORS_ALLOWED_ORIGINS`) с новым портовым профилем по умолчанию.
  - Обновлён fallback API URL во frontend-клиенте на новый backend-порт по умолчанию.
- **Валидация:**
  - `docker compose down`
  - `docker compose up -d --build`
  - `docker compose run --rm web python manage.py check`
  - `curl -I http://localhost:18100/` и `curl -I http://localhost:18100/healthz`
  - `curl -I http://localhost:15173/`
- **Риски:**
  - Для каждой новой копии проекта нужно задать собственный набор `*_HOST_PORT` в её `.env` (иначе конфликт с другой копией на тех же значениях).

## 2026-04-14 — Hardening bootstrap-режима `create_test_users` (без аргументов)
- **Файлы:**
  - `apps/users/management/commands/create_test_users.py`
  - `apps/users/tests/test_create_test_users_command.py`
  - `docs/TASK_STATE.md`
- **Что сделано:**
  - Команда `create_test_users` в режиме без аргументов переведена в канонический bootstrap: всегда обеспечивает 3 организации (`org-simple`, `org-basic`, `org-crm`) с тарифами `simple/basic/crm`, 6 пользователей (`owner` + `manager` на каждую организацию) и платформенного администратора.
  - Для уже существующих bootstrap tenant-ов добавлено приведение состояния к инвариантам seed-сценария: актуальный план, `is_active=True`, `crm_mode=builtin`, корректный primary-domain `<slug>.localhost`.
  - Исправлен консольный отчёт команды: статус manager-profile теперь детерминированно отображается как `created`/`updated`/`skipped` без ложного `skipped` при update.
  - Добавлен регрессионный автотест на reconcile-поведение для частично «сломанного» bootstrap tenant-а.
- **Валидация:**
  - `docker compose down`
  - `docker compose --profile frontend-prod down`
  - `DEBUG=False docker compose up -d --build`
  - `DEBUG=False docker compose run --rm web python manage.py check`
  - `DEBUG=False docker compose run --rm web python manage.py test apps.users.tests.test_create_test_users_command --verbosity 2` → `Ran 4 tests ... OK`
  - `docker compose run --rm web python manage.py create_test_users` → bootstrap seed отрабатывает без аргументов и печатает итоговую сводку.
  - `docker compose run --rm -e DEBUG=False web python manage.py create_test_users` → `CommandError` (guard на non-DEBUG без `--force` работает как ожидается).
  - `curl -I http://localhost:8000/` → `302`, `curl -I http://localhost:8000/healthz` → `200`.
- **Риски:**
  - Команда зависит от наличия активных seed-планов `simple/basic/crm` в `public` schema (если планы удалены вручную, bootstrap корректно завершится с `CommandError`).

## 2026-04-14 — Management-команда `create_test_users`
- **Файлы:**
  - `apps/users/management/commands/create_test_users.py`
  - `apps/users/tests/test_create_test_users_command.py`
  - `apps/users/management/__init__.py`, `apps/users/management/commands/__init__.py`
  - `docs/TASK_STATE.md`
- **Что сделано:**
  - Добавлена идемпотентная management-команда `create_test_users` для подготовки тестовых аккаунтов (`owner/admin/manager/viewer`) и memberships в выбранном tenant.
  - Добавлены безопасные опции: запрет запуска при `DEBUG=False` без явного `--force`, опциональное авто-создание tenant (`--create-tenant`) с планом и primary domain.
  - Добавлено создание/обновление `ManagerProfile` для менеджера (с опцией `--skip-manager-profile`).
  - Исправлена тестовая совместимость guard-логики команды: запуск разрешён в `manage.py test` без ослабления runtime-политики.
- **Валидация:**
  - `docker compose run --rm web python manage.py check`
  - `docker compose run --rm web python manage.py test apps.users.tests.test_create_test_users_command --verbosity 2` → `Ran 2 tests ... OK`
  - `docker compose run --rm web python manage.py create_test_users --tenant-slug demo --password qa_pass_123 --reset-password --force` → `OK`
- **Риски:**
  - В non-DEBUG окружении команда требует `--force`; это ожидаемое защитное поведение.

## 2026-04-14 — Публичный UX-контур и единый вход в продукт
- **Файлы:**
  - `frontend/src/views/LandingView.vue`, `frontend/src/views/RegisterView.vue`, `frontend/src/views/LoginView.vue`
  - `frontend/src/router/index.ts`, `frontend/src/router/guards.ts`, `frontend/src/layouts/SidebarNav.vue`
  - `frontend/src/stores/auth.ts`
  - `config/views.py`, `config/urls.py`, `config/settings.py`
  - `apps/users/api.py`, `apps/users/tests/test_auth_api.py`, `apps/tenants/tests/test_tenant_resolver.py`
  - `docker-compose.yml`, `.env`, `.env.example`, `AGENTS.md`
  - `docs/DECISIONS.md`, `docs/TASK_STATE.md`, `docs/RELEASE_NOTES.md`
- **Что сделано:**
  - Реализован полноценный публичный путь в SPA: посадочная (`/`), вход (`/login`) и регистрация организации (`/register`).
  - Личный кабинет перенесён в защищённый контур `/app`; добавлены redirect-маршруты для обратной совместимости со старыми URL.
  - Backend `localhost:8000` переведён в роль входной точки: `/`, `/login`, `/register`, `/app` перенаправляют на frontend (`FRONTEND_APP_URL`).
  - Исправлен системный баг регистрации: `POST /api/auth/register` теперь всегда работает в `public` schema, даже если запрос пришёл из tenant-контекста.
  - В `docker-compose` frontend переведён в default stack (без profile), чтобы UI поднимался вместе с backend одной командой.
- **Валидация:**
  - `docker compose down`
  - `docker compose up -d --build`
  - `docker compose run --rm web python manage.py check`
  - `docker compose run --rm web python manage.py test apps.users.tests.test_auth_api apps.tenants.tests.test_tenant_resolver --verbosity 2`
  - `docker compose run --rm web python manage.py test apps.users apps.tenants apps.contracts apps.integrations apps.telephony apps.crm apps.audit apps.notifications apps.distribution apps.channels` → `Ran 34 tests ... OK`
  - `docker compose run --rm frontend sh -lc "npm install && npm run test && npm run build"` → `OK`
  - Manual HTTP:
    - `curl -I http://localhost:8000/` → `302` (`Location: http://localhost:5173`)
    - `curl -I http://localhost:8000/login` → `302` (`.../login`)
    - `curl -I http://localhost:8000/register` → `302` (`.../register`)
    - `curl -I http://localhost:5173/` → `200`
    - `curl -I http://localhost:5173/login` → `200`
    - `curl -I http://localhost:5173/register` → `200`
    - e2e smoke регистрации/авторизации через API: `register 201` + `auth/me 200`
- **Риски:**
  - В текущем виде backend root зависит от доступности frontend URL (`FRONTEND_APP_URL`) для пользовательского входа.

## 2026-04-14 — Явный root endpoint backend (исправление 404 на `/`)
- **Файлы:**
  - `config/views.py`, `config/urls.py`
  - `apps/tenants/tests/test_tenant_resolver.py`
  - `docs/DECISIONS.md`, `docs/RELEASE_NOTES.md`
- **Что сделано:**
  - Добавлен маршрут `GET /` с JSON-ответом `200` (`status`, `service`, ссылки на `/healthz` и `/api/`).
  - Добавлен регрессионный тест на root endpoint.
- **Валидация:**
  - `docker compose run --rm web python manage.py test apps.tenants.tests.test_tenant_resolver --verbosity 2` → `OK`
  - `curl -I http://localhost:8000/` → `200`
  - `curl -I http://localhost:8000/healthz` → `200`
- **Риски:**
  - Отсутствуют, изменение ограничено диагностическим публичным endpoint.

## 2026-04-14 — Введение и стабилизация автотестов (backend + frontend)
- **Файлы:**
  - `apps/users/tests/base.py`
  - `apps/users/tests/test_auth_api.py`
  - `apps/tenants/tests/test_tenant_resolver.py`
  - `apps/contracts/tests/test_signing_flow.py`, `apps/contracts/tests/test_contract_limits.py`, `apps/contracts/api.py`
  - `apps/integrations/tests/test_webhook_auth.py`
  - `apps/telephony/tests/test_public_endpoints.py`
  - `apps/crm/tests/test_auto_actions.py`, `apps/crm/tests/test_dashboard_api.py`
  - `apps/audit/tests/test_permissions.py`
  - `apps/notifications/tests/test_preferences_permissions.py`
  - `apps/distribution/tests/test_assignment.py`
  - `apps/channels/tests/test_bridge.py`
  - `frontend/src/api/http.test.ts`, `frontend/package.json`
  - `docs/TASK_STATE.md`, `docs/KNOWN_ISSUES.md`
- **Что сделано:**
  - Добавлен базовый набор автотестов по критичным бизнес-потокам backend (auth, tenant-resolver, contracts signing/limits, integrations webhook auth, telephony public endpoints, CRM auto-actions/dashboard, audit, notifications, distribution, channels).
  - Добавлены frontend unit-тесты API-клиента (JWT + `X-Tenant-Slug` headers и runtime persistence tenant slug).
  - Системно устранена флаки-ошибка tenant-контекста в тестах: в общем `TenantAPITestCase` закреплена установка tenant schema перед каждым тестом и перед flush (`_fixture_teardown`), helper `create_manager_profile` переведён в `tenant_context`.
  - Исправлен API-контракт `POST /api/contracts/generate`: добавлена явная схема ответа для `400`, устранён `ninja ConfigError` при проверке месячного лимита.
- **Валидация:**
  - `docker compose run --rm web python manage.py test apps.contracts.tests.test_contract_limits apps.integrations.tests.test_webhook_auth apps.telephony.tests.test_public_endpoints --verbosity 2`
  - `docker compose run --rm web python manage.py test apps.users apps.tenants apps.contracts apps.integrations apps.telephony apps.crm apps.audit apps.notifications apps.distribution apps.channels --verbosity 2` → `Ran 31 tests ... OK`
  - `docker compose run --rm frontend sh -lc "npm install && npm run test"` → `1 file, 2 tests, OK`
- **Риски:**
  - Пока отсутствуют e2e UI-тесты и нагрузочные проверки, покрытие ограничено smoke/integration и unit-уровнем.

## 2026-04-14 — Системный hardening API/tenant-context + runtime стабилизация
- **Файлы:**
  - `apps/core/tenant.py`, `apps/core/middleware.py`, `apps/core/access.py`, `config/settings.py`
  - `config/__init__.py`
  - `apps/users/api.py`, `apps/tenants/api.py`, `apps/tenants/onboarding_api.py`
  - `apps/integrations/api.py`, `apps/integrations/webhook_views.py`
  - `apps/channels/api.py`
  - `apps/contracts/api.py`, `apps/contracts/services.py`
  - `apps/crm/api.py`, `apps/crm/services/auto_actions.py`
  - `apps/billing/guards.py`, `apps/billing/tasks.py`
  - `apps/audit/api.py`, `apps/notifications/api.py`, `apps/telephony/api.py`
  - `frontend/src/api/http.ts`, `frontend/src/api/auth.ts`, `frontend/src/stores/auth.ts`, `frontend/src/stores/tenant.ts`
  - `docs/DECISIONS.md`, `docs/TASK_STATE.md`, `docs/KNOWN_ISSUES.md`, `docs/RELEASE_NOTES.md`
- **Что сделано:**
  - Добавлен централизованный tenant-resolver с middleware и fallback-поведением для `localhost` + поддержкой `X-Tenant-Slug`.
  - Исправлен критичный runtime-кейс Celery: подключён `celery_app` в `config/__init__.py`, устранены падения при `task.delay()` из web-процесса.
  - Нормализованы API-ответы create endpoint-ов: убраны неописанные `201`, которые приводили к `django-ninja ConfigError`.
  - Исправлен контрактный поток подписания: корректная привязка signing token к tenant в shared schema.
  - Усилены guards/permissions: role-check на audit/preferences/test notification; более безопасная webhook-подпись amoCRM.
  - Внедрён tenant header на фронте (persist в localStorage), синхронизация slug в auth/tenant сторе.
  - Приведён расчёт лимитов `max_contracts_per_month` к месячному окну (API и фоновые проверки).
  - Исправлена авто-задача CRM stage action (`created_by` у task теперь вычисляется корректно, без обращения к несуществующему полю `Deal.created_by`).
- **Валидация:**
  - `docker compose down`
  - `docker compose --profile frontend --profile frontend-prod down`
  - `docker compose up -d --build`
  - `docker compose run --rm web python manage.py check`
  - Targeted smoke (через Django test client в контейнере web):
    - auth/me/tenant/dashboard на `localhost` с `X-Tenant-Slug`
    - contracts template/generate/send-for-signing/sign verify
    - integrations/distribution/channels create flows
    - telephony/crm create flows
  - Frontend:
    - `docker compose --profile frontend up -d frontend`
    - `docker compose logs frontend --tail=80` (Vite ready, без ошибок)
    - `docker compose --profile frontend-prod up -d --build frontend-prod`
  - Manual HTTP:
    - `curl -I http://localhost:8000/healthz` → 200
    - `curl -I http://localhost:5173/` → 200
    - `curl -I http://localhost:4173/` → 200
- **Риски:**
  - Для multi-tenant локальной разработки на одном host требуется явный `X-Tenant-Slug`.
  - Автотесты по-прежнему отсутствуют; smoke-сценарии пока выполняются вручную/скриптами.

## 2026-04-13 — Полная реализация v1: backend+frontend+docker
- **Файлы:**
  - `apps/billing/migrations/0002_seed_default_plans.py`, `apps/billing/tasks.py`
  - `apps/channels/public_views.py`, `apps/channels/tasks.py`, `apps/channels/api.py`
  - `apps/telephony/public_views.py`, `apps/telephony/tasks.py`, `apps/telephony/api.py`
  - `apps/integrations/adapters_amocrm.py`, `apps/integrations/adapters_bitrix24.py`, `apps/integrations/webhook_views.py`
  - `apps/notifications/services.py`, `apps/notifications/consumers.py`, `apps/notifications/api.py`
  - `apps/users/api.py`, `apps/audit/services.py`
  - `apps/core/channels_auth.py`, `config/asgi.py`, `config/urls.py`, `config/settings.py`, `docker-compose.yml`, `Dockerfile.frontend`, `frontend/nginx.conf`
  - `frontend/*` (полная SPA-структура: router, stores, composables, layouts, views, components, api-клиент)
  - `.env`, `.env.example`, `docs/*`
- **Что сделано:**
  - Устранён критический runtime-блокер роутинга (`Router.urls`) и внедрён корректный публичный URL-слой.
  - Добавлена WebSocket JWT-аутентификация и персональные realtime-каналы уведомлений.
  - Реализован seed тарифов/фич и плановые Celery-задачи (лимиты/CRM health/SIP/overdue/signing expiration).
  - CRM-адаптеры переведены со stub-исключений на рабочие HTTP/fallback реализации.
  - Полностью инициализирован frontend SPA (Vue 3 + PrimeVue + Pinia + Router + guards + страницы + feature-gate).
  - Добавлен production frontend delivery (`Dockerfile.frontend`, nginx runtime, `frontend-prod` профиль).
- **Валидация:**
  - `docker compose --profile frontend --profile frontend-prod down`
  - `docker compose down`
  - `docker compose up -d --build`
  - `docker compose run --rm web python manage.py check`
  - `docker compose run --rm web python manage.py migrate_schemas --shared --noinput`
  - `docker compose run --rm web python manage.py test apps.users apps.tenants apps.billing apps.notifications apps.distribution apps.contracts apps.crm apps.integrations apps.telephony apps.channels` (0 tests, без ошибок)
  - `docker compose --profile frontend up -d frontend` + `docker compose logs frontend --tail=80` (Vite ready)
  - `docker compose --profile frontend-prod up -d --build frontend-prod` + `curl -I http://localhost:4173/` (200)
  - `curl -I http://localhost:8000/healthz` (200)
- **Риски:**
  - Для реальной эксплуатации внешних интеграций нужны боевые credentials и product-specific mapping/валидация.
  - FreeSWITCH-профиль остаётся экспериментальным до отдельной платформенной обкатки (особенно ARM).
  - Автотесты предметной логики ещё не покрывают новый функционал (в проекте пока отсутствует набор unit/integration тестов).

## 2026-04-13 — Стабилизация запуска Docker + Django bootstrap
- **Файлы:**
  - `docker-compose.yml` (healthchecks, `migrate` service, `depends_on` gates, optional profiles `frontend/telephony`)
  - `requirements.txt` (совместимая версия `redis` для `celery/kombu`)
  - `config/asgi.py`, `config/routing.py` (корректный ASGI bootstrap для HTTP+WebSocket)
  - `config/settings.py` (`SHOW_PUBLIC_IF_NO_TENANT_FOUND` для dev-bootstrap)
  - `apps/users/api.py` (корректные response-схемы для error-веток auth)
  - `apps/integrations/adapters_amocrm.py`, `apps/integrations/adapters_bitrix24.py` (явные stub-адаптеры вместо падения на импорте)
  - `apps/*/migrations/*.py` (инициализированы миграции для всех проектных приложений)
- **Что сделано:**
  - Устранён конфликт зависимостей, блокировавший сборку контейнеров.
  - Убрана рекурсивная/некорректная ASGI-конфигурация, из-за которой HTTP/WS bootstrap был нестабильным.
  - В Docker добавлен обязательный миграционный шаг перед стартом приложений.
  - Базовый запуск отделён от незавершённых подсистем (frontend и telephony через profiles).
  - Исправлен старт API на чистой БД: таблицы создаются автоматически, `/api/healthz` отвечает.
- **Валидация:**
  - `docker compose down`
  - `docker compose up -d --build`
  - `docker compose run --rm web python manage.py check`
  - `docker compose run --rm web python manage.py test apps.users apps.tenants apps.billing` (0 tests, без ошибок)
  - `docker compose exec -T web sh -lc "python -c '.../api/healthz...'"` → `200 {"status": "ok"}`
- **Риски:**
  - Реальные интеграции amoCRM/Bitrix24 пока не реализованы (stub-адаптеры, `NotImplementedError`).
  - FreeSWITCH в `telephony` профиле требует отдельной платформенной валидации (на ARM возможна нестабильность).

## 2026-04-13 — Инициализация проекта (Этап 1: Каркас)
- **Файлы:** Весь скелет проекта
  - config/ (settings, urls, api, celery, routing, asgi, wsgi)
  - apps/tenants (models, admin, api)
  - apps/billing (models, admin, api, guards)
  - apps/users (models, admin, api — auth + users management)
  - apps/audit (models, admin, api, services)
  - apps/notifications (models, admin, api)
  - apps/contracts (models, admin)
  - apps/distribution (models, admin)
  - apps/integrations (models, admin, adapters protocol)
  - apps/channels (models, admin)
  - apps/telephony (models, admin)
  - apps/crm (models, admin, adapter)
  - apps/core/fields.py (EncryptedJSONField)
  - Dockerfile, docker-compose.yml, requirements.txt, .env
  - docs/, AGENTS.md
- **Что сделано:** Полный скелет Django-проекта с django-tenants, все модели из спецификации, API endpoints (auth, tenant, users, billing, audit, notifications), Docker конфигурация
- **Валидация:** Ожидает docker compose build + manage.py check
- **Риски:** Нет

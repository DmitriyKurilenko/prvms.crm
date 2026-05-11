# Архитектурные решения

## DEC-001: Schema-based мульти-тенантность (2026-04-13)
**Контекст:** Нужна изоляция данных между организациями.
**Решение:** Используем django-tenants с отдельной PostgreSQL schema на каждую организацию.
**Последствия:** Shared модели (User, Membership, Plan, Feature) в public schema. Бизнес-данные в tenant schema. Роутинг по домену.

## DEC-002: SPA + API архитектура (2026-04-13)
**Контекст:** ЛК организации — интерактивное приложение с Kanban, WebRTC, real-time.
**Решение:** Vue 3 SPA (frontend/) + Django API (django-ninja). Django templates только для публичных страниц (signing, admin).
**Последствия:** JWT-аутентификация (access в памяти, refresh в httpOnly cookie). CORS для dev. Nginx в production.

## DEC-003: CRM-режимы тенанта (2026-04-13)
**Контекст:** Организации могут использовать внешнюю CRM (Bitrix24, amoCRM) или встроенную.
**Решение:** Tenant.crm_mode + CRMAdapter protocol. BuiltinCRMAdapter работает через ORM, внешние — через HTTP.
**Последствия:** Единый интерфейс для всех подсистем (распределение, договоры, мессенджеры, телефония).

## DEC-004: Feature-gating через Plan + Feature (2026-04-13)
**Контекст:** Разные тарифы дают доступ к разным функциям.
**Решение:** M2M Plan↔Feature + декоратор require_feature + composable useFeatureGate на фронте.
**Последствия:** Новые функции добавляются через Django Admin без деплоя.

## DEC-005: Детерминированный Docker bootstrap (2026-04-13)
**Контекст:** Проект должен запускаться одной командой на чистой БД, без ручных шагов и падений при старте.
**Решение:** Добавлен одноразовый сервис `migrate`, от которого зависят `web/celery/celery-beat`; `frontend` и `freeswitch` переведены в опциональные профили (`frontend`, `telephony`); для dev включён fallback на `public` schema при неизвестном домене.
**Последствия:** Базовый backend-стек поднимается воспроизводимо, health-check доступен до создания первого tenant/domain, незавершённые подсистемы не ломают старт по умолчанию.

## DEC-006: Публичные endpoint-ы и WS-аутентификация отделены от API-роутеров (2026-04-13)
**Контекст:** Публичные маршруты (`/channels/webhook/...`, `/telephony/...`) были подключены через `django-ninja Router`, что ломало URL bootstrap и запуск мигратора; WebSocket не имел tenant/user-безопасности.
**Решение:** Публичные endpoint-ы переведены в обычные Django view и подключены напрямую в `config/urls.py`; для `/ws/notifications/` добавлена JWT-аутентификация через query-token и персональные каналы `notifications.user.<id>`.

## DEC-A01: Presence tracking через Redis + WebSocket heartbeat (2026-04-18)
**Контекст:** Нужен live-счётчик «менеджеров онлайн» без дополнительной инфраструктуры. WebSocket notifications consumer уже есть, Redis уже задействован для channel layers.
**Решение:** При WS-подключении пишем ключ `presence:{schema}:{user_id}` в Redis c TTL 90s; asyncio-задача внутри consumer обновляет ключ каждые 45s; при disconnect — удаляем. Endpoint `GET /dashboard/managers-online/` сканирует ключи по префиксу + пересекает с active Membership.
**Последствия:** Нет новых сервисов. Изоляция тенантов — через prefix с schema_name. При падении WS ключ истекает через 90s автоматически.

## DEC-A02: Tenant branding — CSS var + Intl (2026-04-18)
**Контекст:** Логотип, цвет бренда, таймзона и язык хранятся в TenantInfo, но нигде не применялись в UI.
**Решение:** `applyBrandColor` устанавливает `--brand` CSS-переменную на `documentElement` при загрузке/сохранении тенанта. Datetime util использует `Intl.DateTimeFormat` с `tenant.timezone` и LOCALE_MAP[tenant.language]. Язык передаётся через `Accept-Language` header. Полный vue-i18n не добавляется.
**Последствия:** Все форматы дат в SPA учитывают TZ и язык организации. Backend получает корректный `Accept-Language` для системных сообщений Django.

## DEC-007: Signing flow — OTP на стороне клиента (2026-04-14)
**Контекст:** Первоначально OTP генерировался и отправлялся при нажатии «Отправить на подпись» в CRM. Менеджер видел OTP и должен был вводить его сам — это нарушало logику подписания.
**Решение:** CRM только создаёт сессию и возвращает ссылку. OTP запрашивается клиентом с публичной страницы через `POST /sign/{token}/request-otp/`. Менеджер не видит OTP.
**Последствия:** Два этапа на публичной странице: «Получить код» → ввод кода. В CRM отображается только ссылка с кнопкой копирования.
**Последствия:** Корневой роутинг соответствует спецификации, bootstrap стабильный, realtime-уведомления доступны только авторизованному пользователю.

## DEC-007a: Дефолтные планы/фичи и полноценный frontend delivery в Docker (2026-04-13)
**Контекст:** Без seed-данных тарифов регистрация организации зависела от ручной подготовки БД; frontend отсутствовал как приложение и production-сборка.
**Решение:** Добавлена миграция seed для `Feature`/`Plan` (`simple/basic/crm`), инициализировано полноценное SPA (`frontend/`) и добавлен production Docker-путь (`Dockerfile.frontend` + `frontend-prod` сервис через nginx).
**Последствия:** Новый инстанс платформы стартует сразу с рабочими тарифами и доступным UI как в dev (`frontend`), так и в production-профиле (`frontend-prod`).

## DEC-008: Единый tenant-resolver для API на localhost и multi-domain (2026-04-14)
**Контекст:** При обращении SPA к `localhost:8000` часть API-запросов выполнялась без tenant-контекста, что приводило к 500 на `auth/me`, `tenant/*` и смежных endpoint-ах.
**Решение:** Добавлен централизованный resolver (`apps/core/tenant.py`) + middleware (`EnsureTenantContextMiddleware`) с поддержкой `X-Tenant-Slug`, fallback на `*.localhost` и dev-single-tenant режим.
**Последствия:** API стабильно работает как в доменной схеме (`tenant.domain`), так и в локальном режиме с единым host; tenant-контекст определяется детерминированно.

## DEC-009: Нормализация контрактов ответов API (2026-04-14)
**Контекст:** Ряд POST endpoint-ов возвращал HTTP 201 без объявленной response-схемы в django-ninja, что вызывало runtime 500.
**Решение:** Создан единый инвариант: endpoint-ы без явной response-карты возвращают 200 с телом результата; 201 оставлен только там, где он явно описан в `response={...}`.
**Последствия:** Исключены падения из-за несовпадения кода статуса и схемы ответа; smoke-сценарии создания сущностей выполняются без ошибок.

## DEC-010: Инициализация Celery app через `config/__init__.py` (2026-04-14)
**Контекст:** В Django-процессе вызовы `task.delay()` могли использовать default Celery app (AMQP), что ломало публичные сценарии (например, verify signing) при отправке задач.
**Решение:** Подключён `celery_app` в `config/__init__.py`, чтобы web/worker использовали единый broker/backend из `settings`.
**Последствия:** Фоновые задачи из web-процесса публикуются в Redis корректно; публичные пользовательские потоки не зависят от ручной настройки default Celery app.

## DEC-011: Явный root endpoint для backend-сервиса (2026-04-14)
**Контекст:** Адрес `http://localhost:8000/` возвращал `404`, что воспринималось как неготовность сервиса, несмотря на рабочие health/API маршруты.
**Решение:** `GET /` и короткие маршруты `/login`, `/register`, `/app` выполняют redirect на frontend (`FRONTEND_APP_URL`).
**Последствия:** Единая точка входа через `localhost:8000` открывает пользовательский интерфейс, а не технический JSON.

## DEC-012: Публичный UX-контур SPA (landing + registration + app shell) (2026-04-14)
**Контекст:** В SPA отсутствовал явный публичный входной слой (посадочная/регистрация), а ЛК был привязан к `/`, что усложняло старт новым пользователям.
**Решение:** Добавлены публичные маршруты SPA (`/`, `/login`, `/register`), защищённый shell перенесён на `/app`, оставлены redirect-маршруты обратной совместимости со старых путей.
**Последствия:** Пользовательский путь стал линейным: landing → регистрация/вход → ЛК; риск «пустого старта» для нового инстанса устранён.

## DEC-013: Параметризованные host-порты Docker для параллельного запуска (2026-04-14)
**Контекст:** Фиксированные host-порты (`8000/5173/5432/6379/...`) мешают поднимать несколько однотипных проектов на одной машине без ручного редактирования compose-файла.
**Решение:** Все внешние публикации портов в `docker-compose.yml` переведены на переменные (`WEB_HOST_PORT`, `FRONTEND_DEV_HOST_PORT`, `FRONTEND_PROD_HOST_PORT`, `DB_HOST_PORT`, `REDIS_HOST_PORT`, и telephony-порты), а `.env/.env.example` содержат явные значения по умолчанию.
**Последствия:** Параллельный запуск нескольких копий сводится к изменению только переменных в `.env` каждой копии; compose-структура остается неизменной.

## DEC-014: Bootstrap-админ должен иметь tenant-контекст для SPA (2026-04-14)
**Контекст:** `platform_admin` без membership не мог пройти пользовательский SPA login flow (`/auth/login` → `/auth/me`) в multi-tenant режиме, так как отсутствовал `tenant_slug`.
**Решение:** В bootstrap-сценарии `create_test_users` платформенному администратору автоматически обеспечивается active membership (`admin`) в `org-crm`.
**Последствия:** Технический админ-аккаунт остаётся суперпользователем платформы и одновременно пригоден для стандартного входа в ЛК без ручных заголовков tenant-контекста.

## DEC-015: Авторизация допускает email и username; seed-команда не маскирует состояние паролей (2026-04-14)
**Контекст:** В реальной эксплуатации вход ломался из-за двух UX-источников ошибок: пользователи вводили username вместо email, а `create_test_users` в режиме без `--reset-password` мог визуально создавать ложное ощущение, что пароль уже синхронизирован.
**Решение:** `POST /api/auth/login` принимает идентификатор как `login`/`email`/`username` (case-insensitive lookup, с приведением к каноническому email для backend authenticate). `create_test_users` теперь в отчёте явно показывает `password:set`/`password:kept`, печатает username рядом с email и отдельный итог по синхронизации паролей с явной командой для `--reset-password`.
**Последствия:** Снижается доля ложных отказов входа и исключается операторская ошибка «команда отработала, но пароль фактически не менялся»; bootstrap-данные становятся детерминированно интерпретируемыми по консольному выводу.

## DEC-016: Пробный период и модуль оплаты (2026-04-14)
**Контекст:** Регистрация давала полный доступ без ограничений — любой мог получить CRM-план бесплатно навсегда. Платёжного контура не существовало.
**Решение:** Добавлен 7-дневный пробный период при регистрации (`trial_expires_at`). Поле `is_paid` на Tenant определяет оплаченный доступ. Модель `Payment` в billing хранит платежи. Access guards (`require_roles`, `require_feature_access`) возвращают HTTP 402 при истечении триала без оплаты. Frontend: баннер триала, план-селектор при регистрации, страница подписки с checkout/history.
**Интеграция ЮKassa:** `POST /billing/checkout/` создаёт реальный платёж через YooKassa API (Python SDK `yookassa==3.10.0`), возвращает `confirmation_url` — пользователь перенаправляется на страницу оплаты ЮKassa. Webhook `POST /billing/yookassa/webhook/` принимает уведомления `payment.succeeded`/`payment.canceled`, активирует подписку или отменяет платёж. Настройки: `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `YOOKASSA_RETURN_URL` через env.
**Последствия:** Бесплатный доступ ограничен 7 днями. Смена плана возможна только во время триала. После оплаты триал снимается. Публичный endpoint `/billing/plans/` доступен без авторизации для страницы регистрации. Ручное подтверждение через Django Admin сохранено как admin override.

## DEC-017: CRM — ответственный привязан к User, а не к ManagerProfile (2026-04-15)
**Контекст:** FK `responsible` в CRM-моделях (Deal, Activity, Contact, Company) ссылался на `integrations.ManagerProfile`. Это означало, что только пользователь с профилем менеджера мог быть назначен ответственным — обычные участники организации (admin, owner) не попадали в список.
**Решение:** FK `responsible` переведён на `users.User`. Endpoint `GET /crm/managers/` возвращает всех активных участников организации через `Membership` (кроме viewer). Data-миграция переводит существующие ManagerProfile.id → User.id.
**Последствия:** Любой активный участник организации (owner, admin, manager) может быть назначен ответственным в CRM. Задачи, созданные триггерами, корректно отображаются во вкладке «Мои задачи» ответственного. ManagerProfile сохранён для distribution/telephony (schedule, max_active_deals, SIP extensions).

## DEC-018: Простая электронная подпись (ПЭП) для договоров (2026-04-16)
**Контекст:** Подписанные договоры не имели криптографической защиты — статус «подписан» менялся только в БД без привязки к содержимому документа.
**Решение:** Реализована простая электронная подпись (ПЭП) по 63-ФЗ. При создании контракта вычисляется SHA-256 хеш PDF-файла (`Contract.pdf_hash`). При подписании создаётся HMAC-SHA256 подпись, включающая хеш документа, данные подписанта (телефон, IP, User-Agent), timestamp и ID сессии (`Contract.signature_data` JSONField). OTP генерируется через `secrets` (криптографически безопасно).
**Последствия:** Документ получает юридическую значимость в рамках ПЭП. При проверке можно верифицировать: а) целостность PDF (сравнение хешей), б) подлинность подписи (HMAC через SECRET_KEY). Для усиленной подписи (УНЭП/УКЭП) потребуется интеграция с CryptoPro или аналогом — это отложено на production-hardening.

## DEC-019: Real-time чаты через Django Channels, не polling (2026-04-15)
**Контекст:** Мессенджер-каналы требуют обновления сообщений в реальном времени. Инфраструктура Django Channels + Redis channel layer уже развёрнута (DEC-006). Polling через setInterval — костыль, противоречащий стеку проекта.
**Решение:** `ChatConsumer` (AsyncJsonWebsocketConsumer) на `ws/chat/?token=...&slug=...`. JWT-аутентификация + tenant slug через query params в `JWTQueryAuthMiddleware`. Celery-задачи (`route_incoming_message`, `route_outgoing_message`) после создания `MessageLog` делают `channel_layer.group_send` для push-доставки.
**Инвариант:** Группы WS включают tenant slug: `chat.{tenant_slug}.channel.{channel_id}`. Это обеспечивает изоляцию между тенантами — channel_id уникален только внутри tenant schema.
**Последствия:** Никакого polling. Сообщения доставляются мгновенно через WS. При отсутствии slug в query WS-соединение отклоняется (code 4400).

## DEC-020: MAX мессенджер — полноценная интеграция через Bot API (2026-04-15)
**Контекст:** MAX-канал был реализован как заглушка с полем `send_url` — без реального API. MAX Bot API (`platform-api.max.ru`) предоставляет стандартные эндпоинты: `POST /subscriptions` (webhook), `POST /messages` (отправка), авторизация через `Authorization: <token>` header, верификация webhook через `X-Max-Bot-Api-Secret`.
**Решение:** Реализована полноценная интеграция по аналогии с Telegram: `register_max_webhook()` / `unregister_max_webhook()` / `get_max_webhook_info()` в `providers.py`. Авто-регистрация webhook при создании/редактировании канала. Отправка через `POST /messages?chat_id=`. Нормализация входящих `message_created` update-ов. Валидация `X-Max-Bot-Api-Secret` в webhook handler.
**Последствия:** MAX-канал работает по тому же паттерну, что и Telegram: `bot_token` в credentials → авто-регистрация webhook → приём/отправка сообщений → real-time через WS.

## DEC-021: Multi-org доступ только через активное membership + безопасное принятие приглашений (2026-04-16)
**Контекст:** Пользователь может состоять в нескольких организациях, но в API не хватало стандартного способа выбора активной организации. Дополнительно принятие приглашения для существующего аккаунта могло происходить без подтверждения владения аккаунтом.
**Решение:**
- Добавлены endpoint-ы `GET /api/auth/organizations` (список доступных организаций пользователя) и `POST /api/auth/switch-tenant` (переключение активной организации).
- В SPA (TopBar) добавлен переключатель организаций.
- `tenant_slug` по умолчанию теперь определяется только из активных **joined** membership (`invite_token IS NULL` и `joined_at IS NOT NULL`), чтобы pending-приглашения не подменяли рабочий tenant.
- Принятие приглашения для существующего аккаунта требует подтверждения пароля этого аккаунта.
- Для tenant-scoped API введён централизованный guard `require_membership`; `tenant` и `notifications` endpoint-ы теперь явно требуют активное membership.
**Последствия:** Исключены неявные переходы между tenant-ами и сценарии доступа к tenant-контексту без membership; мульти-организационный сценарий стал предсказуемым и безопасным.

## DEC-022: Онбординг-шаг менеджеров создаёт реальные приглашения (2026-04-16)
**Контекст:** На шаге 3 онбординга менеджеры добавлялись только как `User`/`ManagerProfile` без pending membership и invite-токена. В результате приглашение “в онбординге” фактически не работало. Дополнительно legacy-пользователи с пустым паролем (`password=''`) ошибочно считались существующими аккаунтами.
**Решение:**
- Шаг 3 онбординга теперь создаёт/обновляет pending `Membership` (role=`manager`, `invite_token`, `invited_at`) и отправляет письмо с invite-ссылкой.
- Для новых пользователей в онбординге используется `create_user(..., password=None)` (unusable password), а не `get_or_create` с пустым паролем.
- В invite-check/accept добавлена защита от legacy-состояния: пользователь с `password=''` трактуется как “без аккаунта” и проходит через установку нового пароля.
**Последствия:** Приглашения из онбординга и из раздела “Команда” работают одинаково: пользователь получает ссылку, открывает `/invite/accept`, задаёт пароль (если аккаунта ещё нет) и корректно вступает в организацию.

## DEC-023: Granular RBAC для CRM-сущностей (2026-04-16)
**Контекст:** Ролевой контроль в CRM был зашит в endpoint-ы через `require_roles`, что не покрывало granular права и область видимости данных (`all/team/own`) для сделок, контактов и компаний.
**Решение:**
- В public schema добавлена модель `users.RolePermission` (`tenant + role + entity`) с флагами `can_view/create/update/delete` и `scope`.
- Добавлены безопасные дефолты по ролям (`owner/admin` — полный доступ, `manager` — CRUD без delete, `viewer` — read-only), с ленивым автодосозданием матрицы для существующих tenant-ов.
- В `apps/core/access.py` добавлены централизованные helper-ы: проверка granular permissions, scope-фильтрация queryset, object-level guard, валидация/нормализация `responsible_id` на запись.
- CRM endpoint-ы `deals/contacts/companies` переведены на новую permission-модель (403 при запрете, scope-aware выборка/изменение).
- Добавлены API управления матрицей прав: `GET /api/users/role-permissions/`, `PATCH /api/users/role-permissions/{role}/{entity}/`; `GET /api/auth/me` теперь возвращает `crm_permissions`.
- Frontend: в `TeamView` добавлена вкладка «Права ролей», в `CRMView` actions скрываются/блокируются по текущим permission-ам.
- Изменения роли и матрицы прав логируются в аудит.
**Последствия:** Контроль доступа к CRM-сущностям стал конфигурируемым на уровне роли и tenant-а; поддержан multi-org сценарий с разными матрицами прав в разных организациях для одного пользователя.

## DEC-024: External CRM integrations — marketplace-first UX + статусный контур (2026-04-16)
**Контекст:** Базовые OAuth/webhook endpoint-ы существовали, но для пользователя интеграция выглядела «технической»: не хватало one-click установки из маркетплейса, прозрачных статусов, теста подключения и человеческого error-log.
**Решение:**
- Добавлен двухконтурный setup во внешних CRM: «Рекомендуемый (marketplace/OAuth)» и «Быстрый старт (webhook/manual)».
- Реализованы endpoint-ы marketplace-start для amoCRM/Битрикс24 с tenant-bound `state`.
- OAuth callback расширен автоконфигурацией: default webhook, запуск sync менеджеров и health-check.
- Введён единый статус интеграции (`working / requires_authorization / webhook_error / insufficient_scope / error / disabled`) + scope-валидация.
- Добавлен пользовательский журнал ошибок (`IntegrationErrorLog`) с кодом, понятным описанием и шагом исправления.
- Добавлены endpoint-ы `test` (connection + webhook probe) и `reconnect` (автовосстановление OAuth токенов).
- Усилен webhook pipeline: фиксация последнего успешного входящего webhook и логирование auth-ошибок.
- Синхронизация менеджеров исправлена до production-поведения: создаются/связываются `User` + `Membership` в tenant-контуре.
**Последствия:** Интеграции с внешними CRM стали управляемыми и диагностируемыми из UI без «ручной отладки в коде»; multi-org/tenant инвариант сохранён для marketplace и webhook потоков.

## DEC-025: Пользовательская справка как bundled markdown без runtime-зависимостей (2026-04-18)
**Контекст:** Нужен встроенный раздел «Помощь» с пошаговыми инструкциями для пользователей ЛК. Добавлять runtime-зависимость (`marked`/`markdown-it`) ради статичного набора статей — избыточно; хранить контент в двух местах (репо-документация + assets фронта) — риск расхождения.
**Решение:**
- Источник правды — `docs/user-guide/*.md` в корне репо. Файлы содержат только пользовательские формулировки (без имён функций/URL/route-имён/codename прав).
- SPA подгружает те же md через Vite `import.meta.glob('@/docs/user-guide/*.md', { query: '?raw', eager: true })` — статьи бандлятся в build-time, без fetch в рантайме.
- Docker-контейнер `frontend` монтирует только `./frontend` → `/app`, поэтому симлинк внутри `src/` за пределы монтируемой директории не работает. Используется отдельный volume: `./docs/user-guide:/app/src/docs/user-guide:ro`. На хосте `frontend/src/docs/user-guide/` — обычная пустая директория (placeholder).
- Рендер делает свой `frontend/src/utils/markdown.ts` (~50 строк): headings с slug-id (unicode `\p{L}\p{N}` для кириллицы), списки, параграфы, inline-код, bold/italic, ссылки, `<hr/>`. Внешние ссылки получают `target="_blank" rel="noopener"`.
**Последствия:** Никакой новой npm-зависимости; один источник правды для справки; при добавлении новых статей в `docs/user-guide/` они появляются в SPA без изменений кода. Формат md намеренно ограничен (нет таблиц, ```-блоков, blockquote) — при необходимости расширяем рендер, а не подтягиваем библиотеку.

## DEC-027: Дизайн-система SPA выровнена под redesign (2026-04-29)
**Контекст:** В `redesign/` подготовлен прототип на React/CSS-vars (Sakai-inspired) с фиксированной палитрой (indigo primary), своими токенами и тёмной темой. SPA на Vue 3 + PrimeVue нужно привести к этому визуальному языку без слома существующих компонентов.
**Решение:**
- В `frontend/src/main.ts` Aura-preset переопределён через `definePreset`: `primary` palette смаппена на indigo, semantic токены (primary/highlight/surface) заданы для `light` и `dark` colorScheme. `darkModeSelector: '.app-dark'` сохранён.
- В `frontend/src/styles/main.css` зафиксированы дизайн-токены редизайна (`--primary*`, `--surface-*`, `--text-color*`, цветовые палитры `--green/red/orange/blue/violet/cyan/yellow` с `-500/-50`, `--radius-*`, `--shadow-*`, `--sidebar-width`, `--topbar-height`). Тёмные переопределения вынесены в `:root.app-dark`.
- Шрифт `Nunito Sans` подключён через `<link>` в `frontend/index.html` (preconnect + display=swap), назначен на body через `--font-family`.
- `stores/ui.ts` стал единственным источником истины для темы: `initTheme()` (вызывается из `main.ts` до mount) читает `localStorage['crm.theme']`, иначе `prefers-color-scheme`; `setTheme(mode)`/`toggleTheme()` пишут класс на `<html>` и в localStorage. `layout/composables/layout.ts` теперь делегирует тему в ui store.
**Последствия:** Тема выбора пользователя сохраняется между сессиями, единая точка переключения, PrimeVue компоненты и кастомные секции редизайна используют общие токены. Дальнейшие PR (layout, dashboard, CRM-страницы) переиспользуют те же `--surface-*`/`--primary*` без расхождений.

## DEC-026: Subscription-контур доступен при `trial_expired` + единый источник usage лимитов (2026-04-18)
**Контекст:** При истечении trial tenant получал 402 на все membership/role guarded endpoint-ы, включая страницу подписки и billing flow, что создавало dead-end. Параллельно usage лимитов считался в нескольких местах с риском рассинхронизации (особенно по managers/pipelines).
**Решение:**
- В access-слое введён управляемый флаг `allow_trial_expired` для `require_membership`/`require_roles`.
- Для subscription/billing контура явно разрешён доступ при `trial_expired`: `/tenant/`, `/tenant/plan/`, `/tenant/plans/`, `/billing/checkout/`, `/billing/change-plan/`, `/billing/payments/`.
- Для бизнес-endpoint-ов сохранён прежний инвариант: при `trial_expired` возвращается 402 до оплаты.
- Канонизирован расчёт usage в `apps/billing/usage.py` и переиспользован в API и фоновой задаче проверки лимитов.
- `managers` считаются только по `Membership` в public schema: `is_active=True`, `joined_at IS NOT NULL`, `invite_token IS NULL`, роли `owner/admin/manager`; `viewer` и pending invite не учитываются.
- В usage добавлен ключ `pipelines`, а DTO планов для `/billing/plans/` и `/tenant/plans/` унифицирован через общий serializer.
**Последствия:** Пользователь с истёкшим trial всегда может попасть в подписку и завершить оплату без обходных путей; лимиты отображаются и проверяются консистентно во всех слоях; структура планов в регистрации и ЛК синхронизирована и не дрейфует.

## DEC-028: Server bootstrap для infra-стеков через общий Docker network `proxy` (2026-04-29)
**Контекст:** На «чистых» или частично подготовленных серверах запуск `Portainer` падал с `network proxy not found`; ранее также встречался невалидный restart policy (`max retry count` для non-`on-failure`), что делало старт infra-стека недетерминированным.
**Решение:** Добавлен единый bootstrap-скрипт `for_sample_deploy/bootstrap-server.sh`, который:
- устанавливает Docker/Compose (Debian/Ubuntu);
- готовит каталоги `/opt/traefik`, `/opt/portainer`, `/opt/scripts`;
- гарантирует создание общей сети `proxy` до запуска стеков;
- генерирует compose-файлы без устаревшего `version` и с валидным `restart: unless-stopped`;
- создаёт управляющие скрипты `/opt/scripts/start-all.sh`, `stop-all.sh`, `status-all.sh`.
**Последствия:** Первичная настройка и повторный старт infra-слоя воспроизводимы; `Portainer` подключается к `proxy` без ручного вмешательства; исчезают ошибки старта из-за некорректной restart policy.

## DEC-029: AI Assistant через Hermes orchestrator + OpenCode.ai (2026-05-09)
**Контекст:** Нужен AI-ассистент в CRM с поддержкой чата, CRM-функций и проактивных уведомлений.
**Решение:** Hermes Agent (Docker, port 8642) как orchestrator с OpenCode.ai cloud provider. Per-tenant Hermes profiles изолируют данные. Django хранит диалоги в PostgreSQL (AIConversation/AIMessage, tenant-scoped). Hermes skills написаны на Python и работают через schema_context. Проактивные уведомления идут через Hermes cron → webhook → Django Notification → WebSocket.
**Последствия:** OpenCode Go — облачный сервис (не отдельный контейнер). Hermes — единственный orchestrator. Диалоги хранятся в PostgreSQL (а не в Hermes state.db). Интеграция через OpenAI-compatible API (/v1/chat/completions).

## DEC-030: Pipeline seeding при регистрации тенанта + синонимный фоллбек distribution (2026-05-10)
**Контекст:** После редизайна `auto_create_lead` в мессенджерах не работал — Pipeline/Stage создавались только при шаге 2 онбординга (выбор CRM-режима). Если пользователь пропускал онбординг или первый контакт приходил до настройки, `route_incoming_message` не находил pipeline и Deal не создавался. Распределение тоже не работало: `try_distribute('new_deal', ...)` вызывалось с триггером `new_deal`, но дефолтное правило создавалось с `new_lead`.
**Решение:**
- `_seed_default_pipeline()` вызывается при регистрации тенанта (`register()`) и при пропуске онбординга (`onboarding_skip()`). Гарантированно создаёт воронку «Продажи» с 7 этапами.
- `try_distribute()` делает синонимный фоллбек: если `new_deal` не нашёл правило, пробует `new_lead` (и наоборот). Обратная совместимость с legacy-правилами.
- `auto_create_lead` в `tasks.py` обёрнут в `try/except` с логированием в `message.error` — transient failures не теряют сообщения.
- Cookie рефреш-токена: `SameSite='Lax'` в dev (достаточно для cross-port на localhost), `SameSite='None'` + `Secure=True` в production.
**Последствия:** Pipeline всегда доступен для новых тенантов. Distribution работает с любыми существующими правилами. При сбое `auto_create_lead` сообщение сохраняется с пометкой ошибки.

## DEC-031: UI error handling hardening — toast + planLoaded guards (2026-05-10)
**Контекст:** После редизайна 10+ view имели нулевую обработку ошибок API-вызовов. Паттерн `try { ... } finally { ... }` без `catch` приводил к «немым» кнопкам — клик выполнял запрос, ошибка проглатывалась, кнопка снова становилась активной без объяснения причины.
**Решение:** В каждой view, делающей API-вызовы, добавлены `catch`-блоки с toast-уведомлением через PrimeVue Toast. `<PToast />` размещён в `App.vue`. Вспомогательные guard-ы (`planLoaded` в tenant store) защищают от ложных блокировок до загрузки данных.
**Последствия:** Пользователь всегда видит причину ошибки (toast в правом верхнем углу). Инвариант: любой `await api(...)` обязан иметь `try/catch` с toast при ошибке. Новые view должны следовать этому паттерну с первого коммита.

## DEC-032: Полный рефакторинг A-E (2026-05-10)
**Контекст:** Аудит выявил несколько P0/P1 проблем: ai_assistant миграция с camelCase-полем `herMes_conversation_id` ломала тесты при создании второго tenant; Vite dev отдавал 500 EISDIR на `/app` из-за коллизии SPA-маршрута и `working_dir: /app`; во frontend ~12 кастов `(... as any)` обходили типизацию; `apps/users/api.py` (769 LOC) совмещал auth + invites + roles + role-permissions + manager-profiles; `_seed_default_pipeline` импортировался напрямую из `apps.tenants.onboarding_api` в `apps/users/api.py` (приватный символ через границу app); `CRMView.vue` (2023 LOC) дублировал функциональность DealsView/ContactsView/TasksView; `console.log` оставались в production-коде; bare `except Exception:` без логирования встречались в 23 местах.
**Решение:**
- **AI assistant**: `tenant` FK удалён (избыточен внутри tenant schema), поле переименовано в `hermes_conversation_id`, миграция перегенерирована (БД пустая), удалён дубликат тестов в `tests/__init__.py`.
- **Vite EISDIR**: `working_dir: /srv/app` в `docker-compose.yml` (frontend), все volume mount-ы перенесены на `/srv/app/*`. SPA-маршрут `/app` больше не коллидирует с CWD.
- **Frontend types**: `CrmContact` расширен (`position/messenger_id/source/esign_agreement_*`), `CrmDeal` получил `contracts/chat_sessions/source` рефы, `IvrMenu.options` строго типизирован. Логика retry в `http.ts` вынесена из `onResponseError` в обёртку (правильная архитектура, не заплатка). `(x as any)` касты удалены везде. `tsconfig.json` получил `skipLibCheck: true` для подавления кросс-зависимостей `vite/vitest`.
- **Tenant provisioning service**: создан `apps/tenants/services.py` с публичным `provision_tenant(tenant)` и `ensure_default_pipeline()`. `register()` (auth) и `onboarding_skip()` теперь вызывают единую публичную функцию. Приватный импорт через границу app устранён.
- **users/api split**: 769 LOC → `auth_api.py` (login/register/refresh/logout/me/orgs/switch/invite-check-accept), `team_api.py` (members/invite/role/role-permissions/deactivate), `managers_api.py` (manager-profiles/days-off). `apps/users/api.py` стал тонким shim для обратной совместимости с `config/api.py`.
- **bare except**: `TokenError` (ninja-jwt), `User.DoesNotExist`, `Contact.DoesNotExist`, `requests.RequestException`, `OSError`, `json.JSONDecodeError` — узкие исключения там, где они стабильно определены. Где broad `except` оправдан (greenswitch ESL без публичной иерархии исключений) — добавлен явный комментарий «почему».
- **Frontend decomposition**: `CRMView.vue` (2023 LOC) удалён. Уникальные функции вынесены: `CompaniesView` (167 LOC), `PipelinesView` с двумя tabs воронки/триггеры (460 LOC), `StatsView` (135 LOC). Дубликаты Kanban/Contacts/Tasks устранены — их исходные view (`DealsView/ContactsView/TasksView`) остаются единственной точкой правды. `/app/crm` → redirect на `/app/deals`. Sidebar обновлён: добавлены Компании / Воронки / Аналитика CRM.
- **Frontend logger**: создан `frontend/src/utils/logger.ts` (scoped logger с `debug/info/warn/error`; `debug/info` молчат в production). `console.log` в `stores/notifications.ts`, `stores/ai.ts` и новых views заменены на `log.debug`/`log.error`.
**Последствия:**
- Все 118 backend-тестов зелёные. KNOWN_ISSUES #4 (typecheck), #5 (ai_assistant), #6 (Vite EISDIR) закрыты.
- `apps/users/api.py`: 769 LOC → 18 LOC (shim).
- Зелёный `npm run typecheck`, 5/5 vitest, 118/118 Django tests.
- Частная функция `_seed_default_pipeline` больше не импортируется через границу app — единая публичная точка через `apps.tenants.services.provision_tenant`.
- Production console чище: только warn/error попадают в браузер.

## DEC-033: Системная диагностика и перезапуск Traefik после деплоя (2026-05-11)
**Контекст:** Проект `crm_prvms` на shared VPS не получал Let's Encrypt сертификат, хотя остальные проекты работали. Точечный скрипт `fix-crm-https.sh` маскировал проблему, но не устранял первопричину. Traefik не видел Docker-роутеры CRM.
**Решение:**
- Удалён временный `fix-crm-https.sh`. Вся логика восстановления встроена в общие скрипты.
- `fix-https.sh`: добавлена проверка типа сети `proxy` (overlay + attachable), проверка роутеров через Traefik Dashboard API (`localhost:8080/api/http/routers`), принудительный перезапуск Traefik после ремонта.
- `start-all.sh`: после запуска всех проектов Traefik перезапускается, чтобы гарантированно увидеть все контейнеры (Docker provider `watch=true` иногда пропускает события при быстрых `compose up`).
- `check-https.sh`: добавлена проверка `driver=overlay`/`attachable=true` для сети `proxy` и проверка наличия каждого проектного роутера в Traefik API.
- `crm_prvms/deploy.sh`: после `docker compose up -d` Traefik перезапускается, чтобы подхватить новые/пересозданные контейнеры.
**Последствия:** Любой деплой или перезапуск стека гарантирует, что Traefik перечитывает Docker-конфигурацию. Сетевая целостность `proxy` проверяется автоматически. Точечные скрипты больше не нужны.

## DEC-034: HealthCheckBypassMiddleware + IPv4-литерал для liveness-probe (2026-05-11)
**Контекст:** Диагностика DEC-033 устранила симптом (Traefik не видел роутеры), но при следующем деплое сертификат снова не выдался. Debug-лог Traefik показал `Filtering unhealthy or starting container` для `crm_prvms-web` и `crm_prvms-frontend-app` — Traefik 2.x **намеренно** не регистрирует роутеры контейнеров со статусом `unhealthy`/`starting`. Причины unhealthy оказались две, обе системные:
1. `web` healthcheck бил `curl http://localhost:8000/healthz`, но Django возвращал 404 — `django_tenants.middleware.main.TenantMainMiddleware` стоит перед URL-резолвом и не находит домен `localhost`/`127.0.0.1` в shared schema `Domain`, поэтому отдаёт 404 ещё до того, как `config/urls.py` получает шанс отработать. `SHOW_PUBLIC_IF_NO_TENANT_FOUND=True` поведение не меняет в актуальной версии django-tenants в этой конфигурации.
2. `frontend-app` healthcheck использовал `wget -q --spider http://localhost/`. Busybox-`wget` в `nginx:alpine` резолвит `localhost` в `::1` первым и **не** делает fallback на IPv4, а nginx слушает только IPv4 (entrypoint `10-listen-on-ipv6-by-default.sh` пропускает добавление IPv6-listen из-за «differs from packaged» конфига).

**Решение:**
- `apps/core/middleware.py`: новый `HealthCheckBypassMiddleware`, отвечает `JsonResponse({'status':'ok'})` на `/healthz` и `/healthz/` **до** любых других middleware.
- `config/settings.py`: `HealthCheckBypassMiddleware` поставлен первым в `MIDDLEWARE`, до `TenantMainMiddleware`.
- `vps-deployment/crm_prvms/docker-compose.yml`: healthcheck `frontend-app` использует `http://127.0.0.1/` вместо `localhost` (IPv4-литерал, обход busybox-wget без IPv6-fallback).
- `vps-deployment/scripts/start-all.sh`: добавлен preflight `crm_prvms`: если `PUBLIC_HOSTNAME` отсутствует/пуст в `.env.prod`, проект не стартует — Traefik-лейблы шаблонизированы на этой переменной и без неё дают `Host(``)`.
- `.gitignore`: убран блок-исключение `/vps-deployment` (тёрло отслеживание полезных файлов); добавлены прицельные паттерны `vps-deployment/**/.env*`, `acme.json`, `logs/`, `media/`. Удалён случайный снапшот `vps-deployment/crm_prvms/.venv.current_on_server` с production-секретами.

**Последствия:**
- Liveness-probe больше не зависит от состояния тенантов/доменов — endpoint работает с любого `Host` header, до tenant resolution.
- Контейнер `frontend-app` становится healthy через 30 секунд после старта без костылей с curl/wget внутри образа.
- `start-all.sh` обрывает запуск CRM до того, как Traefik увидит контейнер с пустым `Host(``)` лейблом — fail-fast вместо silent-fail.
- Любая утечка `.env.prod` или серверного снапшота в репозиторий заблокирована на уровне `.gitignore`.
- DEC-033 (перезапуск Traefik) остаётся как defensive measure — устраняет редкие случаи пропуска docker-events. Не отменяется.

### Дополнение (2026-05-11, после прод-выкатки v1):
v1 не закрыла проблему до конца — на сервере `/` всё равно отдавал 404. Причины и доводка:
- **`/opt/crm_prvms/docker-compose.yml` — копия, не симлинк.** При initial setup кто-то скопировал файл вместо `ln -sf`. Git pull обновлял источник (`vps-deployment/crm_prvms/docker-compose.yml`), но рабочий compose оставался прежним → новый healthcheck не попадал в контейнер. Структурный фикс: `deploy.sh` и `start-all.sh` теперь идемпотентно пересоздают симлинки при каждом запуске, копии бэкапятся в `*.copy_replaced_*.bak`. Эта ловушка больше невозможна.
- **`frontend-app` healthcheck удалён полностью.** Бороться с busybox-wget над `localhost`/`127.0.0.1`/IPv6/IPv4/PATH — это бесконечная борьба с инструментом, не предназначенным для liveness-probe. nginx со статикой не падает; Traefik трактует контейнеры без healthcheck как healthy и сразу регистрирует их роутеры. Если nginx умрёт — Docker restart policy поднимет. Чище и надёжнее.
- **`bring_up()` теперь использует `--force-recreate`** — гарантирует, что compose-level изменения (healthcheck, labels) фактически применяются. Без этого compose может посчитать что image hash тот же → контейнер не пересоздаётся → старый healthcheck остаётся.
- **`web` healthcheck переписан на `127.0.0.1`** для консистентности — не критично (curl делает IPv4 fallback), но устраняет лишний RTT и делает поведение детерминированным.

# Dev Log

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

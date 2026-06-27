# Известные проблемы

36. Транскрипция и резюме звонков (DEC-056, Фаза 2) — сквозной результат не проверен из dev-среды.
    - **Граница vs сквозь:** контракт Deepgram подтверждён реальными вызовами из dev (request_id, confidence 0.998), задачи и API покрыты тестами с моками. Но полный сквозной путь (реальная запись Exolve → транскрипт → AI-резюме как активность в таймлайне сделки) не проверялся, потому что прод-сервер `/opt/prvms.crm` работает на старом коде — проверка возможна только после деплоя этой ветки. Изменение самодиагностируемо: логгер `apps.telephony.transcription` пишет `request_id`/длительность/статус, что позволит подтвердить за один прогон.
    - **Резюме через Hermes:** путь идёт через существующий Hermes. Локальная конфигурация Hermes/OpenCode теперь зафиксирована кодом (DEC-057) и проверена live-зондом `/v1/chat/completions`; сквозной результат на реальной записи всё ещё требует прод-деплоя.
    - **Качество русского ASR** на боевых записях (шум линии, перебивания) на реальных данных не измерялось; модель `nova-2`/`language=ru` выбраны по контракту, но метрики WER не снимались.
    - **Стоимость:** каждый звонок несёт переменную внешнюю стоимость (Deepgram + LLM); лимита минут транскрипции в месяц пока нет — кандидат на тарифный лимит.
    - **Резюме** строится по плоскому тексту без диаризации (кто говорит) — посегментная разметка не реализована.
    - **Файлы:** `apps/telephony/deepgram_client.py`, `apps/telephony/tasks.py`, `apps/telephony/models.py`, `apps/telephony/api.py`, `apps/ai_assistant/services.py`, `frontend/src/views/TelephonyView.vue`.
    - **План закрытия:** сквозной зонд на проде после деплоя (по SSH, только чтение логов/статуса с подтверждением шагов); лимит минут транскрипции; диаризация спикеров.

35. ~~Навигация: осиротевший маршрут `/app/pipelines` и мёртвые файлы меню~~ (найдено при актуализации user-guide 0.17.1, 2026-06-23). **Закрыто (2026-06-26, версия 0.19.0):** пункт «Воронки» (owner/admin, `feature: crm_builtin`) возвращён в `frontend/src/layout/AppMenu.vue` по образцу `sales-targets`; мёртвые `frontend/src/layouts/SidebarNav.vue` и `frontend/src/layouts/TopBar.vue` удалены (ноль ссылок в `src`); `docs/user-guide/15-pipelines.md` обновлён под пункт меню. typecheck EXIT=0, build OK.
    - **Сирота:** страница «Воронки и триггеры» ([frontend/src/views/PipelinesView.vue](../frontend/src/views/PipelinesView.vue), маршрут `/app/pipelines`, owner/admin) не имеет пункта в живом боковом меню [frontend/src/layout/AppMenu.vue](../frontend/src/layout/AppMenu.vue). Ссылка на неё встречается только в мёртвом `SidebarNav.vue`. Открыть страницу можно лишь по прямому URL — в руководстве пользователя ([docs/user-guide/15-pipelines.md](user-guide/15-pipelines.md)) это описано как временное обходное решение.
    - **Мёртвый код:** `frontend/src/layouts/SidebarNav.vue` и `frontend/src/layouts/TopBar.vue` не импортируются нигде в дереве компонентов (активны `frontend/src/layout/AppSidebar.vue`→`AppMenu.vue` и `AppTopbar.vue`). Они вводят в заблуждение при сверке меню.
    - **План закрытия:** вернуть пункт «Воронки» в `AppMenu.vue` (owner/admin) либо встроить управление воронками в раздел «Сделки»/«Настройки»; удалить неиспользуемые `SidebarNav.vue`/`TopBar.vue`.

34. ~~Планы продаж и аналитика воронки (DEC-055, Фаза 10).~~ **Закрыто полностью (2026-06-26, Волна 2, версия 0.19.0).**
    - ~~**Конверсия** по текущему распределению, не по истории.~~ **Закрыто (задача 2.4, Часть A):** введена модель `StageTransition` (лог `from_stage→to_stage` на каждый переход), пишется в `create_deal` (вход в начальную стадию) и `move_deal`; эндпоинт `funnel` теперь отдаёт `reached` на стадию (число уникальных сделок когорты, входивших в стадию) и поэтапную конверсию `reached[i]/reached[i-1]` + `history_since`; `StatsView` показывает таблицу «Прохождение по стадиям» с примечанием, что история ведётся с момента внедрения лога. Тесты `HonestFunnelTest`.
    - ~~**`closed_at`** не бэкафилнут.~~ **Закрыто (задача 2.4):** сервис `backfill_closed_at()` + миграция `crm/0013`. Тесты `BackfillClosedAtTest`.
    - ~~**Планы** только по менеджеру помесячно.~~ **Закрыто (задача 2.4, Часть C):** `SalesTarget` получил опциональную воронку (`pipeline`, NULL = все) и командную цель (`responsible` NULL = вся команда); `target-progress` считает факт в области каждого плана, поддерживает командную строку «Команда» и план по воронке; `SalesTargetsView` даёт выбор воронки и пункт «Команда». Уникальность через `nulls_distinct=False`. Миграция `crm/0015`. Тесты `TargetScopeTest`.
    - **Остаточное ограничение:** честная конверсия достоверна только с момента внедрения `StageTransition` — у сделок, перемещённых до релиза, истории переходов нет (явно помечено в UI).
    - **Файлы:** `apps/crm/models.py`, `apps/crm/deals_api.py`, `apps/crm/analytics_api.py`, `apps/crm/schemas.py`, `apps/crm/migrations/{0014_stagetransition,0015_*}.py`, `frontend/src/views/{StatsView,SalesTargetsView}.vue`, `frontend/src/api/crm.ts`.

33. Календарь, напоминания и повторяемость (DEC-054, Фаза 9) — остаточные ограничения v1.
    - **Охват:** ~~календарь показывает задачи только текущего пользователя; командного вида и drag-and-drop нет~~ **Закрыто (2026-06-26, Волна 2 / задача 2.6, версия 0.19.0):** эндпоинт `calendar_activities` принимает `scope=mine|team`; для владельца/админа `team` показывает задачи всех с подписью ответственного, остальным тихо откатывается на личные. В `CalendarView.vue` добавлен переключатель «Мои/Все задачи» и перенос задач мышью (`eventDrop` → `patch_activity(due_date)`). Тесты `CalendarScopeTest`. Drag-перенос в браузере сквозным результатом не наблюдался (нет браузера).
    - **Повторяемость:** UI даёт пресеты (ежедневно/еженедельно/ежемесячно) + поле сырого RRULE; визуального конструктора сложных правил (например, «каждый 2-й вторник») нет — такие правила вводятся строкой RRULE вручную.
    - **Напоминания:** in-app-доставка ответственному подтверждена сквозным зондом через реальный worker; реальная доставка письма-напоминания зависит от боевого SMTP и в среде разработки сквозным результатом не подтверждалась.
    - **Bundle:** добавление FullCalendar увеличило основной чанк (gzip ~463 КБ); предупреждение Vite «chunks > 500 kB» было и до этого, code-splitting не вводился.
    - **Файлы:** `apps/crm/models.py`, `apps/crm/services/recurrence.py`, `apps/crm/tasks.py`, `apps/crm/activities_api.py`, `apps/notifications/services.py`, `frontend/src/views/CalendarView.vue`.
    - **План закрытия:** командный календарь со scope team/all, drag-and-drop переноса срока, визуальный конструктор RRULE, code-splitting тяжёлых вью.

32. Импорт/экспорт и слияние (DEC-053, Фаза 6) — остаточные ограничения v1.
    - **Охват:** ~~реализованы только контакты и компании; сделки не охвачены~~ **Расширено (2026-06-26, Волна 2 / задача 2.3, версия 0.19.0):** добавлены импорт и экспорт сделок. Импорт разрешает FK по имени (воронка по названию или дефолтная, стадия по названию или первая, контакт по телефону/ФИО — опционально) и дедуплицирует по ключу `название+контакт` (`tasks._import_one_deal`); экспорт — `export_deals_csv`; сущности I/O теперь `contacts`/`companies`/`deals`. **Слияние сделок осознанно не реализовано** — сделки транзакционны, дедуп-слияние применимо только к справочным контактам/компаниям; вкладка «Дубли» для сделок показывает пояснение. Тесты `DealImportExportServiceTest` + `test_export_deals_endpoint_returns_csv`.
    - **Импорт:** лимит 10 000 строк на файл (`_MAX_IMPORT_ROWS`); распарсенные строки передаются в Celery-задачу как аргумент — для очень больших файлов целесообразно перейти на загрузку файла в стораджи и стриминг; XLSX читается с `data_only=True` (кэш-значения формул, не сами формулы); капчи/антиспама нет (эндпоинты под JWT+RBAC, не публичные).
    - **Слияние:** необратимо; на фронте подтверждается выбором основной записи, на бэкенде фиксируется в аудите. Откат возможен только восстановлением из бэкапа.
    - **Файлы:** `apps/crm/services/import_export.py`, `apps/crm/services/merge.py`, `apps/crm/import_api.py`, `apps/crm/tasks.py`, `frontend/src/views/DataToolsView.vue`.
    - **План закрытия:** добавить импорт/слияние сделок; для крупных файлов — загрузка через стораджи; UI слияния с предпросмотром итоговой записи.

## Закрытые (2026-05-17)

18. ~~Авторизация в dev-режиме не работает: `SameSite='None'` + `Secure=False` отклоняется браузерами.~~
    - **Истинная причина:** `_set_refresh_cookie` в `apps/users/auth_api.py` использовал `samesite='None'` безусловно. В dev (`DEBUG=True`) `secure=False`, что делает комбинацию `SameSite=None; Secure=False` невалидной по спецификации RFC — браузеры отбрасывают refresh_token cookie. Пользователь логинится, получает access_token, но refresh_token не сохраняется. При следующем запросе, требующем refresh, frontend получает 400 «Missing refresh token» и разлогинивает пользователя.
    - **Исправление:** `samesite = 'Lax' if settings.DEBUG else 'None'`. Для localhost cross-port (`:15173` → `:18100`) `Lax` корректно отправляет cookie, потому что `localhost` с любым портом считается same-site. В prod `SameSite=None` + `Secure=True` сохраняется.
    - **Файлы:** `apps/users/auth_api.py`

## Закрытые (2026-05-16)

16. ~~В мобильной версии не скрывается боковое меню; UI не адаптирован под мобильные.~~
    - **Истинная причина (меню):** баг CSS-специфичности, не JS. `.layout-static .layout-sidebar` (специфичность `0,2,0`) всегда перебивал `@media (max-width:991px) .layout-sidebar` (`0,1,0`) — media query не добавляет специфичности, контейнер всегда несёт `layout-static`. Сайдбар был постоянно виден на телефоне.
    - **Исправление (DEC-037):** layout-режимы разнесены по взаимоисключающим media-диапазонам (desktop → `min-width:992px`, mobile off-canvas → `max-width:991px`). Single-source адаптивный слой в `main.css` (form-сетки, section-header, dialog/drawer `max-width:95vw`, topbar). Директива `v-responsive-table` (class-agnostic, сверена с DOM PrimeVue 4.4) → карточный режим на ≤767px для всех 24 `PDataTable`. Tasks/Assistant 1-колоночные на ≤768px, tab-bar wrap.
    - **Файлы:** `frontend/src/styles/main.css`, `frontend/src/directives/responsiveTable.ts`, `frontend/src/main.ts`, 21 view/component.

## Закрытые (2026-05-10)

4. ~~`frontend` typecheck нестабилен из-за TS-несоответствий и `(... as any)` кастов.~~
   - Закрыто DEC-032: типы `CrmContact/CrmDeal` расширены под фактический backend-ответ; `IvrMenu.options` строго типизирован; `http.ts` retry вынесен в обёртку (правильная архитектура); `tsconfig.json` получил `skipLibCheck: true`. `npm run typecheck` зелёный.

5. ~~Backend-тесты падают с `relation "ai_assistant_aiconversation" does not exist` при создании второго tenant.~~
   - Закрыто DEC-032: убран избыточный `tenant` FK (модель живёт в tenant schema), поле `herMes_conversation_id → hermes_conversation_id`, миграция перегенерирована. 118/118 backend-тестов зелёные.

6. ~~Vite dev `GET /app` → 500 EISDIR из-за коллизии SPA-маршрута и `working_dir: /app`.~~
   - Закрыто DEC-032: `working_dir: /srv/app` в `docker-compose.yml`. Все volume-mount-ы перенесены. `/app` возвращает SPA HTML (200).

7. ~~auto_create_lead в мессенджерах не работал — Pipeline/Stage не сидировались при регистрации тенанта.~~
   - Исправлено: `_seed_default_pipeline()` в `register()`, `onboarding_skip()`, try/except в `tasks.py`. После DEC-032 — единый `provision_tenant()` сервис.

8. ~~Распределение не работало — trigger mismatch `new_deal` vs `new_lead` + отсутствовал синонимный фоллбек.~~
   - Исправлено: trigger `'new_deal'` в онбординге, фоллбек в `try_distribute()`, `builtin_crm` в SOURCE_CHOICES

9. ~~Выход при рефреше страницы — `SameSite='None'` без `Secure` в dev.~~
   - Исправлено: `samesite='Lax' if DEBUG else 'None'`, `secure=not DEBUG`

10. ~~В DealsView не было быстрого создания контакта/компании.~~
    - Исправлено: quick-create диалоги + `+` кнопки в формах создания/редактирования

## Закрытые (2026-05-15)

14. ~~Регрессия инварианта DEC-032 «0 `as any`»: 11 `as any` во фронтенде (9 в `DealsView.vue`, 2 на границе SIP.js).~~
    - **Истинная причина:** тип `CrmDeal` неполный — бэкенд (`get_deal`/`kanban_deals`) отдаёт `created_at/expected_close_date/loss_reason`, в типе их не было; часть кастов вообще лишние (поля уже были в типе). На границе SIP.js — нетипизированный доступ к `sessionDescriptionHandler.peerConnection` и `creds.sip_domain`.
    - **Исправление (DEC-036):** `CrmDeal` дополнен; касты сняты; `contactLabel` принимает `number|null|undefined`; SIP.js типизирован через `Web.SessionDescriptionHandler` (namespace-экспорт `sip.js`) и `creds.sip_domain` (поле уже в `WebRTCCredentials`). `npm run typecheck` EXIT=0.
    - **Файлы:** `frontend/src/api/crm.ts`, `frontend/src/views/DealsView.vue`, `frontend/src/composables/useSIPPhone.ts`

## Закрытые (2026-05-13)

13. ~~Не создаются сделки от входящих сообщений в Telegram/MAX.~~
    - **Истинная причина:** `normalize_incoming_payload` для Telegram не обрабатывал `edited_message` (весь Update попадал как payload, `chat_id='unknown'`). MAX `bot_started` создавал мусорную сессию с `chat_id='unknown'`. При отсутствии Pipeline/Stage `auto_create_lead` молча пропускал создание сделки без логирования. `except Exception` проглатывал реальные ошибки.
    - **Исправление (DEC-035):** `normalize_incoming_payload` возвращает `None` для неподдерживаемых update-типов (Telegram `callback_query`, MAX `bot_started`). `_find_pipeline_and_stage()` с явным логированием. `_auto_create_lead()` записывает `message.error` при отсутствии pipeline/stage. Узкие `except` вокруг создания сделки и синхронизации с внешней CRM. Покрытие тестами расширено с 3 до 13 тестов.
    - **Файлы:** `apps/channels/tasks.py`, `apps/channels/providers.py`, `apps/channels/public_views.py`, `apps/channels/tests/test_bridge.py`

## Закрытые (2026-05-11)

12. ~~crm.prvms.ru не получает Let's Encrypt сертификат на shared VPS.~~
    - **Истинная причина (выявлена debug-логами Traefik):** Traefik 2.x намеренно не регистрирует роутеры для контейнеров со статусом `unhealthy`/`starting` (`Filtering unhealthy or starting container`). Контейнеры `web` и `frontend-app` были unhealthy по двум независимым причинам: (а) `web` healthcheck бил `/healthz`, но `django_tenants.TenantMainMiddleware` не находил `localhost` в Domain table и возвращал 404 до URL-резолва; (б) `frontend-app` healthcheck использовал busybox-wget на `localhost`, который резолвит `::1` и не делает IPv4-fallback, а nginx слушал только IPv4.
    - **Дополнительная причина (исходный триггер):** В серверном `.env.prod` отсутствовал `PUBLIC_HOSTNAME`, на котором шаблонизированы Traefik-лейблы. Без него лейблы становились `Host(``)` и Traefik их отбрасывал.
    - **Исправление (DEC-034):** `HealthCheckBypassMiddleware` отвечает на `/healthz` до tenant resolution; healthcheck `frontend-app` удалён (nginx без healthcheck → Traefik сразу регистрирует роутер); `deploy.sh`/`start-all.sh` идемпотентно пересоздают `/opt/crm_prvms/*` симлинки на каждый запуск (копии бэкапятся в `*.copy_replaced_*.bak`); `bring_up()` использует `--force-recreate`; в `start-all.sh` добавлен preflight на `PUBLIC_HOSTNAME`. DEC-033 (перезапуск Traefik) сохранён как defensive measure.
    - **Файлы:** `apps/core/middleware.py`, `config/settings.py`, `vps-deployment/crm_prvms/docker-compose.yml`, `vps-deployment/crm_prvms/deploy.sh`, `vps-deployment/scripts/start-all.sh`, `.gitignore`

## Закрытые (2026-06-21)

26. ~~Заявки с лендинга не приходят на почту: в логе Celery `delivered=1`, но письмо печатается воркером.~~
    - **Истинная причина:** в запущенном стеке активен `django.core.mail.backends.console.EmailBackend`. В репозиторийном `.env` уже был переключён на SMTP, но `.env.example` по умолчанию задавал `console`; при копировании примера и заполнении только SMTP-блока получался молчаливый fallback. Docker Compose также не перечитывает `env_file` без пересоздания контейнеров, поэтому смена переменной без `--force-recreate`/`--build` не влияла на работающий воркер.
    - **Исправление:** `settings.py` теперь автоматически выбирает SMTP-бэкенд, если задан `SMTP_HOST`, но `EMAIL_BACKEND` не указан явно; добавлен Django system check `notifications.W001`, который предупреждает в `manage.py check` о конфликте `console + SMTP_HOST`; `.env.example` приведён к автовыбору backend.
    - **Файлы:** `config/settings.py`, `apps/notifications/checks.py`, `apps/notifications/apps.py`, `.env.example`
    - **Действие для продолжения:** пересоздать контейнеры (`docker compose down && up -d --build`) и убедиться, что в рабочем `.env` нет явного `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.

27. ~~После перехода на SMTP Celery не может резолвить/достучаться до `smtp.beget.com`: `socket.gaierror: [Errno -3] Temporary failure in name resolution`.~~
    - **Истинная причина:** в `docker-compose.prod.yml` сеть `backend` имеет `internal: true`, что блокирует исходящий трафик из контейнеров. `celery` был подключён только к `backend`, поэтому не мог установить TCP-соединение с внешним SMTP-сервером.
    - **Исправление:** `celery` в `docker-compose.prod.yml` подключён также к внешней сети `traefik` (исходящий интернет); `send_email_async` получила `autoretry_for=(smtplib.SMTPException, OSError)` с экспоненциальным бэкоффом (`max_retries=3`) для переживания кратковременных сетевых сбоев.
    - **Файлы:** `docker-compose.prod.yml`, `apps/notifications/tasks.py`
    - **Действие для продолжения:** пересобрать и пересоздать production-стек (`./deploy.sh` или `docker compose -f docker-compose.prod.yml down && up -d --build`); убедиться, что хостовый файрвол не блокирует исходящий 465/587.

## Открытые

31. ~~**Автоматизации — частично закрыто (DEC-052), остался триггер `sla_breach`.**~~ **Закрыто полностью (2026-06-26, версия 0.19.0).**
    - **Контекст:** Реализованы правила «если → то» с триггерами `new_deal`/`stage_changed`/`no_activity`, событийная оценка и beat для time-based, конструктор в ЛК.
    - **Закрыто (2026-06-26, Волна 1 / задача 1.2):**
      - ~~Действия `change_stage`/`assign`/`create_document` не выведены в UI~~ — добавлены в конструктор `AutomationView.vue` с выбором целевой стадии/менеджера/шаблона; `create_document` гейтован фичей `documents`.
      - ~~Условия правила в UI ограничены~~ — добавлены необязательные условия «Воронка» и «Стадия» (`conditions.pipeline_id`/`stage_id`).
      - Защита: `automation_api._validate` теперь требует обязательные параметры действий (`stage_id`/`responsible_id`/`template_id`), иначе правило падало бы при срабатывании внутри `create_deal`/`move_deal` (бэкенд-тесты `AutomationValidationApiTest` + исполнение `change_stage`/`assign`).
    - **Закрыто (2026-06-26, Волна 2 / задача 2.5):**
      - ~~Триггер «превышение SLA на стадии» (`sla_breach`)~~ — реализован в beat `evaluate_time_rules` по образцу `no_activity`: метрика времени — момент входа в текущую стадию (последняя активность `stage_change`, иначе `created_at`), идемпотентность через `AutomationRunLog`. Добавлен в `_TRIGGERS`, выведен в конструктор с полем «Дней на стадии (SLA)» и подсказкой задать стадию в условиях. Тесты `test_sla_breach_*` (срабатывание, идемпотентность, учёт свежего `stage_change`).
    - **Файлы:** `apps/crm/services/auto_actions.py`, `apps/crm/automation_api.py`, `apps/crm/tasks.py`, `frontend/src/views/AutomationView.vue`
    - **Статус:** закрыто полностью (DEC-052 первой версии + действия/условия 1.2 + `sla_breach` 2.5).

30. ~~**Теги и сегменты (DEC-051).**~~ **Закрыто полностью (2026-06-26, версия 0.19.0).**
    - **Закрыто (Волна 1 / задача 1.1):** чипы тегов и `PMultiSelect` в карточках контакта/сделки; сериализаторы `get_contact`/`get_deal`/`kanban_deals` возвращают `tags`; фильтр «Тег» в списках.
    - **Закрыто (Волна 2 / сегменты):** UI сегментов (сохранённых фильтров) добавлен в списки контактов и сделок — выпадающий список сегментов применяет сохранённый фильтр по тегу, кнопка «закладка» сохраняет текущий фильтр как именованный сегмент (`createSegment`/`listSegments`, `entity` contacts/deals). Бэкенд CRUD `segments/` был готов ранее.
    - **Файлы:** `apps/crm/tags_api.py`, `apps/crm/contacts_api.py`, `apps/crm/deals_api.py`, `frontend/src/views/{TagsView,ContactsView,DealsView,DealDetailView}.vue`, `frontend/src/components/ContactDrawer.vue`, `frontend/src/api/crm.ts`

29. **Веб-формы — ограничения первой версии (DEC-050).**
    - **Контекст:** Реализован конструктор веб-форм + встраиваемый виджет + публичный приём заявок. Подтверждено: живой POST публичного endpoint (контакт+сделка), e2e конструктора в ЛК.
    - **Закрыто (2026-06-26, Волна 2 / задача 2.2, версия 0.19.0):**
      - ~~Типы полей ограничены `text/email/phone/textarea`~~ — добавлены `select` (с вариантами) и `checkbox` в конструкторе (`WebFormsView.vue`) и виджете (`crm-webform.js`); приём кладёт ответы в `custom_fields` обобщённо.
      - ~~reCAPTCHA/hCaptcha не добавлены~~ — добавлена подключаемая серверная проверка капчи (`apps/crm/services/captcha.py`): при пустом `CAPTCHA_SECRET` — no-op (формы работают), иначе токен проверяется в `webform_submit` у провайдера (контракт siteverify), site_key отдаётся в схеме, виджет рендерит reCAPTCHA/hCaptcha. Контракт verify покрыт тестом с моком; **сквозной результат с боевым ключом не подтверждался** из этой среды.
    - **Осталось:**
      - Тип «файл» не поддержан; проверка виджета и капчи на реальном внешнем сайте сквозным результатом не выполнялась.
    - **Файлы:** `apps/crm/public_views.py`, `apps/crm/services/captcha.py`, `config/settings.py`, `frontend/public/widget/crm-webform.js`, `frontend/src/views/WebFormsView.vue`
    - **План закрытия:** тип «файл», боевая проверка виджета и капчи на внешнем сайте.

28. **Email-канал — ограничения первой версии (DEC-049).**
    - **Контекст:** Реализован двусторонний email-канал (IMAP-приём + SMTP-отправка). Подтверждено: сквозной SMTP/IMAP round-trip на боевом ящике; e2e создания канала в браузере (`email-channel.spec.ts`, `3 passed`); юнит-тесты разбора письма (HTML-fallback, метаданные вложений).
    - **Закрыто (2026-06-26, Волна 2 / задача 2.1, версия 0.19.0):**
      - ~~Содержимое вложений не хранится/не скачивается~~ — `parse_email` сохраняет содержимое вложений как base64 в `MessageLog.attachments` (лимит 5 МБ; крупнее — только метаданные), чат-компонент `ChatsTab.vue` отдаёт их ссылкой на скачивание через data-URI.
      - ~~Тред-заголовки не проставляются~~ — исходящий ответ получает `In-Reply-To`/`References` из `Message-ID` последнего входящего письма переписки (`_send_email(headers=...)`, `_last_incoming_email_id`). Покрыто юнит-тестами `EmailParseAndThreadingTest`.
    - **Осталось:**
      - Инлайн-HTML и картинки не рендерятся (HTML захватывается в `parse_email['html']`, но безопасный рендер требует поля модели и санитайзера — XSS-риск, не хардкодим).
      - OAuth для Gmail/Yandex не реализован; авторизация только по логину/паролю IMAP/SMTP.
    - **Файлы:** `apps/channels/email_poller.py`, `apps/channels/providers.py`, `apps/channels/tests/test_email_channel.py`, `frontend/src/components/ChatsTab.vue`
    - **План закрытия:** безопасный рендер инлайн-HTML (поле + санитайзер), OAuth Gmail/Yandex.

22. **Канал ВКонтакте — ограничения первой версии.**
    - **Контекст:** Реализован базовый приём/отправка текстовых сообщений через Callback API.
    - **Закрыто (2026-06-26, Волна 2 / задача 2.7, версия 0.19.0):**
      - ~~Имя контакта «Клиент ВК <id>»~~ — при первом входящем VK-сообщении `route_incoming_message` подтягивает реальное имя через `get_vk_user_name` (VK `users.get`) и сохраняет в сессию, так что контакт называется по-человечески. Контракт `users.get` покрыт тестом с моком; **сквозной результат с боевым групповым токеном не подтверждался** из этой среды.
    - **Осталось:**
      - Вложения исходящих сообщений из CRM в ВК не поддерживаются.
      - Стикеры/опросы/геолокация из входящих сохраняются только как метаданные attachments, не отображаются в UI.
      - Лид-формы, комментарии под постами, wall_reply — не обрабатываются.
    - **Файлы:** `apps/channels/providers.py`, `apps/channels/tasks.py`, `apps/channels/oauth_api.py`, `frontend/src/views/oauth/VkCallbackView.vue`
    - **План закрытия:** отдельные задачи (исходящие вложения, рендер стикеров/опросов, лид-формы/комментарии).

19. ~~**SettingsView доступен admin — организационные настройки не защищены от редактирования.**~~ **Решено (2026-06-26):** по решению владельца роль «Администратор» намеренно сохраняет право менять настройки организации наравне с владельцем; отдельная защита org-полей не вводится. Пункт закрыт как продуктовое решение, не дефект.
    - **Контекст:** После переноса Notifications и Channels внутрь SettingsView доступ к `/app/settings` расширен с `owner` на `owner` + `admin` (router meta). Однако организационные поля (название, brand_color, timezone, language, логотип) пока не имеют UI-guard'а, ограничивающего редактирование только owner.
    - **Файлы:** `frontend/src/views/SettingsView.vue`, `frontend/src/router/index.ts`
    - **План закрытия:** добавить `canManageOrg` guard (computed от auth.role === 'owner') и блокировать/скрывать org-поля для admin; либо вынести notifications/channels в отдельные роуты с собственным access-control.

20. **Вложенные `FeatureGate` в `SettingsView` дают визуальное дублирование padding/section.** _(2026-06-26: косметика, осознанно отложено в бэклог — Волна 0 закрыла только #19/#21/#35; см. `docs/ROADMAP_BACKLOG.md`.)_
    - **Контекст:** `NotificationsView` и `ChannelsView` встроены как вкладки в `SettingsView`. Каждый из них обёрнут в `<section class="...">` с собственными отступами, что при переключении вкладок даёт небольшое несоответствие вертикальных отступов.
    - **Файлы:** `frontend/src/views/SettingsView.vue`, `frontend/src/views/NotificationsView.vue`, `frontend/src/views/ChannelsView.vue`
    - **План закрытия:** создать презентационные "settings-panel" компоненты без `<section>`-обёртки, или вынести вкладки в отдельные роуты (`/app/settings/notifications`, `/app/settings/channels`).

21. ~~**`ChannelsView` всё ещё содержит таб «Чаты», дублирующий `ChatsView`.**~~ **Закрыто (2026-06-26):** таб «Чаты» и вся его чат-логика (WebSocket, сессии, сообщения, AI-ассистент) удалены из `frontend/src/views/ChannelsView.vue`; остаётся только управление каналами. Старая ссылка `/app/channels?tab=chats` редиректит на `/app/chats` через `router.replace`. `ChatsTab.vue` сохранён (используется `ChatsView`/`DealChatTab`). typecheck EXIT=0, build OK, vitest 11/11.
    - **Контекст:** `ChannelsView` (теперь вкладка «Мессенджеры» в Настройках) имеет два таба: «Каналы» и «Чаты». Таб «Чаты» функционально идентичен `ChatsView.vue` (`/app/chats`). Прямой доступ к `/app/channels` из меню отсутствует (locked), но deep-link или старые закладки могут привести к путанице.
    - **Файлы:** `frontend/src/views/ChannelsView.vue`
    - **План закрытия:** удалить таб «Чаты» из `ChannelsView`; оставить только «Каналы». Deep-link compatibility можно сохранить редиректом `?tab=chats` → `/app/chats`.

1. ~~Для внешних CRM в production требуется финальная валидация на реальных аккаунтах amoCRM/Битрикс24.~~ **ЗАКРЫТО — внешние CRM удалены из проекта (2026-06-27, DEC-058, версия 0.19.0).** Интеграция со сторонними CRM не нужна; продукт строится только на встроенном CRM. Приложение `apps/integrations` удалено целиком (модели/адаптеры/OAuth/webhooks/UI/фичи/лимит), ядровая модель команды выделена в `apps/team`. См. DEC-058 и память `feedback_no_external_crm`.

2. ~~`freeswitch` в профиле `telephony` остаётся экспериментальным.~~ **Закрыто 2026-06-15 (DEC-042):** FreeSWITCH удалён полностью, телефония переведена на облако MTS Exolve.

23. **Телефония Exolve — сквозным результатом не проверена (нет боевого ключа в dev-среде).**
    - **Контекст:** Backend и frontend реализованы и проверены до уровня кода/сборки/контракта (131/131 backend, typecheck/build/vitest зелёные, публичные webhook-и отвечают корректным JSON-RPC). Реальный голосовой звонок не выполнялся.
    - **Что нужно для закрытия:** боевой `EXOLVE_API_KEY`, закупленный номер, публичный HTTPS-URL (`EXOLVE_PUBLIC_BASE_URL`), `EXOLVE_WEBHOOK_SECRET`. На проде проверить: автозакупку номера через мастер, авто-провижининг SIP, регистрацию софтфона, входящий (создание сделки + дедуп + дозвон ответственному), исходящий из сделки и контакта, журнал и запись.
    - **Самодиагностика:** `apps/telephony/exolve_client.py` логирует каждый запрос/ответ; `public_views.py` логирует каждый IPCR/Call-Event. Подтверждается за один прогон по логам web.

24. **Точки внешнего поведения Exolve, требующие подтверждения на первом боевом звонке.**
    - Форма ответа `GetFree` нормализуется защитно в `ExolveNumberWizard.vue` (`extractNumbers`) — при расхождении ключей поправить маппинг.
    - Маршрутизация `REDIRECT_NUMBER` именно на SIP-аккаунт по `username` (`exolve_service.build_followme_response`) заложена с резервом; сверить на боевом входящем.
    - Автопроигрывание входящего аудио в Web Voice SDK не подтверждено: если SDK не воспроизводит поток сам, добавить привязку `<audio>` к сессии в `stores/phone.ts`.

25. **Корреляция исходящих CDR с Call Events — best-effort.**
    - **Контекст:** Исходящий набирается в браузере через SDK; `click-to-call` создаёт `CallRecord` с локальным `call_sid` (`cti-…`), который не совпадает с `call_sid` Exolve. Поэтому метрики длительности/записи для исходящих из браузера пока не привязываются автоматически к этой записи журнала.
    - **План закрытия:** получать реальный `call_sid`/идентификатор сессии из SDK и сопоставлять с Call Events, либо журналировать исходящие исключительно по Call Events.

3. Покрытие e2e — частичное; нагрузочных тестов нет.
   - **Сделано (DEC-048):** Playwright-каркас + самодостаточный прогон (`docker compose run --rm e2e` сам поднимает `web`+`seed`); сквозные сценарии `catalog.spec.ts` и `deal-items.spec.ts` проходят `2 passed` в реальном headless-Chromium (вход, создание товара, создание сделки, добавление позиции, проверка инварианта суммы).
   - **Осталось:** e2e на tenant switch, документы/подписание, чаты/мессенджеры, телефонию; отдельный performance-профиль для API/WebSocket/Celery.
   - Файлы: `apps/*/tests/*`, `frontend/src/**/*.test.ts`, `frontend/e2e/*`

11. ~~CI отсутствует — нет автоматического прогона `manage.py check`/тестов/typecheck/vitest при PR.~~ **Закрыто (констатация: было неактуально):** CI существует в `.github/workflows/ci.yml` — backend (`check` + migrations guard + tests на Python 3.13 + Postgres), frontend (typecheck + vitest + build на Node 24), deploy на push в main. **2026-06-20 (DEC-044):** добавлена отдельная lint-job (ruff F/E/B/BLE/I), от которой зависит деплой.

15. `TelephonyView`/`DocumentsView` — кандидаты на декомпозицию фронтенда (P2-1 продолжение, DEC-036). **Примечание (2026-06-20):** `ContractsView` переименован в `DocumentsView` (DEC-043); декомпозиция фронтенда (Блок 3 аудита DEC-044) в работу 2026-06-20 не входила — выполнялись только backend/инфра-блоки 0–2.
    - **Контекст:** P2-1 выполнен полностью, включая ранее отложенный ChatsTab. `DealsView` 760→623, `IntegrationsView` 645→415, `ChannelsView` 605→452 — 9 новых презентационных компонентов; вся логика/WS остаётся в родителях. ChatsTab решён без эвристик: дочерний компонент владеет только scroll-DOM-узлом и экспонирует `scrollToBottom()` через `defineExpose`; родительские WS/send/load-обработчики вызывают его в тех же точках управления (1:1 перенос потока, не watcher-догадка) — проверяется `typecheck`+`vite build`. Все гейты зелёные.
    - **Файлы:** `frontend/src/views/{TelephonyView,ContractsView}.vue` (≈555/554 LOC, ещё не декомпозированы)
    - **План закрытия:** применить тот же паттерн «parent owns state, child presentational» + гейт `typecheck`/`vite build`; рекомендуется браузер-QA телефонии/договоров при следующем визуальном прогоне.

17. Адаптивный UI (DEC-037) не прошёл браузер-QA на реальном устройстве — в среде разработки нет браузера.
    - **Контекст:** Фикс специфичности sidebar детерминирован (доказуем по правилам каскада CSS), DOM-предположения директивы `v-responsive-table` сверены с исходниками PrimeVue 4.4, в собранном бандле подтверждены маркеры (`rt-cards`/`data-label`/media-queries), dev SPA отдаёт 200. Но визуальная проверка на устройстве/эмуляторе (off-canvas drawer + mask, карточные таблицы, формы в 1 колонку, диалоги ≤95vw, kanban-swipe, AI-ассистент) не выполнялась.
    - **Файлы:** `frontend/src/styles/main.css`, `frontend/src/directives/responsiveTable.ts`, 21 view/component.
    - **План закрытия:** прогон на эмуляторе (Chrome DevTools device toolbar) и реальном телефоне для ширин 320/375/414/768/1024px; зафиксировать результат в DEV_LOG.

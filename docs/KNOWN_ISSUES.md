# Известные проблемы

36. Транскрипция и резюме звонков (DEC-056, Фаза 2) — сквозной результат не проверен из dev-среды.
    - **Граница vs сквозь:** контракт Deepgram подтверждён реальными вызовами из dev (request_id, confidence 0.998), задачи и API покрыты тестами с моками. Но полный сквозной путь (реальная запись Exolve → транскрипт → AI-резюме как активность в таймлайне сделки) не проверялся, потому что прод-сервер `/opt/prvms.crm` работает на старом коде — проверка возможна только после деплоя этой ветки. Изменение самодиагностируемо: логгер `apps.telephony.transcription` пишет `request_id`/длительность/статус, что позволит подтвердить за один прогон.
    - **Резюме через Hermes:** путь идёт через существующий Hermes. Локальная конфигурация Hermes/OpenCode теперь зафиксирована кодом (DEC-057) и проверена live-зондом `/v1/chat/completions`; сквозной результат на реальной записи всё ещё требует прод-деплоя.
    - **Качество русского ASR** на боевых записях (шум линии, перебивания) на реальных данных не измерялось; модель `nova-2`/`language=ru` выбраны по контракту, но метрики WER не снимались.
    - **Стоимость:** каждый звонок несёт переменную внешнюю стоимость (Deepgram + LLM); лимита минут транскрипции в месяц пока нет — кандидат на тарифный лимит.
    - **Резюме** строится по плоскому тексту без диаризации (кто говорит) — посегментная разметка не реализована.
    - **Файлы:** `apps/telephony/deepgram_client.py`, `apps/telephony/tasks.py`, `apps/telephony/models.py`, `apps/telephony/api.py`, `apps/ai_assistant/services.py`, `frontend/src/views/TelephonyView.vue`.
    - **План закрытия:** сквозной зонд на проде после деплоя (по SSH, только чтение логов/статуса с подтверждением шагов); лимит минут транскрипции; диаризация спикеров.

35. Навигация: осиротевший маршрут `/app/pipelines` и мёртвые файлы меню (найдено при актуализации user-guide 0.17.1, 2026-06-23).
    - **Сирота:** страница «Воронки и триггеры» ([frontend/src/views/PipelinesView.vue](../frontend/src/views/PipelinesView.vue), маршрут `/app/pipelines`, owner/admin) не имеет пункта в живом боковом меню [frontend/src/layout/AppMenu.vue](../frontend/src/layout/AppMenu.vue). Ссылка на неё встречается только в мёртвом `SidebarNav.vue`. Открыть страницу можно лишь по прямому URL — в руководстве пользователя ([docs/user-guide/15-pipelines.md](user-guide/15-pipelines.md)) это описано как временное обходное решение.
    - **Мёртвый код:** `frontend/src/layouts/SidebarNav.vue` и `frontend/src/layouts/TopBar.vue` не импортируются нигде в дереве компонентов (активны `frontend/src/layout/AppSidebar.vue`→`AppMenu.vue` и `AppTopbar.vue`). Они вводят в заблуждение при сверке меню.
    - **План закрытия:** вернуть пункт «Воронки» в `AppMenu.vue` (owner/admin) либо встроить управление воронками в раздел «Сделки»/«Настройки»; удалить неиспользуемые `SidebarNav.vue`/`TopBar.vue`.

34. Планы продаж и аналитика воронки (DEC-055, Фаза 10) — остаточные ограничения v1.
    - **Конверсия:** воронка строится на текущем распределении сделок по стадиям, а не на историческом проходе по этапам (активность `stage_change` хранит названия стадий без `stage_id`, надёжно реконструировать переходы нельзя). Точная поэтапная конверсия потребует логирования `stage_id` в истории.
    - **`closed_at`:** заполняется только при будущих переходах сделки в `won`/`lost`; сделки, закрытые до релиза, остаются с пустым `closed_at` и не попадут в периодную аналитику, пока их не переместят повторно. Разовый бэкафилл `closed_at` по дате последнего `stage_change` в won/lost — кандидат на отдельную миграцию.
    - **Планы:** только помесячно и по менеджеру; разбивки по воронкам и явных командных целей (сверх суммы планов менеджеров) нет.
    - **Файлы:** `apps/crm/deals_api.py`, `apps/crm/analytics_api.py`, `apps/crm/models.py`, `frontend/src/views/StatsView.vue`, `frontend/src/views/SalesTargetsView.vue`.
    - **План закрытия:** логировать `stage_id` в истории для честной поэтапной воронки; миграция-бэкафилл `closed_at`; планы по воронкам и командные цели.

33. Календарь, напоминания и повторяемость (DEC-054, Фаза 9) — остаточные ограничения v1.
    - **Охват:** календарь показывает задачи только текущего пользователя (`responsible_id = me`); командного вида и drag-and-drop переноса событий нет.
    - **Повторяемость:** UI даёт пресеты (ежедневно/еженедельно/ежемесячно) + поле сырого RRULE; визуального конструктора сложных правил (например, «каждый 2-й вторник») нет — такие правила вводятся строкой RRULE вручную.
    - **Напоминания:** in-app-доставка ответственному подтверждена сквозным зондом через реальный worker; реальная доставка письма-напоминания зависит от боевого SMTP и в среде разработки сквозным результатом не подтверждалась.
    - **Bundle:** добавление FullCalendar увеличило основной чанк (gzip ~463 КБ); предупреждение Vite «chunks > 500 kB» было и до этого, code-splitting не вводился.
    - **Файлы:** `apps/crm/models.py`, `apps/crm/services/recurrence.py`, `apps/crm/tasks.py`, `apps/crm/activities_api.py`, `apps/notifications/services.py`, `frontend/src/views/CalendarView.vue`.
    - **План закрытия:** командный календарь со scope team/all, drag-and-drop переноса срока, визуальный конструктор RRULE, code-splitting тяжёлых вью.

32. Импорт/экспорт и слияние (DEC-053, Фаза 6) — остаточные ограничения v1.
    - **Охват:** реализованы только контакты и компании; сделки не охвачены (обязательные FK `pipeline`/`stage`, сложный ключ дедупа `name+contact`).
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

31. **Автоматизации — неполный охват первой версии (DEC-052).**
    - **Контекст:** Реализованы правила «если → то» с триггерами `new_deal`/`stage_changed`/`no_activity`, событийная оценка и beat для time-based, конструктор в ЛК.
    - **Ограничения:**
      - Триггер «превышение SLA на стадии» (`sla_breach`) не реализован — есть только `no_activity` (нет активности N дней).
      - В конструкторе доступны действия «создать задачу» и «отправить уведомление»; действия `change_stage`/`assign`/`create_document` поддержаны бэкенд-исполнителем, но не выведены в UI.
      - Условия правила в UI ограничены (бэкенд умеет фильтр по воронке/стадии).
    - **Файлы:** `apps/crm/services/auto_actions.py`, `apps/crm/automation_api.py`, `frontend/src/views/AutomationView.vue`
    - **План закрытия:** добавить `sla_breach`, расширить UI действий и условий.

30. **Теги/сегменты — UI первой версии неполный (DEC-051).**
    - **Контекст:** Реализованы модели, CRUD и назначение тегов, фильтрация списков по тегу (backend), а также страница управления тегами в ЛК.
    - **Ограничения:**
      - Назначение тегов прямо в карточке контакта/сделки в UI не сделано (эндпоинты `contacts|deals/{id}/tags/` готовы и покрыты тестами).
      - UI работы с сегментами (сохранённые фильтры) не сделан (CRUD `segments/` готов).
      - Фильтр списков по тегу есть в API (`tag_id`), но не выведен в UI списков.
    - **Файлы:** `apps/crm/tags_api.py`, `frontend/src/views/TagsView.vue`
    - **План закрытия:** добавить чипы тегов в карточки и фильтр по тегу/сегменту в списках.

29. **Веб-формы — ограничения первой версии (DEC-050).**
    - **Контекст:** Реализован конструктор веб-форм + встраиваемый виджет + публичный приём заявок. Подтверждено: живой POST публичного endpoint (контакт+сделка), e2e конструктора в ЛК.
    - **Ограничения:**
      - Встраивание виджета на сторонний сайт сквозным результатом не проверялось (тестировался публичный endpoint, который он вызывает); CORS открывается по `allowed_origins` формы.
      - Защита формы — honeypot + rate-limit по IP; reCAPTCHA/hCaptcha не добавлены.
      - Типы полей ограничены (`text/email/phone/textarea`); `select`/чекбоксы/файлы не поддержаны.
    - **Файлы:** `apps/crm/public_views.py`, `apps/crm/services/webform_intake.py`, `frontend/public/widget/crm-webform.js`, `frontend/src/views/WebFormsView.vue`
    - **План закрытия:** отдельные задачи (капча, расширенные типы полей, проверка виджета на реальном внешнем сайте).

28. **Email-канал — ограничения первой версии (DEC-049).**
    - **Контекст:** Реализован двусторонний email-канал (IMAP-приём + SMTP-отправка). Подтверждено: сквозной SMTP/IMAP round-trip на боевом ящике; e2e создания канала в браузере (`email-channel.spec.ts`, `3 passed`); юнит-тесты разбора письма (HTML-fallback, метаданные вложений).
    - **Ограничения (оставшиеся):**
      - HTML-письма конвертируются в простой текст (теги срезаются, `script/style` отбрасываются); инлайн-HTML и картинки не рендерятся.
      - Вложения сохраняются как метаданные (имя/тип) в `MessageLog.attachments`; содержимое файлов не скачивается и не хранится.
      - Авторизация только по логину/паролю IMAP/SMTP; OAuth для Gmail/Yandex не реализован.
      - Тема исходящего ответа фиксирована (`reply_subject` или «Ответ на ваше обращение»); тред-заголовки (`In-Reply-To`/`References`) не проставляются.
    - **Файлы:** `apps/channels/email_poller.py`, `apps/channels/providers.py`, `apps/channels/tasks.py`, `apps/channels/tests/test_email_channel.py`, `frontend/src/components/ChannelsTab.vue`, `frontend/src/views/ChannelsView.vue`, `frontend/e2e/email-channel.spec.ts`
    - **План закрытия:** отдельные задачи (хранение/рендер содержимого вложений и инлайн-HTML, OAuth, тред-заголовки).

22. **Канал ВКонтакте — ограничения первой версии.**
    - **Контекст:** Реализован базовый приём/отправка текстовых сообщений через Callback API.
    - **Ограничения:**
      - Имя контакта при создании сделки из ВК — «Клиент ВК <id>» (не запрашиваем `users.get` в первой версии).
      - Вложения исходящих сообщений из CRM в ВК не поддерживаются.
      - Стикеры/опросы/геолокация из входящих сохраняются только как метаданные attachments, не отображаются в UI.
      - Лид-формы, комментарии под постами, wall_reply — не обрабатываются.
    - **Файлы:** `apps/channels/providers.py`, `apps/channels/oauth_api.py`, `frontend/src/views/oauth/VkCallbackView.vue`
    - **План закрытия:** отдельные задачи после релиза базовой версии.

19. **SettingsView доступен admin — организационные настройки не защищены от редактирования.**
    - **Контекст:** После переноса Notifications и Channels внутрь SettingsView доступ к `/app/settings` расширен с `owner` на `owner` + `admin` (router meta). Однако организационные поля (название, brand_color, timezone, language, логотип) пока не имеют UI-guard'а, ограничивающего редактирование только owner.
    - **Файлы:** `frontend/src/views/SettingsView.vue`, `frontend/src/router/index.ts`
    - **План закрытия:** добавить `canManageOrg` guard (computed от auth.role === 'owner') и блокировать/скрывать org-поля для admin; либо вынести notifications/channels в отдельные роуты с собственным access-control.

20. **Вложенные `FeatureGate` в `SettingsView` дают визуальное дублирование padding/section.**
    - **Контекст:** `NotificationsView` и `ChannelsView` встроены как вкладки в `SettingsView`. Каждый из них обёрнут в `<section class="...">` с собственными отступами, что при переключении вкладок даёт небольшое несоответствие вертикальных отступов.
    - **Файлы:** `frontend/src/views/SettingsView.vue`, `frontend/src/views/NotificationsView.vue`, `frontend/src/views/ChannelsView.vue`
    - **План закрытия:** создать презентационные "settings-panel" компоненты без `<section>`-обёртки, или вынести вкладки в отдельные роуты (`/app/settings/notifications`, `/app/settings/channels`).

21. **`ChannelsView` всё ещё содержит таб «Чаты», дублирующий `ChatsView`.**
    - **Контекст:** `ChannelsView` (теперь вкладка «Мессенджеры» в Настройках) имеет два таба: «Каналы» и «Чаты». Таб «Чаты» функционально идентичен `ChatsView.vue` (`/app/chats`). Прямой доступ к `/app/channels` из меню отсутствует (locked), но deep-link или старые закладки могут привести к путанице.
    - **Файлы:** `frontend/src/views/ChannelsView.vue`
    - **План закрытия:** удалить таб «Чаты» из `ChannelsView`; оставить только «Каналы». Deep-link compatibility можно сохранить редиректом `?tab=chats` → `/app/chats`.

1. Для внешних CRM в production всё ещё требуется финальная валидация на реальных аккаунтах маркетплейсов amoCRM/Битрикс24 (боевые app credentials + реальный callback домен).
   - Файлы: `apps/integrations/oauth_api.py` (OAuth start/callback, после DEC-036), `apps/integrations/connections_api.py`, `apps/integrations/services.py`, `apps/integrations/adapters_amocrm.py`, `apps/integrations/adapters_bitrix24.py`
   - План закрытия: production-hardening этап (staging QA прогон marketplace install + webhook events + auto token refresh на реальных CRM tenant-ах)

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

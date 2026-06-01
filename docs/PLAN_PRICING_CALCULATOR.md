# План: калькулятор тарифа на лэндинге

**Статус:** draft, требует согласования перед стартом реализации.
**Дата:** 2026-06-01.
**Связанные документы:** [DECISIONS.md](DECISIONS.md) (DEC-038 SEO-лэндинг), [TASK_STATE.md](TASK_STATE.md).

## 0. Контекст и ключевые решения

Текущий лэндинг — серверный Django-шаблон [templates/landing.html](../templates/landing.html) с тремя статическими карточками (Simple/Basic/CRM по 900/1900/3900 ₽), забитыми HTML-ом (не из БД). Это намеренно (DEC-038: PageSpeed-оптимизация, без JS).

Новые тарифы (СОЛО 2990, КОМАНДА 5990, СВОБОДНЫЙ — калькулятор) — **полная замена прежней линейки**, а не дополнение. Решения по двум открытым вопросам зафиксированы:

- **Q1 — судьба simple/basic/crm:** мигрировать существующих тенантов на новую линейку (см. этап 2b).
- **Q2 — хранение кастомных лимитов СВОБОДНОГО:** `Tenant.custom_limits` (JSONField), один план-шаблон `free-custom`, лимиты как JSON-override на тенанте.

### Тарифная структура (исходник — задача пользователя)

| Параметр | СОЛО (2990 ₽) | КОМАНДА (5990 ₽) | СВОБОДНЫЙ (калькулятор) |
|----------|---------------|------------------|--------------------------|
| Пользователи | 1 | 5 | 1 пользователь = 1000 ₽ |
| Мессенджеры | Telegram, ВК + email | + MAX | 1 мессенджер = 1000 ₽ |
| Входящие каналы | ВК | + сайт, Авито | 1 канал = 1000 ₽ |
| Телефония | — | 1 номер, 5 линий, 1000 минут | по запросу |
| Документы | 100 / мес | 1000 / мес | 100 документов = 200 ₽ |
| Подписания | 20 / мес | 100 / мес | 50 подписаний = 500 ₽ |

## 1. Backend — модель тарифа и сидирование

### 1.1. Расширить модель `Plan` ([apps/billing/models.py](../apps/billing/models.py))

Текущие поля (`max_managers`, `max_contracts_per_month`, `max_crm_connections`, `max_pipelines`) не покрывают новую структуру лимитов. Добавить:

- `max_messengers PositiveIntegerField(null=True)` — лимит подключённых мессенджер-каналов (Telegram/WhatsApp/MAX); `null` = безлимит.
- `max_inbound_channels PositiveIntegerField(null=True)` — лимит входящих каналов (сайт/ВК/Авито).
- `max_signatures_per_month PositiveIntegerField(null=True)` — лимит подписаний/мес (отдельно от `max_contracts_per_month`).
- `telephony_included BooleanField(default=False)` — флаг базового включения телефонии.
- `max_phone_numbers PositiveIntegerField(null=True)`, `max_phone_lines PositiveIntegerField(null=True)`, `included_minutes PositiveIntegerField(null=True)`.
- `kind CharField(choices=[('preset','Предустановленный'),('custom','Конфигуратор')], default='preset')` — чтобы отличать тариф СВОБОДНЫЙ.
- `description TextField(blank=True)` — короткий маркетинговый текст под именем.

Миграция **`0005_plan_pricing_v2.py`** (schema-level — модель в public schema, `migrate_schemas --shared`).

### 1.2. Миграция данных `0006_seed_plans_solo_komanda.py`

- `Plan(slug='solo', name='СОЛО', price=2990)`:
  - `max_managers=1`, `max_messengers=2` (Telegram + ВК), `max_inbound_channels=1` (ВК), `telephony_included=False`, `max_signatures_per_month=20`, `max_contracts_per_month=100`.
  - features: `messenger_telegram`, `messenger_vk`, `email_notifications`, `channel_vk`, `contracts_basic`, `crm_builtin`.
- `Plan(slug='komanda', name='КОМАНДА', price=5990)`:
  - `max_managers=5`, `max_messengers=3` (+ MAX), `max_inbound_channels=3` (сайт, ВК, Авито), `telephony_included=True`, `max_phone_numbers=1`, `max_phone_lines=5`, `included_minutes=1000`, `max_signatures_per_month=100`, `max_contracts_per_month=1000`.
  - features: всё из СОЛО + `messenger_max`, `channel_avito`, `channel_site_widget`, `telephony_basic`, `distribution`.
- `Plan(slug='free-custom', name='СВОБОДНЫЙ', kind='custom', price=0)` — технический шаблон для расчётов; не отображается в селекторе планов внутри ЛК, не используется в `Payment.plan`. Цена считается на лету по формуле.
- Старые `simple/basic/crm` — деактивировать через `is_active=False`, не удалять (есть ссылка через `Payment.plan` ON_DELETE=PROTECT, плюс existing tenants).

### 1.3. Каталог фич ([apps/billing/migrations/0002_seed_default_plans.py](../apps/billing/migrations/0002_seed_default_plans.py))

Добавить недостающие коды фич в `FEATURE_CODES` (через миграцию-сидер 0006):
- `messenger_telegram`, `messenger_vk`, `messenger_max`, `messenger_whatsapp`
- `channel_vk`, `channel_avito`, `channel_site_widget`, `channel_email`
- `telephony_basic`, `contracts_basic`, `email_notifications`

### 1.4. Публичные endpoints для калькулятора

В [config/views.py](../config/views.py) (там же, где `landing_page`) добавить:

- `pricing_calculator_quote(request)` — `POST /api/public/pricing/quote/` (обычная Django view, без авторизации, без django-ninja).
  - Принимает JSON: `{users, messengers[], inbound_channels[], telephony: {requested: bool, lines?, minutes?}, signatures, documents}`.
  - Возвращает: `{monthly_total, breakdown: [{label, qty, unit_price, total}], telephony_requires_quote: bool, quote_id}`.
  - Логика расчёта — **серверная**, чтобы цены не подделывались на клиенте. Тарифные ставки берутся из `config/settings.py`:
    ```python
    PRICING_CUSTOM = {
        'user': 1000,
        'messenger': 1000,
        'inbound_channel': 1000,
        'documents_per_100': 200,
        'signatures_per_50': 500,
    }
    ```
  - Создаёт запись `PricingQuote` (UUID, TTL 24ч) — для применения цены при регистрации без перепроверки.

- `pricing_telephony_request(request)` — `POST /api/public/pricing/telephony-request/`. Принимает контакт (имя, телефон/email, конфигурация) → создаёт `TelephonyQuoteRequest` + асинхронно шлёт письмо на support через `send_mail` (`apps.notifications.tasks.send_email_async`).
  - Защита от спама: rate-limit по IP (1 запрос/мин), honeypot-поле в форме.

### 1.5. Endpoint для landing JSON

**Решение:** инлайнить JSON в Django-шаблон через `{{ pricing_config|json_script:"pricing-config" }}`. Это сохраняет инвариант DEC-038 (нулевые внешние запросы, 100 PageSpeed). Отдельный публичный endpoint `GET /api/public/pricing/config/` не нужен.

## 2. Лэндинг — секция «Тарифы»

### 2.1. Структура HTML ([templates/landing.html#L552-L595](../templates/landing.html))

Заменить текущий `#pricing` блок на три карточки + калькулятор:

```
[ СОЛО 2990 ₽ ]   [ КОМАНДА 5990 ₽ (Популярный) ]   [ СВОБОДНЫЙ — рассчитать ]
                                                       ↓ (раскрывается под карточкой)
                              ┌─── калькулятор ───┐
                              │ Пользователи [— 1 +] = 1000 ₽
                              │ Мессенджеры: ☐ TG ☐ WA ☐ MAX = +1000 ₽ за каждый
                              │ Каналы: ☐ Сайт ☐ ВК ☐ Авито = +1000 ₽ за каждый
                              │ Телефония: ☐ Нужна (по запросу) → форма
                              │ Документы [— 100 +] = +200 ₽ за каждые 100
                              │ Подписания [— 50 +] = +500 ₽ за каждые 50
                              │ ─────────────────────────────────
                              │ Итого в месяц: 4500 ₽
                              │ [ Зарегистрироваться ]  [ Оставить заявку ]
                              └────────────────────────┘
```

CTA-кнопка на пресетных карточках → `/register?plan=solo` или `/register?plan=komanda`. На СВОБОДНОМ → `/register?plan=free-custom&quote_id=<uuid>` после серверного подтверждения.

### 2.2. CSS / адаптив

Сохранить грид `.pricing-grid` (3 колонки). Калькулятор — отдельный блок `<div class="calculator">` под гридом, скрыт по умолчанию (`hidden` атрибут). Открывается по клику на «Рассчитать тариф» в карточке СВОБОДНОГО. На ≤640px — естественное схлопывание в 1 колонку (`@media (max-width:480px)` уже есть).

Все стили — инлайн в `<style>` блоке (инвариант DEC-038).

### 2.3. JavaScript калькулятора

Инлайн `<script>` в конце `<body>`, **vanilla JS** (без зависимостей — иначе сломаем PageSpeed):
- Чтение конфига из `<script id="pricing-config" type="application/json">…</script>` (Django `json_script`).
- Обработчики `input/change` на полях формы.
- Локальный пересчёт суммы в реальном времени (для UX).
- При сабмите формы — `fetch('/api/public/pricing/quote/', {method:'POST', body:JSON})` для серверного подтверждения цены + редирект на `/register?plan=free-custom&quote_id=<uuid>`.
- Серверный quote хранится в `apps.billing.PricingQuote` (TTL 24ч).

Целевой бюджет скрипта — ≤4 KB без минификации.

### 2.4. SEO/Accessibility

- ARIA: `<fieldset>` с `<legend>` для каждой группы опций, `aria-live="polite"` для итоговой суммы.
- Расширить JSON-LD `Offer` элементами для двух пресетов (текущий `SoftwareApplication` уже есть в [templates/landing.html#L643](../templates/landing.html)).
- FAQ-блок ([templates/landing.html#L666](../templates/landing.html)): добавить вопросы «Чем тарифы отличаются?», «Как работает СВОБОДНЫЙ?», «Как подключить телефонию?».

## 3. Регистрация и применение конфигурации

### 3.1. `RegisterView.vue` ([frontend/src/views/RegisterView.vue#L119](../frontend/src/views/RegisterView.vue))

- Принимать query `?plan=solo|komanda|free-custom&quote_id=<uuid>`.
- Для пресетов — выбрать соответствующий план в `plan_slug`.
- Для `free-custom` — показать pre-confirmed summary («Ваша конфигурация: 3 пользователя, Telegram + ВК, 100 документов; 4500 ₽/мес») и при сабмите — отправить `quote_id` вместе с регистрацией.
- Backend `register()` ([apps/users/auth_api.py](../apps/users/auth_api.py)) при `plan_slug=='free-custom'` + валидный `quote_id`: применяет лимиты из `PricingQuote` к созданному тенанту (записывает в `Tenant.custom_limits`).

### 3.2. Хранение кастомных лимитов

`Tenant.custom_limits: JSONField(default=dict, blank=True)`. Структура:
```json
{
  "max_managers": 3,
  "max_messengers": 2,
  "max_inbound_channels": 1,
  "max_signatures_per_month": 100,
  "max_contracts_per_month": 200,
  "telephony_included": false,
  "monthly_total": 4500,
  "quote_id": "uuid",
  "legacy_pricing": {"old_slug": "basic", "old_price": 1900}
}
```

В [apps/billing/usage.py](../apps/billing/usage.py) — единая функция `get_effective_limits(tenant) -> dict`:
```python
def get_effective_limits(tenant):
    if tenant.custom_limits:
        return tenant.custom_limits
    return {key: getattr(tenant.plan, f'max_{key}') for key in LIMIT_KEYS}
```

**Инвариант:** все feature-gating вызовы используют только `get_effective_limits()` — `Plan.max_*` напрямую больше не читается из api/access.

`Payment.amount` для `free-custom` берётся из `tenant.custom_limits['monthly_total']`, а не из `tenant.plan.price_monthly` (там 0).

### 3.3. Feature-gating

`apps/billing/usage.py` и `apps/core/access.py` — добавить проверки на новые лимиты (`max_messengers`, `max_inbound_channels`, `max_signatures_per_month`). Сейчас проверяется только `managers/contracts/pipelines/crm_connections`.

## 4. Запрос на телефонию

Телефония в СВОБОДНОМ — «по запросу», нужен ad-hoc контур:

- Модель `apps.billing.TelephonyQuoteRequest(name, email, phone, config_json, status=new|contacted|closed, created_at)` — public schema.
- API `POST /api/public/pricing/telephony-request/` (см. 1.4).
- Уведомление: `send_mail` на `settings.SUPPORT_EMAIL` через Celery (`apps.notifications.tasks.send_email_async`).
- Админка Django для просмотра заявок ([apps/billing/admin.py](../apps/billing/admin.py)).

## 5. Миграция существующих тенантов (этап 2b)

Решение по Q1 — мигрировать на новую линейку. Этап разворачивается отдельной миграцией данных, отделённой от сидера новых тарифов.

### 5.1. Маппинг

| Старый план | Новый план | Custom limits |
|-------------|-----------|---------------|
| `simple` | `solo` | — (стандартные лимиты СОЛО) |
| `basic` | `komanda` | — (стандартные лимиты КОМАНДА) |
| `crm` | `free-custom` | наследуя текущие лимиты `max_managers=∞`, всё включено |

### 5.2. Миграция данных `0007_migrate_tenants_to_v2_plans.py` (`migrate_schemas --shared`)

- Pre-flight assertion: посчитать тенантов на каждом старом плане и вывести в лог.
- Для каждого `Tenant` с активным платным планом:
  - Переустановить `tenant.plan_id` на новый план.
  - Если тенант на `crm` → сформировать `custom_limits` из фактических лимитов старого плана.
  - **Сохранение цены платных тенантов:** если у тенанта активная подписка — записать в `Tenant.custom_limits.legacy_pricing = {old_slug, old_price}` и **не повышать цену** до окончания текущего платёжного периода (через `Payment.amount`). Новая цена применится при следующей оплате.

### 5.3. Уведомление пользователей

Одноразовый email через `apps.notifications.tasks` всем `owner`'ам мигрированных тенантов с разъяснением изменений. Текст согласовать отдельно (вне scope этой задачи).

### 5.4. Rollback-план

Reverse-миграция возвращает `tenant.plan_id` на legacy через `custom_limits.legacy_pricing` (данные не теряются, откат за один SQL).

## 6. Документация и валидация

### 6.1. Артефакты документации (после реализации)

- `docs/DECISIONS.md` — **DEC-040: Тарифная линейка v2 с публичным калькулятором** (контекст, решение по схеме pricing, инвариант «расчёт цены — серверный», решения по Q1/Q2, rollback-план).
- `docs/TASK_STATE.md` — задача №33.
- `docs/DEV_LOG.md` — запись с датой и изменёнными файлами.
- `docs/RELEASE_NOTES.md` — пользовательская формулировка («Новые тарифы СОЛО и КОМАНДА, конструктор СВОБОДНЫЙ»).
- `docs/KNOWN_ISSUES.md` — пометить старые `simple/basic/crm` как deprecated.

### 6.2. Тесты

- `apps/billing/tests/test_pricing_calculator.py`:
  - расчёт `quote_view` для разных конфигов (включая граничные: 0 мессенджеров, 1000 документов)
  - rate-limit telephony-request
  - `quote_id` применяется при регистрации с `plan=free-custom`
  - quote истекает через 24ч
- Миграции `0005`/`0006`/`0007` имеют forward+backward пути; тест на сидирование («после `migrate_schemas --shared` СОЛО и КОМАНДА существуют»).
- Тест миграции 0007: имитировать тенант на `basic` → проверить, что после миграции он на `komanda` с сохранённым `legacy_pricing`.
- Frontend: vitest на парсер query-параметров `RegisterView`.

### 6.3. Валидация (Docker, по чеклисту [CLAUDE.md](../CLAUDE.md))

```bash
docker compose down && docker compose up -d --build
docker compose run --rm web python manage.py migrate_schemas --shared --noinput
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test apps.billing
docker compose exec frontend npm run typecheck && npm run build && npm run test
curl http://localhost:18100/ | grep -c 'СОЛО\|КОМАНДА\|СВОБОДНЫЙ'   # три карточки в HTML
curl -X POST http://localhost:18100/api/public/pricing/quote/ -H 'Content-Type: application/json' \
  -d '{"users":3,"messengers":["telegram","vk"],"inbound_channels":["site"],"documents":100,"signatures":50}'
# должно вернуть monthly_total=4500
```

Также — ручной браузер-QA (PageSpeed Insights до/после; целевой score ≥95).

## 7. Этапы реализации (порядок коммитов)

| # | Коммит | Файлы | Риск |
|---|--------|-------|------|
| 1 | Расширение модели `Plan` + миграция `0005` (`migrate_schemas --shared`) | `apps/billing/models.py`, новая миграция | Низкий — поля nullable |
| 2 | Сидер `0006` для СОЛО/КОМАНДА/СВОБОДНЫЙ + новые feature-коды; deactivate старых | `apps/billing/migrations/0006_*.py` | Средний — затрагивает existing tenants |
| 2b | Миграция данных `0007_migrate_tenants_to_v2_plans.py` + email-уведомление | новая миграция, `apps/notifications/tasks.py` | Высокий — затрагивает production-данные. Pre-flight assertion обязателен |
| 3 | `PricingQuote` + `TelephonyQuoteRequest` модели + public endpoints + tests | `apps/billing/models.py`, `apps/billing/public_views.py` (новый), `config/urls.py` | Низкий |
| 4 | Лэндинг: HTML карточек + JSON-конфиг + калькулятор JS + CSS | `templates/landing.html` | Низкий, изолировано |
| 5 | `RegisterView` + backend `register()` поддержка `quote_id`/`custom_limits` | `apps/users/auth_api.py`, `frontend/src/views/RegisterView.vue` | Средний — пограничные кейсы |
| 6 | Feature-gating новых лимитов (`max_messengers`, `max_inbound_channels`, `max_signatures_per_month`) через `get_effective_limits()` | `apps/billing/usage.py`, `apps/core/access.py` | Средний — нужна обратная совместимость для старых тенантов с `null` лимитами |
| 7 | Docs + RELEASE_NOTES + DEC-040 | `docs/*.md` | Нулевой |

Каждый этап — отдельный коммит. Между этапами 2 и 2b — валидация миграций на тестовом тенанте. **Этап 2b — обязательная ручная проверка pre-flight отчёта перед `migrate_schemas --shared` в production.**

## 8. Что НЕ входит в эту задачу

- Изменение flow оплаты ЮKassa (Payment.plan ссылается на план; для СВОБОДНОГО — план тот же `free-custom`, но сумма Payment.amount считается из `Tenant.custom_limits` × тарифных ставок).
- Recalculation на ходу для существующих тенантов (если они хотят добавить пользователей — отдельный flow «Управление подпиской», уже частично есть в `SubscriptionView`).
- Скидки/промокоды (явно out of scope).
- Калькулятор внутри ЛК (страница `/app/subscription`) — отдельная задача, может пере-использовать `pricing_calculator_quote` API.
- Текст email-уведомления о миграции — согласуется с продактом отдельно.

## 9. Открытые вопросы (закрыты)

- ~~Q1: Что делать с simple/basic/crm?~~ → **мигрировать** (этап 2b).
- ~~Q2: Как хранить кастомные лимиты СВОБОДНОГО?~~ → **`Tenant.custom_limits` JSONField**.

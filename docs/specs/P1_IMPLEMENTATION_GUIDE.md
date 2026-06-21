# P1 — детальное руководство по реализации (код-левел)

> **Статус:** предложение, готово к реализации по шагам. Код — скелеты на фактических
> конвенциях репозитория; перед коммитом адаптировать имена и прогнать валидационный гейт
> из `AGENTS.md`.
> **Охват:** Фаза 4 (Веб-формы захвата лидов + чат-виджет), Фаза 5 (Конструктор
> автоматизаций + SLA), Фаза 6 (Импорт/экспорт + дедупликация/слияние), Фаза 7 (Теги и
> сегменты). Карта всех фаз — `docs/specs/CRM_FEATURE_ROADMAP.md`; P0 — `docs/specs/P0_IMPLEMENTATION_GUIDE.md`.
> **Конвенции:** публичный обработчик с honeypot+rate-limit (`apps/billing/public_views.py`),
> shared-lookup «токен → тенант» (`apps/tenants/models.py::SigningTokenLookup`), исполнители
> действий (`apps/crm/services/auto_actions.py`), распределение `try_distribute`
> (`apps/distribution/services.py:122`), расписание `CELERY_BEAT_SCHEDULE`
> (`config/settings.py:183`), CSV-экспорт (`apps/audit/api.py:82`), ninja-роутер на общем
> `crm_router`, тесты на `TenantAPITestCase`.

## Маркировка уровней проверки

`[локально]` — тесты/сборка/типы; `[граница]` — живой вызов внешней системы/пакет на проводе;
`[сквозь]` — результат, наблюдаемый пользователем. P1 почти не имеет внешних границ: основной
риск — браузерный виджет (Фаза 4) и XLSX-парсинг (Фаза 6).

---

# ФАЗА 4 — Веб-формы захвата лидов и чат-виджет

## 4.1. Диаграмма потоков данных

```
КОНСТРУИРОВАНИЕ ФОРМЫ (внутри ЛК)
  WebFormsView ──POST /api/crm/webforms/──► webforms_api.create_webform
       │                                          │
       │                              генерируется public_token (UUID)
       │                              + запись WebFormLookup(token → tenant) в public-схеме
       └─◄── {id, public_token, embed_snippet} ◄──┘

ОТПРАВКА ЛИДА С САЙТА КЛИЕНТА (публично, без auth)
  Встроенный <script> на сайте клиента
       │  POST /api/public/webform/<token>/   {fields, website(honeypot)}
       ▼
  public_views.webform_submit          [csrf_exempt, honeypot, rate-limit по IP]
       │  WebFormLookup.objects.get(token) → tenant       ← резолв тенанта O(1)
       ▼
  schema_context(tenant.schema_name):
       │  Contact.objects.create(...) + Deal.objects.create(pipeline/stage из формы)
       │  try_distribute('new_lead', 'deal', deal.id)      ← переиспользуем распределение
       │  notify(tenant, 'new_deal_created', {...})
       └─◄── {status: 'ok'} ◄──────────────────────────────┘
```

## 4.2. Пошаговый чеклист задач

1. Создать модель `WebForm` (tenant-схема, `apps/crm/models.py`) и shared-lookup
   `WebFormLookup` (public-схема, `apps/tenants/models.py`) — раздел 4.3.
2. `makemigrations crm` и `makemigrations tenants`; проверить отсутствие дрейфа.
3. Схемы `WebFormIn/WebFormPatchIn` в `apps/crm/schemas.py` (раздел 4.4).
4. Добавить сущность `webforms` в `CRM_PERMISSION_ENTITIES` и дефолтные `RolePermission`.
5. Внутренний роутер `apps/crm/webforms_api.py` (CRUD + выдача embed-сниппета) и подключить
   импортом в `apps/crm/api.py` (раздел 4.5).
6. Публичный обработчик `webform_submit` в новом `apps/crm/public_views.py` (раздел 4.6);
   зарегистрировать маршрут `path('api/public/webform/<uuid:token>/', webform_submit)` в
   `config/urls.py` по образцу `pricing_telephony_request`.
7. Сервис создания лида из формы `apps/crm/services/webform_intake.py` (раздел 4.7).
8. Frontend ЛК: `WebFormsView.vue` (конструктор полей + предпросмотр + копирование сниппета),
   маршрут, пункт меню, типы/функции в `frontend/src/api/crm.ts`.
9. Встраиваемый виджет: отдельный лёгкий бандл `frontend/widget/` (раздел 4.8).
10. Feature-код `webforms` + лимит `max_webforms` в `Plan`.
11. Тесты backend (раздел 4.9).
12. Валидационный гейт (раздел 4.10).

## 4.3. Модели

`apps/crm/models.py` (tenant-схема):

```python
import uuid

class WebForm(models.Model):
    """Конструируемая форма захвата лида для встраивания на сайт клиента."""
    name = models.CharField(max_length=200)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    fields_schema = models.JSONField(default=list)   # [{key, label, type, required}]
    pipeline = models.ForeignKey('Pipeline', on_delete=models.PROTECT)
    stage = models.ForeignKey('Stage', on_delete=models.PROTECT)
    source = models.CharField(max_length=50, default='webform')
    auto_distribute = models.BooleanField(default=True)
    success_message = models.CharField(max_length=300, default='Спасибо! Мы свяжемся с вами.')
    allowed_origins = models.JSONField(default=list)  # ['https://client.ru'] для CORS-ограничения
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```

`apps/tenants/models.py` (public-схема, по образцу `SigningTokenLookup`):

```python
class WebFormLookup(models.Model):
    """Shared lookup: публичный токен формы → tenant schema (резолв O(1) без скана схем)."""
    token = models.UUIDField(unique=True, db_index=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='webform_tokens')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.token} -> {self.tenant_id}'
```

> Инвариант: `WebFormLookup` создаётся/обновляется в той же транзакции, что и `WebForm`;
> `token` совпадает с `WebForm.public_token`. При деактивации формы — `is_active=False` в обоих.

## 4.4. Схемы (`apps/crm/schemas.py`)

```python
class WebFormFieldSchema(Schema):
    key: str
    label: str
    type: str = 'text'      # text | email | phone | textarea | select
    required: bool = False
    options: list[str] = []

class WebFormIn(Schema):
    name: str
    fields_schema: list[WebFormFieldSchema] = []
    pipeline_id: int
    stage_id: int
    source: str = 'webform'
    auto_distribute: bool = True
    success_message: str = 'Спасибо! Мы свяжемся с вами.'
    allowed_origins: list[str] = []
    is_active: bool = True

class WebFormPatchIn(Schema):
    name: str | None = None
    fields_schema: list[WebFormFieldSchema] | None = None
    pipeline_id: int | None = None
    stage_id: int | None = None
    auto_distribute: bool | None = None
    success_message: str | None = None
    allowed_origins: list[str] | None = None
    is_active: bool | None = None
```

## 4.5. Внутренний API (`apps/crm/webforms_api.py`)

```python
from __future__ import annotations

from django.db import transaction
from django_tenants.utils import schema_context

from apps.audit.services import log_event
from apps.core.access import require_crm_permission
from apps.core.tenant import get_request_tenant

from ._api_common import _ensure_builtin, _scoped_object_or_error, crm_router
from .models import WebForm
from .schemas import WebFormIn, WebFormPatchIn


def _embed_snippet(request, token) -> str:
    base = f'{request.scheme}://{request.get_host()}'
    return (
        f'<script src="{base}/widget/crm-webform.js" '
        f'data-token="{token}" data-base="{base}" async></script>'
    )


@crm_router.get('/webforms/')
def list_webforms(request):
    require_crm_permission(request, 'webforms', 'view')
    _ensure_builtin(request)
    return [
        {'id': f.id, 'name': f.name, 'public_token': str(f.public_token),
         'pipeline_id': f.pipeline_id, 'stage_id': f.stage_id, 'is_active': f.is_active,
         'embed_snippet': _embed_snippet(request, f.public_token)}
        for f in WebForm.objects.all().order_by('-created_at')
    ]


@crm_router.post('/webforms/')
def create_webform(request, payload: WebFormIn):
    require_crm_permission(request, 'webforms', 'create')
    _ensure_builtin(request)
    tenant = get_request_tenant(request)
    data = payload.dict()
    with transaction.atomic():
        form = WebForm.objects.create(
            name=data['name'],
            fields_schema=data['fields_schema'],
            pipeline_id=data['pipeline_id'], stage_id=data['stage_id'],
            source=data['source'], auto_distribute=data['auto_distribute'],
            success_message=data['success_message'], allowed_origins=data['allowed_origins'],
        )
        # lookup живёт в public-схеме — пишем вне tenant-контекста
        with schema_context('public'):
            from apps.tenants.models import WebFormLookup
            WebFormLookup.objects.create(token=form.public_token, tenant=tenant)
    log_event(request, action='create', instance=form)
    return {'id': form.id, 'public_token': str(form.public_token),
            'embed_snippet': _embed_snippet(request, form.public_token)}
```

> `patch_webform`/`delete_webform` — по образцу остальных CRM-эндпоинтов; при деактивации
> синхронно обновлять `WebFormLookup.is_active`.

## 4.6. Публичный обработчик (`apps/crm/public_views.py`)

```python
"""Публичный приём веб-форм. Резолв тенанта по токену через shared-lookup.
Паттерн полностью повторяет apps/billing/public_views.py (honeypot + rate-limit)."""
from __future__ import annotations

import json
import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_tenants.utils import schema_context

logger = logging.getLogger('crm.webform')


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', 'unknown')


@csrf_exempt
def webform_submit(request, token):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    if data.get('website'):                       # honeypot
        return JsonResponse({'detail': 'Bad request'}, status=400)

    client_ip = _get_client_ip(request)
    cache_key = f'webform:{token}:{client_ip}'
    if cache.get(cache_key):
        return JsonResponse({'detail': 'Слишком много запросов.'}, status=429)
    cache.set(cache_key, True, timeout=60)

    with schema_context('public'):
        from apps.tenants.models import WebFormLookup
        lookup = WebFormLookup.objects.filter(token=token, is_active=True).select_related('tenant').first()
    if not lookup:
        return JsonResponse({'detail': 'Form not found'}, status=404)

    with schema_context(lookup.tenant.schema_name):
        from apps.crm.services.webform_intake import intake_webform_submission
        result = intake_webform_submission(lookup.tenant, token, data.get('fields', {}))
    if not result:
        return JsonResponse({'detail': 'Form inactive'}, status=404)
    logger.info('webform submit token=%s deal=%s', token, result['deal_id'])
    return JsonResponse({'status': 'ok', 'message': result['success_message']})
```

Регистрация в `config/urls.py` (по образцу строк 39–42, секция публичных путей):

```python
from apps.crm.public_views import webform_submit
# ...
path('api/public/webform/<uuid:token>/', webform_submit),
```

## 4.7. Сервис приёма (`apps/crm/services/webform_intake.py`)

```python
from __future__ import annotations

from apps.crm.models import Contact, Deal, WebForm
from apps.distribution.services import ensure_builtin_manager_profiles, try_distribute
from apps.notifications.services import notify


def intake_webform_submission(tenant, token, fields: dict) -> dict | None:
    form = WebForm.objects.filter(public_token=token, is_active=True).first()
    if not form:
        return None
    contact = Contact.objects.create(
        first_name=fields.get('name', '') or 'Лид с формы',
        phone=fields.get('phone', ''), email=fields.get('email', ''),
        source=form.source, custom_fields={k: v for k, v in fields.items()
                                           if k not in ('name', 'phone', 'email')},
    )
    deal = Deal.objects.create(
        name=f'Заявка с формы «{form.name}»',
        pipeline=form.pipeline, stage=form.stage, contact=contact, source=form.source,
    )
    if form.auto_distribute:
        ensure_builtin_manager_profiles()
        try_distribute('new_lead', 'deal', str(deal.id))
    notify(tenant, 'new_deal_created', {'deal_id': deal.id, 'link': f'/app/deals/{deal.id}'})
    return {'deal_id': deal.id, 'success_message': form.success_message}
```

## 4.8. Встраиваемый виджет (`frontend/widget/`)

Отдельный лёгкий бандл (Vite library mode, без зависимостей от SPA), собираемый в
`frontend/public/widget/crm-webform.js`. Скрипт читает `data-token`/`data-base` из тега,
запрашивает описание формы (публичный `GET /api/public/webform/<token>/schema/`), рендерит
поля и шлёт `POST`. Виджет исполняется в браузере клиента — это `[сквозь]`-граница, в
dev проверяется на тестовой странице.

```javascript
// frontend/widget/crm-webform.js  (точка входа library-сборки)
(function () {
  const tag = document.currentScript;
  const token = tag.getAttribute('data-token');
  const base = tag.getAttribute('data-base');
  const mount = document.createElement('div');
  tag.parentNode.insertBefore(mount, tag);

  fetch(`${base}/api/public/webform/${token}/schema/`)
    .then(r => r.json())
    .then(schema => renderForm(mount, schema, token, base));

  function renderForm(el, schema, token, base) {
    const form = document.createElement('form');
    // honeypot
    form.innerHTML = '<input name="website" style="display:none" tabindex="-1" autocomplete="off">';
    schema.fields.forEach(f => { /* строим input по f.type/f.required */ });
    form.addEventListener('submit', ev => {
      ev.preventDefault();
      const fields = collect(form);
      fetch(`${base}/api/public/webform/${token}/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields, website: form.website.value }),
      }).then(r => r.json()).then(res => { el.innerHTML = `<p>${res.message || 'Спасибо!'}</p>`; });
    });
    el.appendChild(form);
  }
})();
```

> Для `GET …/schema/` добавить публичный обработчик, отдающий `fields_schema` формы и
> `success_message`, с тем же резолвом по `WebFormLookup`. CORS публичных endpoint-ов
> ограничить `allowed_origins` формы.

## 4.9. Тесты (`apps/crm/tests/test_webforms.py`)

```python
class WebFormIntakeTest(TenantAPITestCase):
    def test_submission_creates_contact_deal_and_distributes(self):
        pipeline = Pipeline.objects.create(name='P', is_default=True)
        stage = Stage.objects.create(pipeline=pipeline, name='New', stage_type='open')
        form = WebForm.objects.create(name='Сайт', pipeline=pipeline, stage=stage)
        from apps.crm.services.webform_intake import intake_webform_submission
        res = intake_webform_submission(self.tenant, form.public_token,
                                        {'name': 'Иван', 'phone': '+7900', 'comment': 'тест'})
        self.assertIsNotNone(res)
        deal = Deal.objects.get(id=res['deal_id'])
        self.assertEqual(deal.contact.first_name, 'Иван')
        self.assertEqual(deal.contact.custom_fields.get('comment'), 'тест')
```

## 4.10. Критерии приёмки Фазы 4

1. `[локально]` Миграции без дрейфа; `ruff`/тесты/typecheck/build зелёные.
2. `[локально]` Honeypot (`website` заполнен) → 400; повторный POST с того же IP за минуту → 429 (тест).
3. `[сквозь]` На тестовой HTML-странице вставлен сниппет; отправка формы создаёт контакт и
   сделку в нужной воронке/стадии, срабатывает распределение, приходит уведомление.
4. `[сквозь]` Деактивация формы в ЛК делает публичный endpoint недоступным (404).
5. Обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# ФАЗА 5 — Конструктор автоматизаций и SLA

## 5.1. Диаграмма потоков данных

```
СОБЫТИЙНЫЙ ТРИГГЕР (синхронно, уже есть точки вызова)
  move_deal / create_deal / webform_intake ──► evaluate_event_rules(event, deal)
       │                                              │
       │                              AutomationRule.objects.filter(trigger=event, is_active)
       │                              + _match_filter(rule.conditions, deal)
       ▼
  execute_action(rule.action, deal)   ← переиспользуем исполнители из auto_actions.py

ВРЕМЕННОЙ ТРИГГЕР / SLA (асинхронно, новый beat)
  CELERY_BEAT_SCHEDULE: evaluate_time_rules каждые 15 мин
       │  для каждого тенанта, для каждого правила trigger='no_activity'/'sla_breach':
       ▼
  находит сделки: последняя Activity старше N дней / стадия висит дольше SLA
       │  идемпотентность: AutomationRunLog(rule, deal, fired_at) — не повторять
       ▼
  execute_action(...)  → создать задачу / уведомить / сменить ответственного
```

## 5.2. Пошаговый чеклист задач

1. Создать модели `AutomationRule`, `AutomationRunLog` (tenant-схема) — раздел 5.3.
2. `makemigrations crm` (или новое приложение `apps/automation`); проверить дрейф.
3. Вынести исполнители действий из `process_stage_change` в переиспользуемую функцию
   `execute_action(action: dict, deal)` в `apps/crm/services/auto_actions.py` (раздел 5.4),
   сохранив обратную совместимость существующего `process_stage_change`.
4. Реализовать `evaluate_event_rules(event, deal)` и врезать вызов в `create_deal`,
   `move_deal`, `webform_intake` рядом с существующими `notify(...)`.
5. Реализовать beat-задачу `evaluate_time_rules` в `apps/crm/tasks.py` (раздел 5.5) и
   зарегистрировать в `CELERY_BEAT_SCHEDULE` (`config/settings.py:183`).
6. Внутренний API `apps/crm/automation_api.py` (CRUD правил) + права `automation`.
7. Frontend: `AutomationView.vue` — конструктор «если (триггер + условия) → то (действие)».
8. Тесты на идемпотентность и срабатывание (раздел 5.6).
9. Валидационный гейт (раздел 5.7).

## 5.3. Модели

```python
class AutomationRule(models.Model):
    TRIGGERS = [
        ('new_deal', 'Создана сделка'),
        ('stage_changed', 'Смена стадии'),
        ('no_activity', 'Нет активности N дней'),
        ('sla_breach', 'Превышен SLA на стадии'),
    ]
    name = models.CharField(max_length=200)
    trigger = models.CharField(max_length=20, choices=TRIGGERS)
    conditions = models.JSONField(default=dict)   # {pipeline_id, stage_id, days, ...}
    action = models.JSONField(default=dict)       # {type: 'create_task'|'send_notification'|'change_stage'|'assign', ...}
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority', 'id']


class AutomationRunLog(models.Model):
    """Гарантия идемпотентности: одно правило не срабатывает по одной сделке повторно
    в пределах окна (для time-based триггеров)."""
    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='runs')
    deal = models.ForeignKey('Deal', on_delete=models.CASCADE, related_name='automation_runs')
    fired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['rule', 'deal']
        indexes = [models.Index(fields=['rule', 'deal'])]
```

## 5.4. Переиспользуемый исполнитель (`apps/crm/services/auto_actions.py`)

```python
def execute_action(action: dict, deal: Deal):
    """Единая точка исполнения действия. Используется и stage-auto-action, и AutomationRule."""
    action_type = action.get('type')
    if action_type == 'create_task':
        Activity.objects.create(
            activity_type='task', deal=deal, responsible=deal.responsible,
            title=action.get('title', 'Новая задача'), status='planned',
            due_date=timezone.now() + timedelta(days=int(action.get('days_offset', 1))),
            created_by=deal.responsible,
        )
    elif action_type == 'create_document':
        template = DocumentTemplate.objects.get(id=action['template_id'])
        create_document_from_deal(deal, template)
    elif action_type == 'send_notification':
        from django.db import connection
        notify(connection.tenant, action.get('event', 'deal_stage_changed'),
               {'deal_id': deal.id, 'link': f'/app/deals/{deal.id}'})
    elif action_type == 'change_stage':
        new_stage = Stage.objects.get(id=action['stage_id'], pipeline_id=deal.pipeline_id)
        deal.stage = new_stage
        deal.save(update_fields=['stage'])
    elif action_type == 'assign':
        deal.responsible_id = action['responsible_id']
        deal.save(update_fields=['responsible'])


def process_stage_change(deal, old_stage, new_stage):   # обёртка для обратной совместимости
    if new_stage.auto_action:
        execute_action(new_stage.auto_action, deal)


def evaluate_event_rules(event: str, deal: Deal):
    from apps.crm.models import AutomationRule
    for rule in AutomationRule.objects.filter(trigger=event, is_active=True).order_by('-priority'):
        if _match_conditions(rule.conditions, deal):
            execute_action(rule.action, deal)


def _match_conditions(conditions: dict, deal: Deal) -> bool:
    if conditions.get('pipeline_id') and conditions['pipeline_id'] != deal.pipeline_id:
        return False
    if conditions.get('stage_id') and conditions['stage_id'] != deal.stage_id:
        return False
    return True
```

## 5.5. Beat-задача времени (`apps/crm/tasks.py`)

```python
@shared_task
def evaluate_time_rules():
    """Time-based автоматизация: нет активности N дней / SLA на стадии. Идемпотентна
    через AutomationRunLog (unique_together rule+deal)."""
    from django_tenants.utils import schema_context, get_tenant_model
    from django.utils import timezone
    from datetime import timedelta
    from apps.crm.models import AutomationRule, AutomationRunLog, Deal, Activity
    from apps.crm.services.auto_actions import execute_action

    for tenant in get_tenant_model().objects.exclude(schema_name='public'):
        with schema_context(tenant.schema_name):
            for rule in AutomationRule.objects.filter(trigger='no_activity', is_active=True):
                days = int(rule.conditions.get('days', 3))
                threshold = timezone.now() - timedelta(days=days)
                deals = Deal.objects.filter(stage__stage_type='open').exclude(
                    automation_runs__rule=rule)            # ещё не срабатывало
                for deal in deals:
                    last = Activity.objects.filter(deal=deal).order_by('-created_at').first()
                    last_at = last.created_at if last else deal.created_at
                    if last_at < threshold and _match_conditions(rule.conditions, deal):
                        execute_action(rule.action, deal)
                        AutomationRunLog.objects.get_or_create(rule=rule, deal=deal)
```

Регистрация (`config/settings.py`, внутри `CELERY_BEAT_SCHEDULE`):

```python
    'evaluate-automation-time-rules-every-15-min': {
        'task': 'apps.crm.tasks.evaluate_time_rules',
        'schedule': timedelta(minutes=15),
    },
```

## 5.6. Тесты (`apps/crm/tests/test_automation.py`)

```python
class AutomationTest(TenantAPITestCase):
    def test_no_activity_rule_fires_once(self):
        # сделка без активности > N дней → создаётся задача, повторный прогон не дублирует
        ...
        evaluate_time_rules()
        self.assertEqual(Activity.objects.filter(activity_type='task', deal=self.deal).count(), 1)
        evaluate_time_rules()   # повтор
        self.assertEqual(Activity.objects.filter(activity_type='task', deal=self.deal).count(), 1)
```

## 5.7. Критерии приёмки Фазы 5

1. `[локально]` Миграции без дрейфа; `ruff`/typecheck/build зелёные; тест идемпотентности проходит.
2. `[локально]` Существующий `process_stage_change` сохраняет поведение (тест `test_auto_actions.py` не падает).
3. `[сквозь]` Правило «нет активности 3 дня → задача ответственному» создаёт ровно одну задачу;
   правило «смена стадии → уведомление» срабатывает при перемещении сделки.
4. Защита от зацикливания: действие `change_stage` не вызывает повторную событийную оценку
   того же правила (через `AutomationRunLog` для time-based и фильтр стадии для событийных).
5. Обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# ФАЗА 6 — Импорт/экспорт и дедупликация/слияние

## 6.1. Диаграмма потоков данных

```
ИМПОРТ
  ImportView ──POST /api/crm/import/preview/ (файл)──► парсинг → колонки + первые 10 строк
       │                                                     (маппинг колонок на поля делает пользователь)
  ImportView ──POST /api/crm/import/run/ (mapping)──► import_records.delay(schema, entity, rows, mapping)
       │                                                     │  [Celery, батчами]
       │                                          для каждой строки: dedup → create/update
       └─◄── job_id ◄── ImportJob(status, processed, errors[]) ◄┘  (поллинг статуса)

ЭКСПОРТ
  ExportView ──GET /api/crm/export/contacts/?filters──► csv.writer → HttpResponse text/csv
       (паттерн apps/audit/api.py:82)

ДЕДУПЛИКАЦИЯ/СЛИЯНИЕ
  DuplicatesView ──GET /api/crm/duplicates/contacts/──► группы по phone/email/inn
  DuplicatesView ──POST /api/crm/contacts/merge/ {primary_id, merged_ids}──►
       перенос Deal/Activity на primary → удаление дублей → лог в аудит
```

## 6.2. Пошаговый чеклист задач

1. Добавить зависимость `openpyxl` в `requirements.txt` для XLSX (CSV — stdlib `csv`).
   **Прочитать контракт `openpyxl` (load_workbook, iter_rows) до кода.**
2. Создать модель `ImportJob` (tenant-схема) — раздел 6.3.
3. `makemigrations`; проверить дрейф.
4. Парсер файла `apps/crm/services/import_export.py` (раздел 6.4) — изолирует stdlib `csv`
   и `openpyxl`.
5. Celery-задача `import_records` с батчами и дедупом (раздел 6.5).
6. API: `import/preview`, `import/run`, `import/jobs/{id}`, `export/<entity>`,
   `duplicates/<entity>`, `<entity>/merge` в `apps/crm/import_api.py` (раздел 6.6).
7. Сервис слияния `apps/crm/services/merge.py` (раздел 6.7).
8. Frontend: мастер импорта (загрузка → маппинг → предпросмотр → результат), кнопки экспорта,
   экран дублей со слиянием.
9. Тесты (раздел 6.8).
10. Валидационный гейт (раздел 6.9).

## 6.3. Модель `ImportJob`

```python
class ImportJob(models.Model):
    STATUS = [('pending', 'В очереди'), ('running', 'Выполняется'),
              ('done', 'Завершён'), ('failed', 'Ошибка')]
    entity = models.CharField(max_length=20)       # contacts | companies | deals
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list)        # [{row, message}]
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

## 6.4. Парсер (`apps/crm/services/import_export.py`)

```python
"""Импорт/экспорт. Изолирует stdlib csv и openpyxl.
Контракт openpyxl читать до кода (load_workbook, ws.iter_rows)."""
from __future__ import annotations

import csv
import io


def parse_file(filename: str, content: bytes) -> tuple[list[str], list[dict]]:
    """Возвращает (заголовки, строки-словари). Поддержка .csv и .xlsx."""
    if filename.lower().endswith('.csv'):
        text = content.decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return (reader.fieldnames or [], rows)
    if filename.lower().endswith('.xlsx'):
        from openpyxl import load_workbook   # TODO: сверить с контрактом openpyxl
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = [str(h) for h in next(rows_iter)]
        rows = [dict(zip(headers, [('' if v is None else v) for v in r])) for r in rows_iter]
        return (headers, rows)
    raise ValueError('Поддерживаются только .csv и .xlsx')


def export_contacts_csv(queryset) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'first_name', 'last_name', 'phone', 'email', 'company', 'source', 'created_at'])
    for c in queryset:
        writer.writerow([c.id, c.first_name, c.last_name, c.phone, c.email,
                         c.company.name if c.company else '', c.source, c.created_at.isoformat()])
    return buf.getvalue()
```

## 6.5. Celery-импорт (`apps/crm/tasks.py`)

```python
@shared_task
def import_records(schema_name: str, job_id: int, entity: str, rows: list[dict], mapping: dict):
    """mapping: {csv_column -> model_field}. Дедуп по phone/email (contacts) / inn (companies)."""
    from django_tenants.utils import schema_context
    from apps.crm.models import Contact, Company, ImportJob

    with schema_context(schema_name):
        job = ImportJob.objects.get(id=job_id)
        job.status, job.total = 'running', len(rows)
        job.save(update_fields=['status', 'total'])
        for i, raw in enumerate(rows):
            try:
                data = {field: raw.get(col, '') for col, field in mapping.items()}
                if entity == 'contacts':
                    dup = Contact.objects.filter(phone=data.get('phone')).first() if data.get('phone') else None
                    if dup:
                        for k, v in data.items():
                            setattr(dup, k, v or getattr(dup, k))
                        dup.save()
                        job.updated += 1
                    else:
                        Contact.objects.create(**data)
                        job.created += 1
                # companies/deals — аналогично, дедуп по inn / по name+contact
            except Exception as exc:  # noqa: BLE001 — построчная устойчивость импорта
                job.errors.append({'row': i + 2, 'message': str(exc)})
            job.processed = i + 1
            if (i + 1) % 50 == 0:
                job.save(update_fields=['processed', 'created', 'updated', 'errors'])
        job.status = 'done'
        job.save()
```

## 6.6. Экспорт-эндпоинт (паттерн `apps/audit/api.py:82`)

```python
@crm_router.get('/export/contacts/')
def export_contacts(request, source: str | None = None):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    from django.http import HttpResponse
    from apps.crm.services.import_export import export_contacts_csv
    qs = filter_crm_queryset_by_scope(request, Contact.objects.select_related('company').all(), 'contacts')
    if source:
        qs = qs.filter(source=source)
    response = HttpResponse(export_contacts_csv(qs), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="contacts.csv"'
    return response
```

## 6.7. Слияние (`apps/crm/services/merge.py`)

```python
from django.db import transaction
from apps.crm.models import Activity, Contact, Deal


@transaction.atomic
def merge_contacts(primary_id: int, merged_ids: list[int]) -> dict:
    primary = Contact.objects.get(id=primary_id)
    moved_deals = Deal.objects.filter(contact_id__in=merged_ids).update(contact=primary)
    moved_acts = Activity.objects.filter(contact_id__in=merged_ids).update(contact=primary)
    # заполняем пустые поля primary из дублей
    for dup in Contact.objects.filter(id__in=merged_ids):
        for f in ('phone', 'email', 'position'):
            if not getattr(primary, f) and getattr(dup, f):
                setattr(primary, f, getattr(dup, f))
    primary.save()
    Contact.objects.filter(id__in=merged_ids).delete()
    return {'primary_id': primary_id, 'moved_deals': moved_deals, 'moved_activities': moved_acts}
```

> Слияние необратимо — endpoint требует подтверждения на фронте и пишется в аудит через
> `log_event(request, action='update', instance=primary, changes={'Слияние': ...})`.

## 6.8. Тесты (`apps/crm/tests/test_import_merge.py`)

```python
class ImportMergeTest(TenantAPITestCase):
    def test_csv_parse_and_dedup_by_phone(self):
        from apps.crm.services.import_export import parse_file
        content = 'name,phone\nИван,+7900\nИван2,+7900\n'.encode()
        headers, rows = parse_file('x.csv', content)
        self.assertEqual(headers, ['name', 'phone'])
        self.assertEqual(len(rows), 2)

    def test_merge_moves_deals_to_primary(self):
        a = Contact.objects.create(first_name='A', phone='+7900')
        b = Contact.objects.create(first_name='B', phone='+7900')
        deal = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.stage, contact=b)
        from apps.crm.services.merge import merge_contacts
        res = merge_contacts(a.id, [b.id])
        deal.refresh_from_db()
        self.assertEqual(deal.contact_id, a.id)
        self.assertFalse(Contact.objects.filter(id=b.id).exists())
```

## 6.9. Критерии приёмки Фазы 6

1. `[локально]` `openpyxl` добавлен в requirements; миграции без дрейфа; `ruff`/typecheck/build зелёные; тесты парсинга и слияния проходят.
2. `[сквозь]` Импорт CSV и XLSX контактов создаёт записи, дубли по телефону обновляются, а не
   дублируются; отчёт `ImportJob.errors` показывает проблемные строки с номером.
3. `[сквозь]` Экспорт контактов отдаёт CSV с учётом фильтров; файл открывается в Excel
   (кодировка `utf-8-sig`).
4. `[сквозь]` Слияние переносит сделки и активности на основной контакт и удаляет дубли;
   операция зафиксирована в аудите.
5. Обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# ФАЗА 7 — Теги и сегменты

## 7.1. Диаграмма потоков данных

```
ТЕГИ
  TagsManager ──POST /api/crm/tags/──► Tag.objects.create
  карточка контакта/сделки ──PATCH .../tags/ {tag_ids}──► M2M set
  списки ──GET /api/crm/contacts/?tag_id=──► filter(tags__id=...)

СЕГМЕНТЫ (сохранённые фильтры)
  SegmentsView ──POST /api/crm/segments/ {filters}──► Segment.objects.create
  списки ──GET /api/crm/contacts/?segment_id=──► применяем сохранённые filters
```

## 7.2. Пошаговый чеклист задач

1. Создать модели `Tag`, `Segment` (tenant-схема) с M2M к `Contact`/`Deal` — раздел 7.3.
2. `makemigrations`; проверить дрейф.
3. Схемы `TagIn`, `SegmentIn` и `TagAssignIn` в `apps/crm/schemas.py`.
4. API `apps/crm/tags_api.py` — CRUD тегов/сегментов + назначение тегов сущности (раздел 7.4).
5. Расширить фильтрацию списков `contacts`/`deals` параметрами `tag_id`/`segment_id`.
6. Frontend: компонент мультиселекта тегов в карточках; фильтр по тегам/сегментам в списках;
   типы/функции в `crm.ts`.
7. Тесты (раздел 7.5).
8. Валидационный гейт.

## 7.3. Модели

```python
class Tag(models.Model):
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=7, default='#6366F1')
    contacts = models.ManyToManyField('Contact', blank=True, related_name='tags')
    deals = models.ManyToManyField('Deal', blank=True, related_name='tags')

    class Meta:
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['name'], name='uniq_tag_name')]

    def __str__(self):
        return self.name


class Segment(models.Model):
    """Именованный сохранённый фильтр (для списков и будущих рассылок, Фаза 8)."""
    ENTITY = [('contacts', 'Контакты'), ('deals', 'Сделки')]
    name = models.CharField(max_length=120)
    entity = models.CharField(max_length=20, choices=ENTITY)
    filters = models.JSONField(default=dict)   # {tag_ids, source, stage_id, ...}
    created_at = models.DateTimeField(auto_now_add=True)
```

## 7.4. API (`apps/crm/tags_api.py`)

```python
@crm_router.get('/tags/')
def list_tags(request):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    return [{'id': t.id, 'name': t.name, 'color': t.color} for t in Tag.objects.all()]


@crm_router.post('/tags/')
def create_tag(request, payload: TagIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    tag = Tag.objects.create(name=payload.name, color=payload.color)
    return {'id': tag.id}


@crm_router.patch('/contacts/{contact_id}/tags/')
def set_contact_tags(request, contact_id: int, payload: TagAssignIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    contact = _scoped_object_or_error(request, Contact, contact_id, entity='contacts', action='update')
    contact.tags.set(Tag.objects.filter(id__in=payload.tag_ids))
    return {'detail': 'ok'}
```

Расширение фильтрации (в существующем `list_contacts`):

```python
    tag_id: int | None = None,
    segment_id: int | None = None,
    # ...
    if tag_id:
        qs = qs.filter(tags__id=tag_id)
    if segment_id:
        seg = Segment.objects.filter(id=segment_id).first()
        if seg and seg.filters.get('tag_ids'):
            qs = qs.filter(tags__id__in=seg.filters['tag_ids'])
```

## 7.5. Тесты (`apps/crm/tests/test_tags.py`)

```python
class TagsTest(TenantAPITestCase):
    def test_assign_and_filter_by_tag(self):
        tag = Tag.objects.create(name='VIP')
        c = Contact.objects.create(first_name='Иван')
        c.tags.add(tag)
        self.assertEqual(Contact.objects.filter(tags__id=tag.id).count(), 1)
```

## 7.6. Критерии приёмки Фазы 7

1. `[локально]` Миграции без дрейфа; `ruff`/тесты/typecheck/build зелёные.
2. `[сквозь]` Тег создаётся, назначается контакту/сделке, список фильтруется по тегу.
3. `[сквозь]` Сегмент сохраняет набор условий и переиспользуется в фильтре списка; готов как
   источник аудитории для рассылок Фазы 8.
4. Обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# Общий порядок реализации и валидации (P1)

1. Фазы P1 независимы; Фаза 7 (теги/сегменты) — предпосылка Фазы 8 (рассылки) из P2, поэтому
   её разумно делать раньше остальных P2-работ.
2. Внешних границ в P1 минимум: браузерный виджет (Фаза 4) и `openpyxl` (Фаза 6). Перед кодом
   виджета проверить его на тестовой странице; перед XLSX-импортом прочитать контракт `openpyxl`.
3. Гейт завершения каждой фазы: `docker compose down && up -d --build`, `manage.py check`
   (0 issues), `makemigrations --check` (без дрейфа), `ruff check .`, целевые backend-тесты,
   `npm run typecheck`/`build`/`test`, ручная HTTP-проверка экранов.
4. Update Ritual (`AGENTS.md`): новый DEC на каждую фазу, статус в TASK_STATE, запись в
   DEV_LOG, RELEASE_NOTES на русском для видимых пользователю изменений; для веб-форм и
   импорта зафиксировать в KNOWN_ISSUES остаточные ограничения первой версии (CORS/каптча,
   форматы файлов).
5. Коммит и индексацию выполняет пользователь; агент останавливается после прохождения гейта.
```

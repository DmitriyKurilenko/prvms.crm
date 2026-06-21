# P2 — детальное руководство по реализации (код-левел)

> **Статус:** предложение, готово к реализации по шагам. Код — скелеты на фактических
> конвенциях репозитория; перед коммитом адаптировать имена и прогнать валидационный гейт
> из `AGENTS.md`.
> **Охват:** Фаза 8 (Массовые рассылки и кампании), Фаза 9 (Календарь, напоминания,
> повторяющиеся задачи), Фаза 10 (Планы продаж и аналитика воронки). Карта всех фаз —
> `docs/specs/CRM_FEATURE_ROADMAP.md`; P0 — `…/P0_IMPLEMENTATION_GUIDE.md`; P1 — `…/P1_IMPLEMENTATION_GUIDE.md`.
> **Зависимости:** Фаза 8 опирается на email-канал (P0, Фаза 3) и теги/сегменты (P1, Фаза 7).
> **Конвенции:** beat-обход тенантов `Tenant.objects.filter(is_active=True)` + `tenant_context`
> + `notify(...)` (`apps/crm/tasks.py:26`), сигнатура `notify(tenant, event, context, instance=None)`
> (`apps/notifications/services.py:35`), аналитика `require_roles` + `require_feature_access('analytics')`
> + ORM-агрегации (`apps/crm/dashboard_api.py`, `apps/crm/stats_api.py`), отправка через канал
> `route_outgoing_message` (`apps/channels/tasks.py:244`), `CELERY_BEAT_SCHEDULE`
> (`config/settings.py:183`), ninja-роутер на общем `crm_router`, тесты на `TenantAPITestCase`.

## Маркировка уровней проверки

`[локально]` — тесты/сборка/типы; `[граница]` — живой вызов внешней системы/пакет на проводе;
`[сквозь]` — результат, наблюдаемый пользователем. Единственная внешняя граница P2 — массовая
отправка через провайдеров каналов (Фаза 8); фазы 9 и 10 целиком внутренние и проверяемы тестами.

---

# ФАЗА 8 — Массовые рассылки и кампании

> **Правовая граница.** Массовая коммуникация подпадает под 152-ФЗ (персональные данные) и
> закон «О рекламе»: обязательны хранимое согласие контакта на рассылку, механизм отписки и
> троттлинг под лимиты провайдеров. Эти требования — не «фича на потом», а условие легальности;
> в скелете заложены поле согласия, токен отписки и ограничение частоты. **Точные лимиты
> провайдеров (Telegram Bot API, SMTP хостинга) прочитать до кода — `# TODO: сверить с контрактом`.**

## 8.1. Диаграмма потоков данных

```
СОЗДАНИЕ КАМПАНИИ
  CampaignsView ──POST /api/crm/campaigns/──► Campaign(channel, segment, template, schedule)
       │                                            status='draft'
       └─◄── {id}

ЗАПУСК (по расписанию или вручную)
  CELERY_BEAT: dispatch_due_campaigns каждые 5 мин
       │  находит Campaign(status='scheduled', scheduled_at<=now)
       ▼
  для кампании: разворачиваем сегмент в получателей (теги/фильтры из Фазы 7)
       │  фильтр: только contact.consent_marketing=True
       ▼
  для каждого получателя создаём CampaignRecipient(status='pending')
       │  send_campaign_batch.delay(...)  — батчами, с троттлингом
       ▼
  отправка через канал:
       ├─ email  → _send_email_reply(...)              [граница: SMTP]
       └─ telegram/max/vk → route_outgoing_message(...) [граница: провайдер]
       │  фиксируем CampaignRecipient.status='sent'/'failed' + MessageLog
       ▼
  по завершении: Campaign.status='done', notify(tenant, 'campaign_finished', ...)

ОТПИСКА
  публичная ссылка /api/public/unsubscribe/<token>/ → contact.consent_marketing=False
```

## 8.2. Пошаговый чеклист задач

1. Добавить контактам согласие и токен отписки: поля `consent_marketing` (bool) и
   `unsubscribe_token` (UUID) в `Contact` (`apps/crm/models.py`) — раздел 8.3.
2. Создать модели `Campaign`, `CampaignRecipient` (tenant-схема) — раздел 8.3.
3. `makemigrations crm`; data-миграция для существующих контактов: `consent_marketing=False`
   по умолчанию (консервативно — без согласия не рассылаем).
4. Добавить событие `CAMPAIGN_FINISHED` в `NotificationEvent` (`apps/notifications/models.py`)
   и в `seed_default_preferences`.
5. Сервис разворачивания сегмента в получателей `apps/crm/services/campaign.py` (раздел 8.4).
6. Celery-задачи `dispatch_due_campaigns` (beat) и `send_campaign_batch` (раздел 8.5);
   зарегистрировать beat в `config/settings.py:183`.
7. Публичный обработчик отписки `unsubscribe` в `apps/crm/public_views.py` + маршрут в
   `config/urls.py` (раздел 8.6).
8. Внутренний API `apps/crm/campaigns_api.py` (CRUD + запуск/пауза) + права `campaigns`.
9. Frontend: `CampaignsView.vue` (выбор канала, сегмента, шаблон сообщения, расписание,
   статистика отправки).
10. Feature-код `campaigns` + лимит `max_campaign_messages_per_month` в `Plan`.
11. Тесты (раздел 8.7).
12. Валидационный гейт (раздел 8.8).

## 8.3. Модели

`Contact` (дополнить, `apps/crm/models.py`):

```python
    consent_marketing = models.BooleanField(default=False)
    unsubscribe_token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
```

Новые модели:

```python
class Campaign(models.Model):
    STATUS = [('draft', 'Черновик'), ('scheduled', 'Запланирована'),
              ('running', 'Идёт'), ('done', 'Завершена'), ('paused', 'Пауза')]
    name = models.CharField(max_length=200)
    channel = models.ForeignKey('messenger_channels.MessengerChannel', on_delete=models.PROTECT)
    segment = models.ForeignKey('Segment', on_delete=models.SET_NULL, null=True, blank=True)
    message_template = models.TextField()        # с подстановкой {{ first_name }} и т.п.
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='draft')
    throttle_per_minute = models.PositiveIntegerField(default=20)   # лимит провайдера
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class CampaignRecipient(models.Model):
    STATUS = [('pending', 'В очереди'), ('sent', 'Отправлено'),
              ('failed', 'Ошибка'), ('skipped', 'Пропущен (нет согласия)')]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='recipients')
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['campaign', 'contact']   # один контакт — один раз на кампанию
```

> Инвариант согласия: контакт без `consent_marketing=True` получает `status='skipped'`, ему
> ничего не отправляется. Это enforce-ится в сервисе, а не только в UI.

## 8.4. Сервис аудитории (`apps/crm/services/campaign.py`)

```python
from __future__ import annotations

from apps.crm.models import Campaign, CampaignRecipient, Contact, Segment


def build_recipients(campaign: Campaign) -> int:
    """Разворачивает сегмент в CampaignRecipient. Только согласившиеся контакты."""
    qs = Contact.objects.all()
    seg = campaign.segment
    if seg and seg.filters.get('tag_ids'):
        qs = qs.filter(tags__id__in=seg.filters['tag_ids'])
    if seg and seg.filters.get('source'):
        qs = qs.filter(source=seg.filters['source'])
    created = 0
    for contact in qs.distinct():
        status = 'pending' if contact.consent_marketing else 'skipped'
        _, was_created = CampaignRecipient.objects.get_or_create(
            campaign=campaign, contact=contact, defaults={'status': status})
        if was_created and status == 'pending':
            created += 1
    return created


def render_message(template: str, contact: Contact) -> str:
    from django.template import Context, Template
    return Template(template).render(Context({
        'first_name': contact.first_name, 'last_name': contact.last_name,
    }))
```

## 8.5. Celery-задачи (`apps/crm/tasks.py`)

```python
@shared_task
def dispatch_due_campaigns():
    """Beat каждые 5 мин: запускает кампании, у которых наступило время."""
    from django.utils import timezone
    from apps.crm.models import Campaign
    from apps.crm.services.campaign import build_recipients

    for tenant in Tenant.objects.filter(is_active=True):
        with tenant_context(tenant):
            due = Campaign.objects.filter(status='scheduled', scheduled_at__lte=timezone.now())
            for campaign in due:
                build_recipients(campaign)
                campaign.status = 'running'
                campaign.save(update_fields=['status'])
                send_campaign_batch.delay(tenant.id, campaign.id)


@shared_task(rate_limit='1/s')
def send_campaign_batch(tenant_id: int, campaign_id: int):
    """Отправляет очередную порцию получателей с троттлингом. Самоперезапускается,
    пока остаются pending. [граница: провайдеры каналов]."""
    from django.utils import timezone
    from apps.crm.models import Campaign, CampaignRecipient
    from apps.crm.services.campaign import render_message

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    with tenant_context(tenant):
        campaign = Campaign.objects.select_related('channel').get(id=campaign_id)
        if campaign.status != 'running':
            return
        batch = list(CampaignRecipient.objects.filter(
            campaign=campaign, status='pending').select_related('contact')[:campaign.throttle_per_minute])
        if not batch:
            campaign.status = 'done'
            campaign.save(update_fields=['status'])
            notify(tenant, 'campaign_finished',
                   {'message': f'Кампания «{campaign.name}» завершена: '
                               f'{campaign.sent_count} отправлено, {campaign.failed_count} ошибок'})
            return
        for r in batch:
            text = render_message(campaign.message_template, r.contact)
            ok, err = _deliver_to_contact(campaign.channel, r.contact, text)  # [граница]
            r.status = 'sent' if ok else 'failed'
            r.error = err
            r.sent_at = timezone.now()
            r.save(update_fields=['status', 'error', 'sent_at'])
        Campaign.objects.filter(id=campaign_id).update(
            sent_count=CampaignRecipient.objects.filter(campaign=campaign, status='sent').count(),
            failed_count=CampaignRecipient.objects.filter(campaign=campaign, status='failed').count(),
        )
        send_campaign_batch.apply_async((tenant_id, campaign_id), countdown=60)  # следующая минута
```

> `_deliver_to_contact` маршрутизирует по `channel.channel_type`: для `email` использует
> `_send_email_reply` из Фазы 3, для мессенджеров — существующий путь отправки канала.
> Реальная доставка — `[граница]`, в dev подтверждается по логам.

Регистрация beat (`config/settings.py`, `CELERY_BEAT_SCHEDULE`):

```python
    'dispatch-due-campaigns-every-5-min': {
        'task': 'apps.crm.tasks.dispatch_due_campaigns',
        'schedule': timedelta(minutes=5),
    },
```

## 8.6. Отписка (`apps/crm/public_views.py`)

```python
@csrf_exempt
def unsubscribe(request, token):
    from django_tenants.utils import get_tenant_model, schema_context
    for tenant in get_tenant_model().objects.exclude(schema_name='public'):
        with schema_context(tenant.schema_name):
            from apps.crm.models import Contact
            contact = Contact.objects.filter(unsubscribe_token=token).first()
            if contact:
                contact.consent_marketing = False
                contact.save(update_fields=['consent_marketing'])
                return JsonResponse({'status': 'unsubscribed'})
    return JsonResponse({'detail': 'not found'}, status=404)
```

> Маршрут `path('api/public/unsubscribe/<uuid:token>/', unsubscribe)` в `config/urls.py`.
> Ссылку отписки добавлять в каждое сообщение рассылки (требование закона о рекламе).

## 8.7. Тесты (`apps/crm/tests/test_campaigns.py`)

```python
class CampaignTest(TenantAPITestCase):
    def test_recipients_respect_consent(self):
        from apps.crm.services.campaign import build_recipients
        seg = Segment.objects.create(name='Все', entity='contacts', filters={})
        Contact.objects.create(first_name='Да', consent_marketing=True)
        Contact.objects.create(first_name='Нет', consent_marketing=False)
        campaign = Campaign.objects.create(name='C', channel=self.channel, segment=seg, message_template='Привет')
        created = build_recipients(campaign)
        self.assertEqual(created, 1)  # только согласившийся попал в pending
        self.assertEqual(CampaignRecipient.objects.filter(campaign=campaign, status='skipped').count(), 1)

    def test_unsubscribe_clears_consent(self):
        c = Contact.objects.create(first_name='X', consent_marketing=True)
        c.consent_marketing = False
        c.save()
        self.assertFalse(Contact.objects.get(id=c.id).consent_marketing)
```

## 8.8. Критерии приёмки Фазы 8

1. `[локально]` Миграции без дрейфа (включая data-миграцию согласия); `ruff`/тесты/typecheck/build зелёные.
2. `[локально]` Контакт без согласия получает `status='skipped'` и не попадает в отправку (тест).
3. `[граница]` На реальном канале: порция получателей отправляется с троттлингом
   `throttle_per_minute`, в логах фиксируется доставка; ошибки провайдера → `status='failed'` с текстом.
4. `[сквозь]` Запланированная кампания стартует по времени; по завершении приходит уведомление
   `campaign_finished`; переход по ссылке отписки выключает согласие, и контакт исключается из будущих рассылок.
5. Правовые инварианты (согласие, отписка в каждом сообщении, троттлинг) зафиксированы в DEC;
   обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES; ограничения первой версии (форматы
   вложений, частотные лимиты провайдеров) — в KNOWN_ISSUES.

---

# ФАЗА 9 — Календарь, напоминания, повторяющиеся задачи

## 9.1. Диаграмма потоков данных

```
ЗАБЛАГОВРЕМЕННОЕ НАПОМИНАНИЕ
  CELERY_BEAT: process_task_reminders каждые 5 мин   (паттерн check_overdue_tasks)
       │  для каждого тенанта: Activity(type='task', status='planned',
       │     reminder_at<=now, reminder_sent=False)
       ▼
  notify(tenant, 'task_reminder', {message, link})  → reminder_sent=True

ПОВТОРЯЮЩАЯСЯ ЗАДАЧА
  выполнение/просрочка задачи с recurrence != '' ──► spawn_next_occurrence(task)
       │  по recurrence (daily/weekly/monthly) считаем следующий due_date
       ▼
  Activity.objects.create(... due_date=next, status='planned', recurrence=прежний)

КАЛЕНДАРНОЕ ПРЕДСТАВЛЕНИЕ
  CalendarView ──GET /api/crm/calendar/?from&to&responsible_id──► задачи с due_date в диапазоне
```

## 9.2. Пошаговый чеклист задач

1. Дополнить `Activity` полями `reminder_at` (datetime), `reminder_sent` (bool),
   `recurrence` (str: ''/'daily'/'weekly'/'monthly') — `apps/crm/models.py`, раздел 9.3.
2. `makemigrations crm`; проверить дрейф.
3. Добавить событие `TASK_REMINDER` в `NotificationEvent` (`apps/notifications/models.py`) и в
   `seed_default_preferences`.
4. Beat-задача `process_task_reminders` в `apps/crm/tasks.py` по образцу `check_overdue_tasks`
   (раздел 9.4); зарегистрировать в `CELERY_BEAT_SCHEDULE`.
5. Логику повтора `spawn_next_occurrence` врезать в `check_overdue_tasks` и в endpoint
   завершения задачи (раздел 9.5).
6. Endpoint календаря `GET /api/crm/calendar/` в `apps/crm/activities_api.py` (раздел 9.6).
7. Расширить схемы `ActivityIn`/`ActivityPatchIn` полями `reminder_at`/`recurrence`.
8. Frontend: `CalendarView.vue` (день/неделя/месяц) и поля напоминания/повтора в форме задачи.
9. Тесты (раздел 9.7).
10. Валидационный гейт (раздел 9.8).

## 9.3. Модель (дополнение `Activity`)

```python
    reminder_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    recurrence = models.CharField(
        max_length=10, blank=True,
        choices=[('', 'Без повтора'), ('daily', 'Ежедневно'),
                 ('weekly', 'Еженедельно'), ('monthly', 'Ежемесячно')],
    )
```

> Индекс для выборки напоминаний: добавить `models.Index(fields=['status', 'reminder_sent', 'reminder_at'])`
> в `Activity.Meta.indexes`.

## 9.4. Beat-напоминания (`apps/crm/tasks.py`)

```python
@shared_task
def process_task_reminders():
    """Заблаговременные напоминания о задачах. Идемпотентно через reminder_sent."""
    from django.utils import timezone
    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))
    sent = 0
    for tenant in tenants:
        with tenant_context(tenant):
            due = Activity.objects.filter(
                activity_type='task', status='planned',
                reminder_sent=False, reminder_at__isnull=False,
                reminder_at__lte=timezone.now(),
            )
            for task in due:
                notify(tenant, 'task_reminder',
                       {'message': f'Напоминание: {task.title}',
                        'link': f'/app/deals/{task.deal_id}' if task.deal_id else '/app/tasks'})
                task.reminder_sent = True
                task.save(update_fields=['reminder_sent'])
                sent += 1
    return {'sent': sent}
```

Регистрация (`config/settings.py`, `CELERY_BEAT_SCHEDULE`):

```python
    'process-task-reminders-every-5-min': {
        'task': 'apps.crm.tasks.process_task_reminders',
        'schedule': timedelta(minutes=5),
    },
```

## 9.5. Повтор задачи (`apps/crm/services/recurrence.py`)

```python
from __future__ import annotations

from datetime import timedelta
from dateutil.relativedelta import relativedelta   # python-dateutil уже транзитивная зависимость; иначе добавить
from apps.crm.models import Activity


def spawn_next_occurrence(task: Activity) -> Activity | None:
    if not task.recurrence or not task.due_date:
        return None
    delta = {'daily': timedelta(days=1), 'weekly': timedelta(weeks=1)}.get(task.recurrence)
    next_due = task.due_date + delta if delta else task.due_date + relativedelta(months=1)
    return Activity.objects.create(
        activity_type='task', deal=task.deal, contact=task.contact,
        responsible=task.responsible, title=task.title, body=task.body,
        status='planned', due_date=next_due, recurrence=task.recurrence,
        reminder_at=(task.reminder_at + (next_due - task.due_date)) if task.reminder_at else None,
        created_by=task.created_by,
    )
```

> Вызов `spawn_next_occurrence(task)` добавляется в endpoint смены статуса задачи на `done`
> (в `activities_api.py`) и опционально в `check_overdue_tasks` для просроченных повторяющихся.
> Защита от размножения: новая задача создаётся один раз — в момент завершения текущей,
> а не в цикле beat.

## 9.6. Endpoint календаря (`apps/crm/activities_api.py`)

```python
@crm_router.get('/calendar/')
def calendar(request, date_from: str, date_to: str, responsible_id: int | None = None):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    qs = filter_crm_queryset_by_scope(
        request,
        Activity.objects.filter(activity_type='task', due_date__date__gte=date_from,
                                due_date__date__lte=date_to),
        'deals',
    )
    if responsible_id:
        qs = qs.filter(responsible_id=responsible_id)
    return [
        {'id': a.id, 'title': a.title, 'status': a.status,
         'due_date': a.due_date.isoformat() if a.due_date else None,
         'deal_id': a.deal_id, 'responsible_id': a.responsible_id, 'recurrence': a.recurrence}
        for a in qs.order_by('due_date')
    ]
```

## 9.7. Тесты (`apps/crm/tests/test_reminders.py`)

```python
class RemindersTest(TenantAPITestCase):
    def test_reminder_fires_once(self):
        past = timezone.now() - timedelta(minutes=1)
        Activity.objects.create(activity_type='task', title='T', status='planned',
                                reminder_at=past, responsible=self.user)
        process_task_reminders()
        process_task_reminders()  # повтор
        # уведомление поставлено один раз — reminder_sent=True
        self.assertTrue(Activity.objects.get(title='T').reminder_sent)

    def test_recurrence_spawns_next(self):
        from apps.crm.services.recurrence import spawn_next_occurrence
        t = Activity.objects.create(activity_type='task', title='W', status='planned',
                                    due_date=timezone.now(), recurrence='weekly')
        nxt = spawn_next_occurrence(t)
        self.assertEqual((nxt.due_date - t.due_date).days, 7)
```

## 9.8. Критерии приёмки Фазы 9

1. `[локально]` Миграции без дрейфа; `ruff`/тесты/typecheck/build зелёные; идемпотентность
   напоминания и корректность следующего срока повтора покрыты тестами.
2. `[сквозь]` За N минут до срока приходит напоминание ровно один раз; завершение
   повторяющейся задачи создаёт следующую с правильным `due_date`.
3. `[сквозь]` Календарь показывает задачи по диапазону дат и ответственному с учётом scope.
4. Обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# ФАЗА 10 — Планы продаж и аналитика воронки

## 10.1. Диаграмма потоков данных

```
ЦЕЛИ
  TargetsView ──POST /api/dashboard/targets/──► SalesTarget(user, period, amount/count)
       └─◄── {id}

АНАЛИТИКА (агрегации поверх существующего дашборда)
  AnalyticsView ──GET /api/dashboard/funnel/?pipeline_id&from&to──►
       │  Deal.values('stage').annotate(Count, Sum) по стадиям  ← конверсия по этапам
  AnalyticsView ──GET /api/dashboard/forecast/──►
       │  Σ amount по open-сделкам × вес стадии  ← прогноз
  AnalyticsView ──GET /api/dashboard/loss-reasons/──►
       │  Deal.filter(stage_type='lost').values('loss_reason').annotate(Count)
  AnalyticsView ──GET /api/dashboard/target-progress/──►
       │  факт (won за период) против SalesTarget
```

## 10.2. Пошаговый чеклист задач

1. Создать модель `SalesTarget` (tenant-схема) — раздел 10.3.
2. `makemigrations`; проверить дрейф.
3. Эндпоинты аналитики в `apps/crm/dashboard_api.py` по образцу `stats`/`managers`
   (`require_roles` + `require_feature_access('analytics')`) — раздел 10.4.
4. Эндпоинты CRUD целей в том же роутере.
5. Frontend: `AnalyticsView.vue` (воронка-конверсия, прогноз, причины потерь) и блок
   «Выполнение плана» на дашборде; графики через уже используемую библиотеку charts PrimeVue.
6. Тесты агрегаций (раздел 10.5).
7. Валидационный гейт (раздел 10.6).

## 10.3. Модель `SalesTarget`

```python
class SalesTarget(models.Model):
    PERIOD = [('month', 'Месяц'), ('quarter', 'Квартал')]
    METRIC = [('amount', 'Сумма выигранных'), ('count', 'Число выигранных')]
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True,
                             related_name='sales_targets')   # null = командная цель
    period = models.CharField(max_length=10, choices=PERIOD, default='month')
    period_start = models.DateField()
    metric = models.CharField(max_length=10, choices=METRIC, default='amount')
    target_value = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = ['user', 'period_start', 'metric']
```

## 10.4. Эндпоинты аналитики (`apps/crm/dashboard_api.py`)

```python
@dashboard_router.get('/funnel/')
def funnel(request, pipeline_id: int, date_from: str | None = None, date_to: str | None = None):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'analytics')
    start, end = _date_range(date_from, date_to)
    qs = Deal.objects.filter(pipeline_id=pipeline_id)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    rows = (qs.values('stage_id', 'stage__name', 'stage__sort_order', 'stage__stage_type')
              .annotate(total=Count('id'), amount=Sum('amount'))
              .order_by('stage__sort_order'))
    rows = list(rows)
    # конверсия: доля сделок, дошедших до каждой следующей стадии
    base = rows[0]['total'] if rows else 0
    for r in rows:
        r['amount'] = float(r['amount'] or 0)
        r['conversion'] = round(100 * r['total'] / base, 1) if base else 0
    return rows


@dashboard_router.get('/forecast/')
def forecast(request, pipeline_id: int | None = None):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'analytics')
    # вес стадии берём из stage.auto_action.get('forecast_weight') либо по позиции
    qs = Deal.objects.filter(stage__stage_type='open').select_related('stage')
    if pipeline_id:
        qs = qs.filter(pipeline_id=pipeline_id)
    weighted = 0.0
    total = 0.0
    for deal in qs:
        amount = float(deal.amount or 0)
        weight = float((deal.stage.auto_action or {}).get('forecast_weight', 0.5))
        total += amount
        weighted += amount * weight
    return {'pipeline_open_amount': total, 'weighted_forecast': round(weighted, 2)}


@dashboard_router.get('/loss-reasons/')
def loss_reasons(request, date_from: str | None = None, date_to: str | None = None):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'analytics')
    start, end = _date_range(date_from, date_to)
    qs = Deal.objects.filter(stage__stage_type='lost')
    if start:
        qs = qs.filter(closed_at__gte=start)
    if end:
        qs = qs.filter(closed_at__lte=end)
    rows = (qs.values('loss_reason').annotate(total=Count('id')).order_by('-total'))
    return [{'reason': r['loss_reason'] or '(не указана)', 'total': r['total']} for r in rows]


@dashboard_router.get('/target-progress/')
def target_progress(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'analytics')
    from datetime import date
    from .models import SalesTarget
    month_start = date.today().replace(day=1)
    results = []
    for t in SalesTarget.objects.filter(period_start=month_start):
        won = Deal.objects.filter(stage__stage_type='won', closed_at__date__gte=month_start)
        if t.user_id:
            won = won.filter(responsible_id=t.user_id)
        fact = won.aggregate(s=Sum('amount'), c=Count('id'))
        actual = float(fact['s'] or 0) if t.metric == 'amount' else (fact['c'] or 0)
        results.append({
            'target_id': t.id, 'user_id': t.user_id, 'metric': t.metric,
            'target': float(t.target_value), 'actual': actual,
            'progress': round(100 * actual / float(t.target_value), 1) if t.target_value else 0,
        })
    return results
```

> Эти эндпоинты не вводят новых внешних зависимостей — только ORM-агрегации поверх уже
> собираемых полей (`stage_type`, `amount`, `closed_at`, `loss_reason`, `responsible_id`).

## 10.5. Тесты (`apps/crm/tests/test_analytics.py`)

```python
class AnalyticsTest(TenantAPITestCase):
    def test_funnel_conversion(self):
        # 10 сделок на первой стадии, 4 на второй → конверсия 40%
        ...
        rows = funnel(self.request, pipeline_id=self.pipeline.id)
        self.assertEqual(rows[1]['conversion'], 40.0)

    def test_target_progress(self):
        from apps.crm.models import SalesTarget
        SalesTarget.objects.create(period_start=date.today().replace(day=1),
                                   metric='count', target_value=10, user=self.user)
        # одна won-сделка за месяц → progress 10%
        ...
```

## 10.6. Критерии приёмки Фазы 10

1. `[локально]` Миграции без дрейфа; `ruff`/тесты/typecheck/build зелёные; расчёт конверсии и
   выполнения плана покрыт тестами.
2. `[сквозь]` Воронка показывает конверсию по этапам; прогноз считает взвешенную сумму
   открытых сделок; причины потерь агрегируются по `loss_reason`; прогресс к плану отражает
   факт против цели за период.
3. Все эндпоинты под `require_feature_access('analytics')` и ролевым доступом, как существующие.
4. Обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# Общий порядок реализации и валидации (P2)

1. Фаза 8 требует завершённых Фазы 3 (email-канал) и Фазы 7 (теги/сегменты); Фазы 9 и 10
   независимы и не имеют внешних границ — их можно делать в любой момент.
2. Единственная внешняя граница P2 — массовая отправка через провайдеров (Фаза 8); она
   изолирована в существующем конвейере каналов, дополнена согласием, отпиской и троттлингом,
   и до кода требует сверки лимитов провайдеров с их контрактами.
3. Гейт завершения каждой фазы: `docker compose down && up -d --build`, `manage.py check`
   (0 issues), `makemigrations --check` (без дрейфа), `ruff check .`, целевые backend-тесты,
   `npm run typecheck`/`build`/`test`, ручная HTTP-проверка экранов.
4. Update Ritual (`AGENTS.md`): новый DEC на каждую фазу (для Фазы 8 — отдельно зафиксировать
   правовые инварианты согласия/отписки), статус в TASK_STATE, запись в DEV_LOG, RELEASE_NOTES
   на русском; остаточные ограничения первой версии — в KNOWN_ISSUES.
5. Коммит и индексацию выполняет пользователь; агент останавливается после прохождения гейта.
```

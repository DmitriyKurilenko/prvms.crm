from __future__ import annotations

from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.mail import send_mail
from django_tenants.utils import schema_context, tenant_context
import requests

from apps.users.models import Membership, User
from .models import Notification, NotificationEvent, NotificationPreference, TelegramBinding

_DEFAULT_ROLES = ['owner', 'admin']
_DEFAULT_IN_APP_EVENTS = [e.value for e in NotificationEvent]


def seed_default_preferences():
    """Create default notification preferences if none exist in the current schema."""
    if NotificationPreference.objects.exists():
        return
    prefs = []
    for event in _DEFAULT_IN_APP_EVENTS:
        prefs.append(NotificationPreference(
            event=event, channel='in_app', is_enabled=True,
            recipient_roles=_DEFAULT_ROLES,
        ))
        prefs.append(NotificationPreference(
            event=event, channel='email', is_enabled=False,
            recipient_roles=_DEFAULT_ROLES,
        ))
    NotificationPreference.objects.bulk_create(prefs, ignore_conflicts=True)


def notify(tenant, event: str, context: dict, instance=None):
    """Dispatches notifications according to tenant preferences."""
    _ = instance
    seed_default_preferences()
    prefs = NotificationPreference.objects.filter(event=event, is_enabled=True)
    for pref in prefs:
        roles = pref.recipient_roles or ['owner', 'admin']
        users = get_users_by_roles(tenant, roles)
        for user in users:
            if pref.channel == 'email':
                from .tasks import send_notification_email_task
                send_notification_email_task.delay(tenant.id, user.id, event, context)
            elif pref.channel == 'in_app':
                notification = Notification.objects.create(
                    user=user,
                    event=event,
                    title=render_title(event, context),
                    body=render_body(event, context),
                    link=context.get('link', ''),
                    channel='in_app',
                )
                _push_realtime_notification(notification)
            elif pref.channel == 'telegram':
                send_telegram_notification(tenant, user, event, context)


def get_users_by_roles(tenant, roles: list[str]):
    with schema_context('public'):
        user_ids = Membership.objects.filter(
            tenant_id=tenant.id,
            role__in=roles,
            is_active=True,
        ).values_list('user_id', flat=True)
        return list(User.objects.filter(id__in=user_ids, is_active=True))


def render_title(event: str, context: dict) -> str:
    titles = {
        'contract_signed': 'Договор подписан',
        'lead_distributed': 'Заявка распределена',
        'crm_connection_lost': 'Потеряно соединение с CRM',
        'crm_connection_restored': 'Соединение с CRM восстановлено',
        'plan_limit_warning': 'Лимиты плана близки к исчерпанию',
        'plan_limit_reached': 'Лимит плана достигнут',
        'user_invited': 'Пользователь приглашён',
        'manager_sync_done': 'Синхронизация менеджеров завершена',
        'signing_expired': 'Срок подписания истёк',
        'deal_stage_changed': 'Сделка перемещена',
        'task_overdue': 'Есть просроченная задача',
        'new_deal_created': 'Создана новая сделка',
    }
    return titles.get(event, event)


def render_body(event: str, context: dict) -> str:
    if context.get('message'):
        return str(context['message'])
    if event == 'lead_distributed':
        return f"Сущность {context.get('entity_type', 'lead')} #{context.get('entity_id', '')} назначена."
    if event == 'contract_signed':
        return f"Договор #{context.get('contract_id', '')} подписан."
    return 'Событие в CRM Platform'


def send_notification_email(tenant, user, event: str, context: dict):
    with tenant_context(tenant):
        send_mail(
            subject=render_title(event, context),
            message=render_body(event, context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )


def send_telegram_notification(tenant, user, event: str, context: dict):
    token = settings.TELEGRAM_NOTIFICATION_BOT_TOKEN
    if not token:
        return
    with tenant_context(tenant):
        binding = TelegramBinding.objects.filter(user=user, is_active=True).first()
        if not binding:
            return
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': binding.chat_id, 'text': f"{render_title(event, context)}\n{render_body(event, context)}"},
            timeout=10,
        )


def _push_realtime_notification(notification: Notification):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    payload = {
        'id': notification.id,
        'event': notification.event,
        'title': notification.title,
        'body': notification.body,
        'link': notification.link,
        'is_read': notification.is_read,
        'channel': notification.channel,
        'sent_at': notification.sent_at.isoformat(),
    }
    async_to_sync(channel_layer.group_send)(
        f'notifications.user.{notification.user_id}',
        {'type': 'notification.message', 'payload': payload},
    )

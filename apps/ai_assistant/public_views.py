"""
Public webhook endpoint for Hermes cron job notifications.
Hermes calls this endpoint when cron jobs trigger (e.g., daily digest, overdue task reminders).
"""
import hashlib
import hmac
import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_tenants.utils import schema_context

from apps.tenants.models import Tenant
from apps.users.models import User

logger = logging.getLogger(__name__)


def _validate_hermes_webhook(request) -> bool:
    """Validate the Hermes webhook request using HMAC."""
    expected_key = getattr(settings, 'HERMES_WEBHOOK_SECRET', '')
    if not expected_key:
        return True

    signature = request.headers.get('X-Hermes-Signature', '')
    if not signature:
        return False

    expected = hmac.new(
        expected_key.encode(),
        request.body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f'sha256={expected}', signature)


@csrf_exempt
@require_POST
def hermes_webhook(request):
    """
    Public webhook endpoint for Hermes cron notifications.
    Called by Hermes when cron jobs complete.
    """
    secret = getattr(settings, 'HERMES_WEBHOOK_SECRET', '')
    if secret and not _validate_hermes_webhook(request):
        logger.warning('Hermes webhook: invalid signature')
        return JsonResponse({'error': 'Invalid signature'}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning('Hermes webhook: invalid JSON')
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    tenant_slug = payload.get('tenant_slug')
    user_id = payload.get('user_id')
    notification_type = payload.get('type', 'hermes_cron')
    title = payload.get('title', 'Уведомление от AI')
    body = payload.get('body', '')
    link = payload.get('link', '')

    if not tenant_slug:
        return JsonResponse({'error': 'tenant_slug required'}, status=400)

    try:
        with schema_context('public'):
            tenant = Tenant.objects.filter(slug=tenant_slug).first()
            if not tenant:
                return JsonResponse({'error': f'Tenant not found: {tenant_slug}'}, status=404)

        user = None
        if user_id:
            with schema_context('public'):
                user = User.objects.filter(id=user_id).first()

        if not user:
            with schema_context(tenant.schema_name):
                from apps.users.models import Membership
                membership = Membership.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    joined_at__isnull=False,
                    invite_token__isnull=True,
                    role__in=['owner', 'admin']
                ).first()
                if membership:
                    user = membership.user

        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)

        _send_notification(tenant, user, notification_type, title, body, link)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.exception('Hermes webhook error')
        return JsonResponse({'error': str(e)}, status=500)


def _send_notification(tenant, user, notification_type: str, title: str, body: str, link: str):
    """Send notification via Django's notification system."""
    from apps.notifications.models import Notification

    with schema_context(tenant.schema_name):
        notification = Notification.objects.create(
            user=user,
            event=notification_type,
            title=title,
            body=body,
            link=link,
            channel='in_app',
        )

    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(
            f'notifications.user.{user.id}',
            {
                'type': 'notification_message',
                'payload': {
                    'id': notification.id,
                    'event': notification.event,
                    'title': notification.title,
                    'body': notification.body,
                    'link': notification.link,
                    'is_read': notification.is_read,
                    'channel': notification.channel,
                    'sent_at': notification.sent_at.isoformat() if notification.sent_at else None,
                }
            }
        )
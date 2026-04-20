import json
import logging
from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_tenants.utils import schema_context
from yookassa.domain.notification import WebhookNotificationEventType, WebhookNotificationFactory

from .models import Payment

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def yookassa_webhook(request):
    """Обработка уведомлений от ЮKassa о статусе платежа.

    ЮKassa отправляет POST с JSON, содержащим объект notification.
    Обрабатываем только payment.succeeded и payment.canceled.
    """
    try:
        event_json = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.warning('YooKassa webhook: invalid JSON body')
        return HttpResponseBadRequest('Invalid JSON')

    try:
        notification = WebhookNotificationFactory().create(event_json)
    except Exception:
        logger.warning('YooKassa webhook: failed to parse notification', exc_info=True)
        return HttpResponseBadRequest('Invalid notification')

    yoo_payment = notification.object

    # Verify the payment belongs to our shop
    if settings.YOOKASSA_SHOP_ID and yoo_payment.recipient:
        if yoo_payment.recipient.account_id != settings.YOOKASSA_SHOP_ID:
            logger.warning(
                'YooKassa webhook: account_id mismatch: %s != %s',
                yoo_payment.recipient.account_id, settings.YOOKASSA_SHOP_ID,
            )
            return HttpResponseBadRequest('Account mismatch')

    yookassa_id = yoo_payment.id

    with schema_context('public'):
        try:
            payment = Payment.objects.select_related('tenant', 'plan').get(
                yookassa_payment_id=yookassa_id,
            )
        except Payment.DoesNotExist:
            logger.warning('YooKassa webhook: payment not found for yookassa_id=%s', yookassa_id)
            return HttpResponse('OK')

        if notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            if payment.status == 'paid':
                return HttpResponse('OK')

            now = timezone.now()
            payment.status = 'paid'
            payment.paid_at = now
            payment.expires_at = now + timedelta(days=30 * payment.months)
            payment.save(update_fields=['status', 'paid_at', 'expires_at'])

            tenant = payment.tenant
            tenant.plan = payment.plan
            tenant.is_paid = True
            tenant.trial_expires_at = None
            tenant.save(update_fields=['plan', 'is_paid', 'trial_expires_at'])

            logger.info(
                'YooKassa: payment %s succeeded, tenant %s activated on plan %s',
                payment.id, tenant.slug, payment.plan.slug,
            )

        elif notification.event == WebhookNotificationEventType.PAYMENT_CANCELED:
            if payment.status not in ('pending',):
                return HttpResponse('OK')

            payment.status = 'cancelled'
            cancellation = yoo_payment.cancellation_details
            if cancellation:
                payment.comment = f'{cancellation.party}: {cancellation.reason}'
            payment.save(update_fields=['status', 'comment'])

            logger.info('YooKassa: payment %s cancelled', payment.id)

    return HttpResponse('OK')

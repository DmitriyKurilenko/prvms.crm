from __future__ import annotations

import logging
import smtplib

from celery import shared_task
from django.core.mail import send_mail
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant
from apps.users.models import User

from .services import send_notification_email, send_telegram_notification

logger = logging.getLogger(__name__)


@shared_task
def send_notification_email_task(tenant_id: int, user_id: int, event: str, context: dict):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)
    with tenant_context(tenant):
        send_notification_email(tenant, user, event, context)


@shared_task
def send_telegram_notification_task(tenant_id: int, user_id: int, event: str, context: dict):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)
    with tenant_context(tenant):
        send_telegram_notification(tenant, user, event, context)


@shared_task(
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
)
def send_email_async(subject: str, message: str, from_email: str | None, recipient_list: list[str]):
    try:
        sent = send_mail(subject, message, from_email, recipient_list)
    except (smtplib.SMTPException, OSError):
        logger.exception('send_email_async failed: subject=%r to=%s', subject, recipient_list)
        raise
    logger.info('send_email_async delivered=%s subject=%r to=%s', sent, subject, recipient_list)

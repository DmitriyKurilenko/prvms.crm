import json
import logging
from typing import Optional

import requests
from django.conf import settings
from django_tenants.utils import schema_context

from apps.crm.models import Activity, Contact, Deal
from apps.users.models import User

logger = logging.getLogger(__name__)


def get_hermes_profile_for_tenant(tenant_slug: str) -> str:
    """Returns Hermes profile name for tenant."""
    return tenant_slug


def build_context_for_hermes(tenant, context_data: dict) -> dict:
    """Build system context with CRM data for Hermes prompt."""
    context_parts = []

    if 'deal_id' in context_data:
        with schema_context(tenant.schema_name):
            try:
                deal = Deal.objects.get(id=context_data['deal_id'])
                stage_name = deal.stage.name if deal.stage else 'Unknown'
                pipeline_name = deal.pipeline.name if deal.pipeline else 'Unknown'
                context_parts.append(
                    f"Текущая сделка: {deal.name}\n"
                    f"Стадия: {pipeline_name} / {stage_name}\n"
                    f"Сумма: {deal.amount} {deal.currency}\n"
                    f"Ответственный: {deal.responsible.get_full_name() if deal.responsible else 'Не назначен'}"
                )
            except Deal.DoesNotExist:
                pass

    if 'crm_lead_id' in context_data:
        with schema_context(tenant.schema_name):
            deal = Deal.objects.filter(id=context_data['crm_lead_id']).select_related('stage').first()
            if deal:
                context_parts.append(
                    f"Лид (из мессенджера): {deal.name}\n"
                    f"Стадия: {deal.stage.name if deal.stage else 'Unknown'}\n"
                    f"Сумма: {deal.amount} {deal.currency}"
                )

    if 'crm_contact_id' in context_data:
        with schema_context(tenant.schema_name):
            try:
                contact = Contact.objects.select_related('company').get(id=context_data['crm_contact_id'])
                context_parts.append(
                    f"Клиент: {contact.get_full_name()}\n"
                    f"Компания: {contact.company.name if contact.company else 'Не указана'}\n"
                    f"Телефон: {contact.phone or 'Не указан'}\n"
                    f"Email: {contact.email or 'Не указан'}"
                )
            except Contact.DoesNotExist:
                pass

    return '\n\n'.join(context_parts) if context_parts else ''


def send_to_hermes(tenant, user: User, message: str, conversation_id: str, context: Optional[dict] = None) -> str:
    """
    Send message to Hermes and return response.
    Uses Hermes OpenAI-compatible API.
    """
    hermes_url = getattr(settings, 'HERMES_API_URL', 'http://hermes:8642')
    hermes_api_key = getattr(settings, 'HERMES_API_KEY', '')

    profile = get_hermes_profile_for_tenant(tenant.slug)

    system_context = ""
    if context:
        system_context = build_context_for_hermes(tenant, context)

    system_prompt = (
        "Ты AI-ассистент в CRM системе. Помогай менеджеру работать с клиентами и сделками.\n"
        "Будь кратким и полезным.\n"
    )
    if system_context:
        system_prompt += f"\n\nКонтекст CRM:\n{system_context}"

    payload = {
        'model': profile,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': message},
        ],
        'stream': False,
    }

    headers = {
        'Authorization': f'Bearer {hermes_api_key}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            f'{hermes_url}/v1/chat/completions',
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        if 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0]['message']['content']
        return 'Извините, не удалось получить ответ от AI.'

    except requests.exceptions.Timeout:
        return 'Извините, истекло время ожидания ответа. Попробуйте ещё раз.'
    except requests.exceptions.RequestException as e:
        return f'Ошибка связи с AI: {str(e)}'


def send_notification_via_hermes(tenant, user: User, title: str, body: str) -> bool:
    """
    Send notification through Hermes (for proactive alerts from cron jobs).
    """
    hermes_url = getattr(settings, 'HERMES_API_URL', 'http://hermes:8642')
    hermes_api_key = getattr(settings, 'HERMES_API_KEY', '')

    profile = get_hermes_profile_for_tenant(tenant.slug)

    payload = {
        'model': profile,
        'messages': [
            {'role': 'system', 'content': 'Ты отправляешь уведомления менеджеру.'},
            {'role': 'user', 'content': f'Отправь уведомление пользователю {user.get_full_name()}: {title}\n{body}'},
        ],
        'stream': False,
    }

    headers = {
        'Authorization': f'Bearer {hermes_api_key}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            f'{hermes_url}/v1/chat/completions',
            json=payload,
            headers=headers,
            timeout=30,
        )
        return response.status_code == 200
    except requests.RequestException:
        logger.warning('Hermes notification delivery failed', exc_info=True)
        return False
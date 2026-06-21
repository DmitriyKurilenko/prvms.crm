"""Приём заявки веб-формы: контакт + сделка + распределение + уведомление.

Вызывается из публичного обработчика внутри `schema_context` тенанта.
Переиспользует существующий CRM-конвейер (Contact/Deal/try_distribute/notify).
"""
from __future__ import annotations

import logging

from apps.crm.models import Contact, Deal, WebForm
from apps.distribution.services import ensure_builtin_manager_profiles, try_distribute
from apps.notifications.services import notify

logger = logging.getLogger('crm.webform')

# Поля формы, которые ложатся в стандартные колонки контакта; остальное — в custom_fields.
_STANDARD = {'name', 'first_name', 'last_name', 'phone', 'email'}


def intake_webform_submission(tenant, token, fields: dict) -> dict | None:
    """Создаёт контакт и сделку из данных формы. Возвращает None, если форма неактивна."""
    form = WebForm.objects.filter(public_token=token, is_active=True).first()
    if not form:
        return None

    name = str(fields.get('name') or fields.get('first_name') or '').strip() or 'Лид с формы'
    contact = Contact.objects.create(
        first_name=name[:100],
        last_name=str(fields.get('last_name') or '')[:100],
        phone=str(fields.get('phone') or '')[:50],
        email=str(fields.get('email') or '')[:254],
        source=form.source,
        custom_fields={k: v for k, v in fields.items() if k not in _STANDARD},
    )
    deal = Deal.objects.create(
        name=f'Заявка с формы «{form.name}»',
        pipeline=form.pipeline,
        stage=form.stage,
        contact=contact,
        source=form.source,
    )
    WebForm.objects.filter(id=form.id).update(submissions_count=form.submissions_count + 1)

    if form.auto_distribute and not deal.responsible_id:
        ensure_builtin_manager_profiles()
        try_distribute('new_lead', 'deal', str(deal.id))

    notify(tenant, 'new_deal_created', {'deal_id': deal.id, 'link': f'/app/deals/{deal.id}'})
    logger.info('webform intake token=%s deal=%s contact=%s', token, deal.id, contact.id)
    return {'deal_id': deal.id, 'contact_id': contact.id, 'success_message': form.success_message}

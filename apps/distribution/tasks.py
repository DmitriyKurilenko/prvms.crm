from __future__ import annotations

from celery import shared_task
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant
from .services import assign_entity, choose_rule


@shared_task
def process_incoming_webhook(tenant_id: int, trigger: str, payload: dict):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    with tenant_context(tenant):
        rule = choose_rule(trigger, payload)
        if not rule:
            return {'status': 'no_rule'}
        log = assign_entity(
            rule=rule,
            entity_type=str(payload.get('entity_type', 'lead')),
            entity_id=str(payload.get('entity_id', '')),
            source=str(payload.get('source', 'crm_webhook')),
            payload=payload,
        )
        return {'status': 'ok', 'log_id': log.id, 'assigned_to': log.assigned_to_id}

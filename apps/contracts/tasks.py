from __future__ import annotations

from celery import shared_task
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant
from apps.integrations.adapters import get_adapter_for_tenant
from .models import Contract, SigningSession
from .services import send_for_signing


@shared_task
def send_otp(tenant_id: int, contract_id: int, recipient: str):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    with tenant_context(tenant):
        contract = Contract.objects.get(id=contract_id)
        send_for_signing(contract, recipient)


@shared_task
def expire_signing_sessions():
    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))
    for tenant in tenants:
        with tenant_context(tenant):
            expired = SigningSession.objects.filter(
                verified_at__isnull=True,
                otp_expires_at__lt=timezone.now(),
            ).select_related('contract')
            for session in expired:
                if session.contract.status in {'sent', 'viewed'}:
                    session.contract.status = 'expired'
                    session.contract.save(update_fields=['status'])


@shared_task
def notify_contract_signed(tenant_id: int, contract_id: int):
    from apps.notifications.services import notify

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    with tenant_context(tenant):
        contract = Contract.objects.select_related('deal').get(id=contract_id)
        notify(
            tenant,
            'contract_signed',
            {
                'contract_id': contract.id,
                'link': f'/contracts/{contract.id}',
                'message': f'Договор #{contract.id} успешно подписан.',
            },
        )
        try:
            if contract.crm_entity_id:
                adapter = get_adapter_for_tenant(tenant)
                adapter.update_lead(contract.crm_entity_id, {'contract_status': 'signed'})
        except Exception as exc:  # noqa: BLE001
            return {'status': 'warning', 'detail': str(exc)[:500]}
    return {'status': 'ok'}

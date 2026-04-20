from __future__ import annotations

from uuid import uuid4

from django.utils import timezone
from celery import shared_task
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant
from .models import CRMConnection, ManagerProfile
from .services import add_error_log, call_adapter_with_reconnect, clear_connection_error, is_connection_authorized


def _sanitize_username(seed: str) -> str:
    normalized = ''.join(ch for ch in str(seed).strip().lower() if ch.isalnum() or ch in {'_', '-', '.'})
    return (normalized or 'manager')[:150]


def _next_username(seed: str):
    from apps.users.models import User

    base = _sanitize_username(seed)
    candidate = base
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        token = f'_{suffix}'
        candidate = f'{base[: max(1, 150 - len(token))]}{token}'
        suffix += 1
    return candidate


def _resolve_user_for_crm_user(tenant, crm_type: str, crm_user):
    from apps.users.models import Membership, User

    email = (crm_user.email or '').strip().lower()
    with schema_context('public'):
        user = User.objects.filter(email__iexact=email).first() if email else None
        if not user:
            suffix = uuid4().hex[:8]
            synthetic_email = email or f'{crm_type}_{crm_user.id}_{tenant.slug}_{suffix}@crm.local'
            user = User.objects.filter(email__iexact=synthetic_email).first()
            if not user:
                user = User.objects.create_user(
                    email=synthetic_email,
                    username=_next_username(crm_user.name or synthetic_email.split('@')[0]),
                    password=None,
                )

        membership = Membership.objects.filter(user_id=user.id, tenant_id=tenant.id).first()
        joined_at = membership.joined_at if membership and membership.joined_at else timezone.now()
        if membership:
            membership.role = 'manager'
            membership.is_active = True
            membership.invite_token = None
            membership.joined_at = joined_at
            membership.save(update_fields=['role', 'is_active', 'invite_token', 'joined_at'])
        else:
            Membership.objects.create(
                user_id=user.id,
                tenant_id=tenant.id,
                role='manager',
                is_active=True,
                joined_at=joined_at,
            )
    return user


@shared_task
def sync_crm_users(tenant_id: int, connection_id: int):
    from apps.notifications.services import notify

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    with tenant_context(tenant):
        connection = CRMConnection.objects.get(id=connection_id)
        if not is_connection_authorized(connection):
            add_error_log(
                connection,
                code='manager_sync_failed',
                message='Синхронизация менеджеров невозможна: интеграция не авторизована.',
                resolution='Переавторизуйте подключение и повторите синхронизацию.',
            )
            return {'synced': 0, 'error': 'not_authorized'}

        try:
            users = call_adapter_with_reconnect(connection, 'list_users') or []
        except Exception as exc:  # noqa: BLE001
            connection.last_error = str(exc)[:1000]
            connection.save(update_fields=['last_error'])
            add_error_log(
                connection,
                code='manager_sync_failed',
                message=f'Синхронизация менеджеров завершилась ошибкой: {exc}',
                resolution='Проверьте credentials CRM и права на чтение пользователей, затем повторите синхронизацию.',
                details={'exception': str(exc)},
            )
            notify(
                tenant,
                'manager_sync_failed',
                {'message': f'Синхронизация менеджеров не выполнена: {exc}', 'link': '/integrations'},
            )
            return {'synced': 0, 'error': str(exc)}

        synced = 0
        active_ids: set[str] = set()
        for crm_user in users:
            user = _resolve_user_for_crm_user(tenant, connection.crm_type, crm_user)
            crm_user_id = str(crm_user.id)
            active_ids.add(crm_user_id)
            ManagerProfile.objects.update_or_create(
                crm_connection=connection,
                crm_user_id=crm_user_id,
                defaults={
                    'user': user,
                    'crm_user_name': crm_user.name,
                    'is_active': bool(crm_user.is_active),
                },
            )
            synced += 1

        ManagerProfile.objects.filter(crm_connection=connection).exclude(crm_user_id__in=active_ids).update(is_active=False)

        connection.last_sync_at = timezone.now()
        clear_connection_error(connection)
        connection.refresh_from_db(fields=['last_error'])
        connection.save(update_fields=['last_sync_at'])
        notify(
            tenant,
            'manager_sync_done',
            {'message': f'Синхронизация менеджеров завершена: {synced}', 'link': '/integrations'},
        )
        return {'synced': synced}


@shared_task
def check_crm_connections_health():
    from apps.notifications.services import notify

    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))
    results = []
    for tenant in tenants:
        with tenant_context(tenant):
            for connection in CRMConnection.objects.filter(is_active=True):
                previous_error = connection.last_error
                connection.last_health_check_at = timezone.now()
                try:
                    if is_connection_authorized(connection):
                        call_adapter_with_reconnect(connection, 'list_users')
                    clear_connection_error(connection)
                    connection.refresh_from_db(fields=['last_error'])
                except Exception as exc:  # noqa: BLE001
                    connection.last_error = str(exc)[:1000]
                    add_error_log(
                        connection,
                        code='connection_health_failed',
                        message=f'Проверка подключения не пройдена: {exc}',
                        resolution='Проверьте доступ к CRM API и нажмите «Проверить» повторно.',
                        details={'exception': str(exc)},
                    )
                connection.save(update_fields=['last_error', 'last_health_check_at'])
                if previous_error and not connection.last_error:
                    notify(
                        tenant,
                        'crm_connection_restored',
                        {'message': f'Соединение с CRM "{connection.name}" восстановлено.', 'link': '/integrations'},
                    )
                if not previous_error and connection.last_error:
                    notify(
                        tenant,
                        'crm_connection_lost',
                        {'message': f'Потеряно соединение с CRM "{connection.name}".', 'link': '/integrations'},
                    )
                results.append({'tenant': tenant.id, 'connection': connection.id, 'error': connection.last_error})
    return results

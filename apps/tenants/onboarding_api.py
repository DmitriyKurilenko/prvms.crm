from __future__ import annotations

import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from ninja import Body, Router
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_roles
from apps.core.tenant import get_request_tenant
from apps.integrations.models import ManagerProfile
from apps.users.models import Membership, User
from apps.distribution.models import DistributionRule

onboarding_router = Router(tags=['onboarding'], auth=JWTAuth())


@onboarding_router.get('/status/')
def onboarding_status(request):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    return {'onboarding_step': tenant.onboarding_step}


@onboarding_router.post('/step/{step}/')
def onboarding_step(request, step: int, payload: dict = Body(...)):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    step = max(0, min(step, 5))

    if step == 1:
        _apply_org_step(tenant, payload)
    elif step == 2:
        _apply_crm_mode_step(tenant, payload)
    elif step == 3:
        _apply_managers_step(tenant, payload)
    elif step == 4:
        _apply_distribution_step(payload)

    if step > tenant.onboarding_step:
        tenant.onboarding_step = step
        tenant.save(update_fields=['onboarding_step'])
    return {'detail': 'ok', 'onboarding_step': tenant.onboarding_step, 'saved': payload}


@onboarding_router.post('/skip/')
def onboarding_skip(request):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    tenant.onboarding_step = 5
    tenant.save(update_fields=['onboarding_step'])
    return {'detail': 'ok', 'onboarding_step': 5}


def _apply_org_step(tenant, payload: dict):
    changed = []
    for field in ('name', 'timezone', 'language', 'brand_color'):
        value = payload.get(field)
        if value:
            setattr(tenant, field, value)
            changed.append(field)
    if changed:
        tenant.save(update_fields=changed)


def _apply_crm_mode_step(tenant, payload: dict):
    crm_mode = payload.get('crm_mode')
    if crm_mode in {'builtin', 'amocrm', 'bitrix24'} and crm_mode != tenant.crm_mode:
        tenant.crm_mode = crm_mode
        tenant.save(update_fields=['crm_mode'])
    if crm_mode == 'builtin':
        _seed_default_pipeline()


def _apply_managers_step(tenant, payload: dict):
    managers = payload.get('managers')
    if not managers:
        return
    # Accept structured data: [{"name": "...", "email": "..."}]
    if isinstance(managers, list):
        entries = managers
    else:
        # Legacy: comma-separated string of "email:name" or just names
        entries = []
        items = [item.strip() for item in str(managers).replace(';', ',').replace('\n', ',').split(',') if item.strip()]
        for item in items:
            if ':' in item:
                email, name = item.split(':', 1)
                entries.append({'email': email.strip(), 'name': name.strip()})
            elif '@' in item:
                entries.append({'email': item, 'name': item.split('@')[0]})
            else:
                entries.append({'name': item})
    for entry in entries:
        if isinstance(entry, str):
            entry = {'name': entry}
        email = entry.get('email', '').strip()
        name = entry.get('name', '').strip()
        if not name and not email:
            continue
        if not email:
            continue  # email is required — skip entries without it
        email = email.lower()
        if not name:
            name = email.split('@')[0]
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            username = _next_available_username(name or email.split('@')[0])
            user = User.objects.create_user(
                email=email,
                username=username,
                password=None,
            )

        membership = Membership.objects.filter(user_id=user.id, tenant_id=tenant.id).first()
        invite_token = None
        now = timezone.now()
        if membership and membership.is_active and membership.joined_at and not membership.invite_token:
            # Already an active member of this org — no onboarding invite required.
            pass
        else:
            invite_token = uuid.uuid4()
            if membership:
                membership.role = 'manager'
                membership.is_active = True
                membership.invite_token = invite_token
                membership.invited_at = now
                membership.joined_at = None
                membership.save(update_fields=['role', 'is_active', 'invite_token', 'invited_at', 'joined_at'])
            else:
                Membership.objects.create(
                    user=user,
                    tenant=tenant,
                    role='manager',
                    is_active=True,
                    invite_token=invite_token,
                    invited_at=now,
                )

        ManagerProfile.objects.get_or_create(
            user=user,
            defaults={'crm_user_name': name, 'crm_user_id': '', 'schedule': {}, 'is_active': True},
        )
        if invite_token:
            invite_link = f'{settings.FRONTEND_APP_URL.rstrip("/")}/invite/accept?token={invite_token}'
            send_mail(
                subject='Приглашение в CRM Platform',
                message=(
                    f'Вас пригласили в организацию "{tenant.name}" с ролью "manager".\n'
                    f'Ссылка для принятия приглашения: {invite_link}'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )


def _apply_distribution_step(payload: dict):
    strategy = payload.get('strategy', 'round_robin')
    valid = {'min_load', 'round_robin', 'weighted', 'manual_queue'}
    if strategy not in valid:
        strategy = 'round_robin'
    DistributionRule.objects.get_or_create(
        name='Основное правило',
        defaults={
            'trigger': 'new_lead',
            'strategy': strategy,
            'priority': 0,
            'is_active': True,
        },
    )


def _seed_default_pipeline():
    """Create a default sales pipeline with typical stages if none exists."""
    from apps.crm.models import Pipeline, Stage

    if Pipeline.objects.exists():
        return

    pipeline = Pipeline.objects.create(name='Продажи', is_default=True, sort_order=0)
    stages = [
        ('Новая заявка', 'open', '#3B82F6', 0),
        ('Квалификация', 'open', '#8B5CF6', 1),
        ('Предложение', 'open', '#F59E0B', 2),
        ('Переговоры', 'open', '#EF4444', 3),
        ('Согласование', 'open', '#10B981', 4),
        ('Успешно закрыта', 'won', '#22C55E', 5),
        ('Проиграна', 'lost', '#6B7280', 6),
    ]
    Stage.objects.bulk_create([
        Stage(pipeline=pipeline, name=name, stage_type=stype, color=color, sort_order=order)
        for name, stype, color, order in stages
    ])


def _next_available_username(seed: str) -> str:
    base = ''.join(ch for ch in str(seed).strip().lower() if ch.isalnum() or ch in {'_', '-', '.'}) or 'user'
    base = base[:150]
    candidate = base
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        suffix_token = f'_{suffix}'
        candidate = f'{base[: max(1, 150 - len(suffix_token))]}{suffix_token}'
        suffix += 1
    return candidate

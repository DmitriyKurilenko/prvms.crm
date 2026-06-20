"""Бизнес-логика телефонии Exolve.

Здесь сосредоточены три задачи:
1. Провижининг — подбор/покупка номера и заведение SIP-аккаунтов менеджеров.
2. Резолв тенанта по номеру для публичных webhook-ов (IPCR / Call Events).
3. Синхронное решение по входящему звонку (getControlCallFollowMe):
   резолв контакта, контроль дублей сделки, выбор маршрута на ответственного.

Контракты Exolve см. в :mod:`apps.telephony.exolve_client` и в документации
``instructions/call-forwarding-to-url`` (метод getControlCallFollowMe).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.tenants.models import ExolveNumberLookup, Tenant

from .exolve_client import ExolveClient, ExolveError
from .models import CallRecord, ExolveChannel, ExolveSIPAccount

logger = logging.getLogger(__name__)

_RESPONSIBLE_TIMEOUT = 25
_OTHERS_TIMEOUT = 25


# ---------------------------------------------------------------------------
# Публичные URL webhook-ов
# ---------------------------------------------------------------------------

def _public_base_url() -> str:
    base = (getattr(settings, 'EXOLVE_PUBLIC_BASE_URL', '') or '').strip()
    if base:
        return base.rstrip('/')
    return f'{settings.PLATFORM_PROTOCOL}://{settings.PLATFORM_DOMAIN}'.rstrip('/')


def _webhook_qs() -> str:
    secret = (getattr(settings, 'EXOLVE_WEBHOOK_SECRET', '') or '').strip()
    return f'?key={secret}' if secret else ''


def ipcr_url() -> str:
    return f'{_public_base_url()}/telephony/exolve/ipcr/{_webhook_qs()}'


def events_url() -> str:
    return f'{_public_base_url()}/telephony/exolve/events/{_webhook_qs()}'


# ---------------------------------------------------------------------------
# Нормализация телефона
# ---------------------------------------------------------------------------

def _digits(value: str) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


# ---------------------------------------------------------------------------
# Канал тенанта
# ---------------------------------------------------------------------------

def get_channel() -> ExolveChannel:
    channel = ExolveChannel.objects.order_by('id').first()
    if channel is None:
        channel = ExolveChannel.objects.create()
    return channel


# ---------------------------------------------------------------------------
# Подбор номеров (для UI-мастера)
# ---------------------------------------------------------------------------

def number_reference(client: ExolveClient | None = None) -> dict:
    client = client or ExolveClient()
    return client.number_reference()


def list_available_numbers(type_id: int, region_id: int | None = None,
                           mask: str = '', limit: int = 20,
                           client: ExolveClient | None = None) -> dict:
    client = client or ExolveClient()
    return client.number_get_free(type_id=type_id, region_id=region_id, mask=mask, limit=limit)


# ---------------------------------------------------------------------------
# Подключение выбранного номера (Lock -> Buy -> SetCallForwarding)
# ---------------------------------------------------------------------------

def connect_number(tenant: Tenant, number_code: str, number_e164: str,
                   type_id: int | None = None, region_id: int | None = None,
                   client: ExolveClient | None = None) -> ExolveChannel:
    """Купить выбранный номер и направить его на IPCR-URL.

    Шаги полностью автоматические; пользователь только выбрал номер в UI.
    """
    client = client or ExolveClient()
    channel = get_channel()
    channel.status = 'connecting'
    channel.status_detail = ''
    channel.exolve_number = _digits(number_e164)
    channel.number_code = str(number_code)
    channel.type_id = type_id
    channel.region_id = region_id
    channel.save()

    try:
        lock = client.number_lock(number_code, seconds=300)
        reserve_uid = lock.get('Id') or lock.get('id') or lock.get('uid')
        if not reserve_uid:
            raise ExolveError(f'Lock не вернул идентификатор брони: {lock}')
        client.number_buy(number_code, reserve_uid)
        client.number_set_forwarding_ipcr(
            number_code,
            url=ipcr_url(),
            reserve=getattr(settings, 'EXOLVE_IPCR_RESERVE', ''),
        )
    except ExolveError as exc:
        channel.status = 'error'
        channel.status_detail = str(exc)
        channel.save(update_fields=['status', 'status_detail'])
        logger.exception('Exolve connect_number failed for tenant %s', tenant.schema_name)
        raise

    channel.status = 'active'
    channel.status_detail = ''
    channel.forwarding_set_at = timezone.now()
    channel.save(update_fields=['status', 'status_detail', 'forwarding_set_at'])

    _upsert_number_lookup(tenant, channel)
    ensure_sip_accounts(tenant, client=client)
    return channel


def _upsert_number_lookup(tenant: Tenant, channel: ExolveChannel) -> None:
    with schema_context('public'):
        ExolveNumberLookup.objects.filter(tenant=tenant).exclude(number=channel.exolve_number).delete()
        ExolveNumberLookup.objects.update_or_create(
            number=channel.exolve_number,
            defaults={'tenant': tenant, 'number_code': channel.number_code},
        )


def connect_existing_number(tenant: Tenant, number: str, number_code: str,
                            sip_resource_id: str, sip_username: str,
                            client: ExolveClient | None = None) -> ExolveChannel:
    """Подключить уже купленный номер к тенанту через переадресацию type=2 на SIP.

    Применяется, когда номер занят как CLI SIP-аккаунта и IPCR недоступен:
    ставим статическую переадресацию номера на SIP менеджера с event_url на наш
    приёмник Call Events (там создаётся сделка с контролем дублей). Покупку не
    выполняем — номер и SIP уже существуют на аккаунте Exolve.
    """
    from apps.distribution.services import ensure_builtin_manager_profiles
    from apps.integrations.models import ManagerProfile

    client = client or ExolveClient()
    digits = _digits(number)

    attrs = client.sip_get_attributes(sip_resource_id).get('attributes', {})
    password = attrs.get('password', '')

    channel = get_channel()
    channel.exolve_number = digits
    channel.number_code = str(number_code)
    # Номер «принадлежит» SIP-аккаунту (создан с этим номером): входящий на номер
    # маршрутизируется на этот SIP напрямую, поэтому SetCallForwarding не ставим
    # (Exolve отвергает его как "number has sip"). События вызова приходят на
    # app-level URL «Уведомление о событиях» (задаётся в портале Exolve, без API).
    channel.status = 'active'
    channel.status_detail = ''
    channel.forwarding_set_at = timezone.now()
    channel.save()
    _upsert_number_lookup(tenant, channel)

    if getattr(tenant, 'crm_mode', None) == 'builtin':
        ensure_builtin_manager_profiles()
    manager = ManagerProfile.objects.filter(is_active=True).order_by('id').first()
    if manager:
        ExolveSIPAccount.objects.update_or_create(
            manager=manager,
            defaults={
                'sip_resource_id': str(sip_resource_id),
                'username': sip_username,
                'password': password,
                'display_number': digits,
                'status': 'active',
                'is_active': True,
            },
        )
    return channel


def register_inbound_deal(from_number: str, to_number: str):
    """Создать/найти контакт и сделку (контроль дублей) для входящего звонка.

    Вызывается из обработчика Call Events на событии 'b' (начало вызова).
    Возвращает (contact, deal, manager_profile ответственного или None).
    """
    from apps.integrations.models import ManagerProfile

    contact, _ = _get_or_create_contact(from_number)
    deal, _ = _ensure_deal_with_dedup(contact, from_number)
    responsible_user_id = _responsible_user_id(deal, contact)
    manager_profile = None
    if responsible_user_id:
        manager_profile = ManagerProfile.objects.filter(user_id=responsible_user_id, is_active=True).first()
    return contact, deal, manager_profile


# ---------------------------------------------------------------------------
# Провижининг SIP-аккаунтов менеджеров
# ---------------------------------------------------------------------------

def provision_sip_account(manager, number_code: str, display_number: str,
                          client: ExolveClient | None = None) -> ExolveSIPAccount:
    """Создать SIP-аккаунт менеджера через SIP API и сохранить креды."""
    client = client or ExolveClient()
    account, _ = ExolveSIPAccount.objects.get_or_create(manager=manager)
    if account.status == 'active' and account.username:
        return account

    account.status = 'provisioning'
    account.status_detail = ''
    account.save(update_fields=['status', 'status_detail'])
    try:
        created = client.sip_create(
            sip_name=f'crm-{manager.id}-{manager.crm_user_name[:20]}',
            number=number_code,
            call_record=True,
        )
        sip_resource_id = created.get('sip_resource_id')
        username = created.get('username', '')
        attrs = client.sip_get_attributes(sip_resource_id).get('attributes', {})
        password = attrs.get('password', '')
        if display_number:
            client.sip_set_display_number(sip_resource_id, _digits(display_number))
    except ExolveError as exc:
        account.status = 'error'
        account.status_detail = str(exc)
        account.save(update_fields=['status', 'status_detail'])
        logger.exception('Exolve SIP provisioning failed for manager %s', manager.id)
        raise

    account.sip_resource_id = str(sip_resource_id)
    account.username = username or attrs.get('username', '')
    account.password = password
    account.display_number = _digits(display_number)
    account.status = 'active'
    account.status_detail = ''
    account.is_active = True
    account.save()
    return account


def ensure_sip_accounts(tenant: Tenant, client: ExolveClient | None = None) -> int:
    """Завести SIP-аккаунты всем активным менеджерам тенанта без аккаунта."""
    from apps.distribution.services import ensure_builtin_manager_profiles
    from apps.integrations.models import ManagerProfile

    client = client or ExolveClient()
    channel = get_channel()
    if not channel.number_code:
        return 0
    if getattr(tenant, 'crm_mode', None) == 'builtin':
        ensure_builtin_manager_profiles()

    provisioned = 0
    for manager in ManagerProfile.objects.filter(is_active=True):
        account = getattr(manager, 'exolve_sip', None)
        if account and account.status == 'active' and account.username:
            continue
        try:
            provision_sip_account(manager, channel.number_code, channel.exolve_number, client=client)
            provisioned += 1
        except ExolveError:
            continue
    return provisioned


# ---------------------------------------------------------------------------
# Резолв тенанта по номеру (для публичных webhook-ов)
# ---------------------------------------------------------------------------

def resolve_tenant_by_number(number: str) -> Tenant | None:
    digits = _digits(number)
    if not digits:
        return None
    with schema_context('public'):
        row = (
            ExolveNumberLookup.objects.select_related('tenant')
            .filter(number=digits, tenant__is_active=True)
            .first()
        )
        if row:
            return row.tenant
        # запасной матч по последним 10 цифрам
        if len(digits) >= 10:
            tail = digits[-10:]
            row = (
                ExolveNumberLookup.objects.select_related('tenant')
                .filter(number__endswith=tail, tenant__is_active=True)
                .first()
            )
            if row:
                return row.tenant
    return None


# ---------------------------------------------------------------------------
# Входящий звонок: контакт, дедуп сделки, маршрут
# ---------------------------------------------------------------------------

def _find_contact(numberA: str):
    from apps.crm.models import Contact

    digits = _digits(numberA)
    contact = Contact.objects.filter(phone=numberA).first() or Contact.objects.filter(phone=digits).first()
    if not contact and len(digits) >= 10:
        contact = Contact.objects.filter(phone__endswith=digits[-10:]).first()
    return contact


def _get_or_create_contact(numberA: str):
    from apps.crm.models import Contact

    contact = _find_contact(numberA)
    if contact:
        return contact, False
    contact = Contact.objects.create(
        first_name=f'Клиент {numberA}',
        phone=_digits(numberA),
        source='exolve',
    )
    return contact, True


def _ensure_deal_with_dedup(contact, numberA: str):
    """Контроль дублей: при наличии активной (open) сделки новую не создаём."""
    from apps.channels.tasks import _find_pipeline_and_stage
    from apps.crm.models import Deal
    from apps.distribution.services import ensure_builtin_manager_profiles, try_distribute

    open_deal = (
        Deal.objects.filter(contact=contact, stage__stage_type='open')
        .order_by('-updated_at')
        .first()
    )
    if open_deal:
        return open_deal, False

    result = _find_pipeline_and_stage()
    if result is None:
        logger.warning('Exolve inbound: воронка/этап не настроены — сделка не создана')
        return None, False
    pipeline, stage = result
    deal = Deal.objects.create(
        name=f'Звонок {numberA}',
        pipeline=pipeline,
        stage=stage,
        contact=contact,
        source='exolve',
    )
    if not deal.responsible_id:
        ensure_builtin_manager_profiles()
        try_distribute('new_deal', 'deal', str(deal.id))
        deal.refresh_from_db()
    return deal, True


def _responsible_user_id(deal, contact) -> int | None:
    if deal and deal.responsible_id:
        return deal.responsible_id
    if contact and contact.responsible_id:
        return contact.responsible_id
    return None


def _followme_targets(responsible_user_id: int | None):
    """Вернуть (responsible_account, other_accounts) среди активных SIP."""
    accounts = list(
        ExolveSIPAccount.objects.filter(is_active=True, status='active')
        .exclude(username='')
        .select_related('manager')
    )
    responsible = None
    others = []
    for acc in accounts:
        if responsible_user_id and acc.manager.user_id == responsible_user_id and responsible is None:
            responsible = acc
        else:
            others.append(acc)
    return responsible, others


def build_followme_response(rpc_id, tenant: Tenant, sip_id: str, numberA: str, call_sid: str) -> dict:
    """Синхронное решение по входящему звонку.

    Выполняется в контексте tenant. Создаёт/находит контакт и сделку (с контролем
    дублей), определяет ответственного и строит followme_struct: ответственный
    (order 1) → остальные активные менеджеры (order 2, параллельно).
    """
    from apps.crm.models import Activity

    contact, _ = _get_or_create_contact(numberA)
    deal, _ = _ensure_deal_with_dedup(contact, numberA)
    responsible_user_id = _responsible_user_id(deal, contact)
    responsible_acc, other_accs = _followme_targets(responsible_user_id)

    followme: list[dict] = []
    order = 1
    if responsible_acc:
        followme.append({
            'I_FOLLOW_ORDER': 1,
            'ACTIVE': True,
            'NAME': responsible_acc.manager.crm_user_name or 'Менеджер',
            'REDIRECT_NUMBER': responsible_acc.username,
            'PERIOD': 'always',
            'PERIOD_DESCRIPTION': 'always',
            'TIMEOUT': _RESPONSIBLE_TIMEOUT,
        })
        order = 2
    for acc in other_accs:
        followme.append({
            'I_FOLLOW_ORDER': order,
            'ACTIVE': True,
            'NAME': acc.manager.crm_user_name or 'Менеджер',
            'REDIRECT_NUMBER': acc.username,
            'PERIOD': 'always',
            'PERIOD_DESCRIPTION': 'always',
            'TIMEOUT': _OTHERS_TIMEOUT,
        })

    manager_profile = responsible_acc.manager if responsible_acc else None
    CallRecord.objects.update_or_create(
        call_sid=call_sid,
        defaults={
            'direction': 'inbound',
            'caller_number': numberA,
            'called_number': sip_id,
            'result': 'missed',
            'manager': manager_profile,
            'crm_contact_id': str(contact.id) if contact else '',
            'crm_lead_id': str(deal.id) if deal else '',
            'started_at': timezone.now(),
        },
    )
    if deal:
        Activity.objects.create(
            activity_type='call',
            deal=deal,
            contact=contact,
            title=f'Входящий звонок {numberA}',
            body='Входящий звонок через Exolve',
            status='planned',
        )

    redirect_type = 2 if followme else 1
    logger.info(
        'Exolve IPCR decision tenant=%s call_sid=%s numberA=%s targets=%s',
        tenant.schema_name, call_sid, numberA, [t['REDIRECT_NUMBER'] for t in followme],
    )
    return {
        'id': rpc_id,
        'jsonrpc': '2.0',
        'sip_id': sip_id,
        'result': {
            'redirect_type': redirect_type,
            'event_URL': events_url(),
            'masking': False,
            'followme_struct': [1, followme],
        },
    }

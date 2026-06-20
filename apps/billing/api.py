import logging
import uuid

from django.conf import settings
from django_tenants.utils import schema_context
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from yookassa import Configuration as YooConfiguration
from yookassa import Payment as YooPayment

from apps.billing.catalog import get_active_plans_queryset, serialize_plan_for_client
from apps.core.access import require_roles
from apps.core.tenant import get_request_tenant

from .models import Payment, Plan

logger = logging.getLogger(__name__)

billing_router = Router(tags=['billing'], auth=JWTAuth())

# Configure YooKassa globally
if settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY:
    YooConfiguration.account_id = settings.YOOKASSA_SHOP_ID
    YooConfiguration.secret_key = settings.YOOKASSA_SECRET_KEY


class FeatureOut(Schema):
    code: str
    name: str
    description: str


class PlanOut(Schema):
    id: int
    name: str
    slug: str
    features: list[FeatureOut]
    max_managers: int | None
    max_documents_per_month: int | None
    max_crm_connections: int | None
    max_pipelines: int | None
    price_monthly: float
    is_active: bool


class CheckoutIn(Schema):
    plan_slug: str
    months: int = 1


class CheckoutOut(Schema):
    payment_id: int
    amount: float
    status: str
    confirmation_url: str


class ChangePlanIn(Schema):
    plan_slug: str


class PaymentOut(Schema):
    id: int
    plan_name: str
    amount: float
    months: int
    status: str
    created_at: str
    paid_at: str | None
    expires_at: str | None


@billing_router.get('/plans/', response=list[PlanOut], auth=None)
def list_plans(request):
    plans = get_active_plans_queryset()
    return [PlanOut(**serialize_plan_for_client(plan)) for plan in plans]


@billing_router.post('/checkout/', response={200: CheckoutOut, 400: dict})
def checkout(request, payload: CheckoutIn):
    """Создать платёж в ЮKassa и вернуть URL для перенаправления пользователя."""
    require_roles(request, ['owner'], allow_trial_expired=True)
    tenant = get_request_tenant(request)

    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        raise HttpError(503, 'Платёжная система не настроена. Обратитесь к администратору.')

    plan = Plan.objects.filter(slug=payload.plan_slug, is_active=True).first()
    if not plan:
        return 400, {'detail': f'Plan "{payload.plan_slug}" not found'}

    if payload.months < 1 or payload.months > 12:
        return 400, {'detail': 'months must be 1-12'}

    amount = plan.price_monthly * payload.months

    with schema_context('public'):
        payment = Payment.objects.create(
            tenant=tenant,
            plan=plan,
            amount=amount,
            months=payload.months,
            status='pending',
        )

    idempotence_key = str(uuid.uuid4())
    description = f'Подписка «{plan.name}» на {payload.months} мес. (Организация: {tenant.name})'

    yoo_payment = YooPayment.create({
        'amount': {
            'value': f'{amount:.2f}',
            'currency': 'RUB',
        },
        'confirmation': {
            'type': 'redirect',
            'return_url': settings.YOOKASSA_RETURN_URL,
        },
        'capture': True,
        'description': description[:128],
        'metadata': {
            'payment_id': str(payment.id),
            'tenant_slug': tenant.slug,
        },
    }, idempotence_key)

    with schema_context('public'):
        payment.yookassa_payment_id = yoo_payment.id
        payment.yookassa_confirmation_url = yoo_payment.confirmation.confirmation_url
        payment.save(update_fields=['yookassa_payment_id', 'yookassa_confirmation_url'])

    return CheckoutOut(
        payment_id=payment.id,
        amount=float(amount),
        status='pending',
        confirmation_url=yoo_payment.confirmation.confirmation_url,
    )


@billing_router.get('/payments/', response=list[PaymentOut])
def list_payments(request):
    """История платежей тенанта."""
    require_roles(request, ['owner', 'admin'], allow_trial_expired=True)
    tenant = get_request_tenant(request)
    with schema_context('public'):
        payments = Payment.objects.filter(tenant=tenant).order_by('-created_at')[:50]
        return [
            PaymentOut(
                id=p.id,
                plan_name=p.plan.name,
                amount=float(p.amount),
                months=p.months,
                status=p.status,
                created_at=p.created_at.isoformat(),
                paid_at=p.paid_at.isoformat() if p.paid_at else None,
                expires_at=p.expires_at.isoformat() if p.expires_at else None,
            )
            for p in payments
        ]


@billing_router.post('/change-plan/', response={200: dict, 400: dict})
def change_plan(request, payload: ChangePlanIn):
    """Сменить план (только на триале, до оплаты)."""
    require_roles(request, ['owner'], allow_trial_expired=True)
    tenant = get_request_tenant(request)

    if tenant.is_paid:
        return 400, {'detail': 'Для смены плана после оплаты обратитесь к администратору.'}

    plan = Plan.objects.filter(slug=payload.plan_slug, is_active=True).first()
    if not plan:
        return 400, {'detail': f'Plan "{payload.plan_slug}" not found'}

    with schema_context('public'):
        tenant.plan = plan
        tenant.save(update_fields=['plan'])

    return {'detail': f'План изменён на "{plan.name}".'}

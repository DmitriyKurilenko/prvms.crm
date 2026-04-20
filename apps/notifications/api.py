from django.conf import settings
from django.utils import timezone
from django.core.signing import TimestampSigner
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth
from apps.core.access import require_membership, require_roles
from apps.core.tenant import get_request_tenant
from .models import Notification, NotificationPreference, TelegramBinding
from .services import notify

notifications_router = Router(tags=['notifications'], auth=JWTAuth())


class NotificationOut(Schema):
    id: int
    event: str
    title: str
    body: str
    link: str
    is_read: bool
    channel: str
    sent_at: str


class PreferenceOut(Schema):
    event: str
    channel: str
    is_enabled: bool
    recipient_roles: list[str]


class PreferenceIn(Schema):
    event: str
    channel: str
    is_enabled: bool
    recipient_roles: list[str] = []


@notifications_router.get('/', response=list[NotificationOut])
def list_notifications(request, limit: int = 50, offset: int = 0):
    require_membership(request)
    qs = Notification.objects.filter(user=request.auth, channel='in_app')
    items = qs[offset:offset + limit]
    return [
        NotificationOut(
            id=n.id,
            event=n.event,
            title=n.title,
            body=n.body,
            link=n.link,
            is_read=n.is_read,
            channel=n.channel,
            sent_at=n.sent_at.isoformat(),
        )
        for n in items
    ]


@notifications_router.post('/{notification_id}/read/')
def mark_read(request, notification_id: int):
    require_membership(request)
    Notification.objects.filter(
        id=notification_id, user=request.auth
    ).update(is_read=True, read_at=timezone.now())
    return {'detail': 'ok'}


@notifications_router.post('/read-all/')
def mark_all_read(request):
    require_membership(request)
    Notification.objects.filter(
        user=request.auth, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    return {'detail': 'ok'}


@notifications_router.get('/preferences/', response=list[PreferenceOut])
def list_preferences(request):
    require_roles(request, ['owner', 'admin'])
    prefs = NotificationPreference.objects.all()
    return [
        PreferenceOut(
            event=p.event,
            channel=p.channel,
            is_enabled=p.is_enabled,
            recipient_roles=p.recipient_roles,
        )
        for p in prefs
    ]


@notifications_router.put('/preferences/')
def update_preferences(request, payload: list[PreferenceIn]):
    require_roles(request, ['owner', 'admin'])
    for item in payload:
        NotificationPreference.objects.update_or_create(
            event=item.event,
            channel=item.channel,
            defaults={
                'is_enabled': item.is_enabled,
                'recipient_roles': item.recipient_roles,
            },
        )
    return {'detail': 'Preferences updated'}


@notifications_router.post('/test/')
def send_test_notification(request):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    notify(
        tenant,
        'new_deal_created',
        {'message': 'Тестовое уведомление', 'link': '/notifications'},
    )
    return {'detail': 'Test notification queued'}


@notifications_router.get('/telegram/status/')
def telegram_status(request):
    require_membership(request)
    binding = TelegramBinding.objects.filter(user=request.auth, is_active=True).first()
    return {
        'linked': binding is not None,
        'chat_id': binding.chat_id if binding else None,
        'username': binding.username if binding else '',
        'bot_username': settings.TELEGRAM_NOTIFICATION_BOT_USERNAME,
    }


@notifications_router.post('/telegram/link/')
def telegram_link(request, payload: dict | None = None):
    require_membership(request)
    payload = payload or {}
    chat_id = payload.get('chat_id')
    if not chat_id:
        signer = TimestampSigner(salt='telegram-binding')
        bind_token = signer.sign(str(request.auth.id))
        bot_username = settings.TELEGRAM_NOTIFICATION_BOT_USERNAME
        link = f'https://t.me/{bot_username}?start=bind_{bind_token}' if bot_username else ''
        return {
            'detail': 'Use this token in Telegram bot /start flow',
            'bind_token': bind_token,
            'telegram_link': link,
        }
    binding, _ = TelegramBinding.objects.update_or_create(
        user=request.auth,
        defaults={'chat_id': int(chat_id), 'username': payload.get('username', ''), 'is_active': True},
    )
    return {'detail': 'linked', 'chat_id': binding.chat_id}


@notifications_router.delete('/telegram/unlink/')
def telegram_unlink(request):
    require_membership(request)
    TelegramBinding.objects.filter(user=request.auth).update(is_active=False)
    return {'detail': 'unlinked'}

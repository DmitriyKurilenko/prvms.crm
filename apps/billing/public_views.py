from __future__ import annotations

import json
from datetime import timedelta
from math import ceil

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.notifications.tasks import send_email_async

from .models import PricingQuote, TelephonyQuoteRequest

# ---------- Helpers ----------


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _calculate_quote(data: dict) -> tuple[int, list[dict], bool]:
    cfg = settings.PRICING_CUSTOM
    total = 0
    breakdown = []
    telephony = bool(data.get('telephony', {}).get('requested'))

    users = max(0, int(data.get('users', 1)))
    user_total = users * cfg['user']
    total += user_total
    breakdown.append({'label': 'Пользователи', 'qty': users, 'unit_price': cfg['user'], 'total': user_total})

    messengers = data.get('messengers', [])
    if isinstance(messengers, list):
        m_count = len(messengers)
    else:
        m_count = 0
    m_total = m_count * cfg['messenger']
    total += m_total
    if m_count:
        breakdown.append({'label': 'Мессенджеры', 'qty': m_count, 'unit_price': cfg['messenger'], 'total': m_total})

    channels = data.get('inbound_channels', [])
    if isinstance(channels, list):
        c_count = len(channels)
    else:
        c_count = 0
    c_total = c_count * cfg['inbound_channel']
    total += c_total
    if c_count:
        breakdown.append({'label': 'Входящие каналы', 'qty': c_count, 'unit_price': cfg['inbound_channel'], 'total': c_total})

    documents = max(0, int(data.get('documents', 0)))
    doc_blocks = ceil(documents / 100)
    doc_total = doc_blocks * cfg['documents_per_100']
    total += doc_total
    if doc_total:
        breakdown.append({'label': 'Документы', 'qty': documents, 'unit_price': cfg['documents_per_100'], 'total': doc_total, 'note': 'за каждые 100'})

    signatures = max(0, int(data.get('signatures', 0)))
    sig_blocks = ceil(signatures / 50)
    sig_total = sig_blocks * cfg['signatures_per_50']
    total += sig_total
    if sig_total:
        breakdown.append({'label': 'Подписания', 'qty': signatures, 'unit_price': cfg['signatures_per_50'], 'total': sig_total, 'note': 'за каждые 50'})

    if telephony:
        breakdown.append({'label': 'Телефония', 'qty': 1, 'unit_price': 0, 'total': 0, 'note': 'по запросу'})

    return total, breakdown, telephony


# ---------- Endpoints ----------


@csrf_exempt
def pricing_calculator_quote(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    total, breakdown, telephony = _calculate_quote(data)
    expires_at = timezone.now() + timedelta(hours=24)
    quote = PricingQuote.objects.create(
        expires_at=expires_at,
        config=data,
        monthly_total=total,
        telephony_requires_quote=telephony,
    )

    return JsonResponse({
        'monthly_total': total,
        'breakdown': breakdown,
        'telephony_requires_quote': telephony,
        'quote_id': str(quote.id),
    })


@csrf_exempt
def pricing_telephony_request(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    # Honeypot protection
    if data.get('website'):
        return JsonResponse({'detail': 'Bad request'}, status=400)

    # Rate limit by IP: 1 request per minute
    client_ip = _get_client_ip(request)
    cache_key = f'telephony_req:{client_ip}'
    if cache.get(cache_key):
        return JsonResponse({'detail': 'Слишком много запросов. Попробуйте через минуту.'}, status=429)
    cache.set(cache_key, True, timeout=60)

    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip()
    phone = str(data.get('phone', '')).strip()
    config = data.get('configuration', {})

    if not name or (not email and not phone):
        return JsonResponse({'detail': 'Укажите имя и контакт (email или телефон)'}, status=400)

    TelephonyQuoteRequest.objects.create(
        name=name,
        email=email,
        phone=phone,
        config_json=config,
    )

    # Async email to support
    support_email = getattr(settings, 'SUPPORT_EMAIL', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    if support_email:
        subject = f'Заявка на телефонию от {name}'
        message_lines = [
            'Новая заявка на подключение телефонии (СВОБОДНЫЙ тариф).',
            '',
            f'Имя: {name}',
            f'Email: {email}',
            f'Телефон: {phone}',
            f'Конфигурация: {json.dumps(config, ensure_ascii=False, indent=2)}',
        ]
        send_email_async.delay(subject, '\n'.join(message_lines), None, [support_email])

    return JsonResponse({'status': 'ok'})

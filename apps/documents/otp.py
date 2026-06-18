"""OTP lifecycle: generation, hashing, verification, delivery (SMS/email)."""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _generate_otp() -> str:
    return ''.join(str(secrets.randbelow(10)) for _ in range(6))


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def _verify_otp(code: str, otp_hash: str) -> bool:
    return hmac.compare_digest(_hash_otp(code), otp_hash)


def _send_otp(recipient: str, code: str, method: str):
    if method == 'email_otp':
        send_mail(
            subject='Код подтверждения документа',
            message=f'Ваш код подтверждения: {code}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
        return
    # SMS OTP
    _send_sms(recipient, f'Код подтверждения документа: {code}')


def _send_sms(phone: str, message: str):
    """Send SMS via configured provider."""
    import requests as _requests

    provider = getattr(settings, 'SMS_PROVIDER', 'stub')
    api_key = getattr(settings, 'SMS_API_KEY', '')
    sender_name = getattr(settings, 'SMS_SENDER_NAME', 'Platform')

    if provider == 'stub' or not api_key:
        logger.info('SMS stub: phone=%s message=%s', phone, message)
        return

    if provider == 'smsru':
        resp = _requests.get(
            'https://sms.ru/sms/send',
            params={
                'api_id': api_key,
                'to': phone,
                'msg': message,
                'json': 1,
                'from': sender_name,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != 'OK':
            logger.error('sms.ru send failed: %s', data)
    elif provider == 'smsc':
        resp = _requests.post(
            'https://smsc.ru/sys/send.php',
            data={
                'login': getattr(settings, 'SMS_SMSC_LOGIN', ''),
                'psw': api_key,
                'phones': phone,
                'mes': message,
                'sender': sender_name,
                'fmt': 3,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            logger.error('SMSC send failed: %s', data)
    else:
        logger.warning('Unknown SMS provider: %s, message not sent', provider)

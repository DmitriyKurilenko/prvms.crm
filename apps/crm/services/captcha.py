"""Подключаемая проверка капчи для публичных веб-форм.

Контракт провайдеров (сверено с официальной документацией):
- reCAPTCHA: ``POST https://www.google.com/recaptcha/api/siteverify`` с
  ``secret`` и ``response`` → JSON ``{"success": bool, "error-codes": [...]}``.
- hCaptcha: ``POST https://hcaptcha.com/siteverify`` с теми же параметрами и
  тем же форматом ответа.

Если ``CAPTCHA_SECRET`` не задан, проверка отключена и пропускает любой запрос
(``True``) — существующие формы продолжают работать без капчи. Самодиагностика:
каждый живой вызов пишет в логгер ``crm.webform`` исход и коды ошибок, что
позволяет подтвердить интеграцию за один прогон на боевых ключах.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger('crm.webform')

_DEFAULT_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def captcha_enabled() -> bool:
    return bool(getattr(settings, 'CAPTCHA_SECRET', ''))


def captcha_site_info() -> dict | None:
    """Публичные данные для рендера капчи виджетом (None, если капча отключена)."""
    if not captcha_enabled():
        return None
    return {
        'provider': getattr(settings, 'CAPTCHA_PROVIDER', 'recaptcha'),
        'site_key': getattr(settings, 'CAPTCHA_SITE_KEY', ''),
    }


def verify_captcha(response_token: str, remote_ip: str | None = None) -> bool:
    """Проверяет токен капчи у провайдера. При отключённой капче — пропускает."""
    if not captcha_enabled():
        return True
    if not response_token:
        logger.warning('captcha: пустой токен при включённой капче')
        return False

    verify_url = getattr(settings, 'CAPTCHA_VERIFY_URL', '') or _DEFAULT_VERIFY_URL
    payload = {'secret': settings.CAPTCHA_SECRET, 'response': response_token}
    if remote_ip:
        payload['remoteip'] = remote_ip
    try:
        resp = requests.post(verify_url, data=payload, timeout=10)
        result = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error('captcha verify failed: %s', exc)
        return False
    success = bool(result.get('success'))
    logger.info('captcha verify success=%s errors=%s', success, result.get('error-codes'))
    return success

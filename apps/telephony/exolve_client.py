"""HTTP-клиент MTS Exolve REST API (Numbering API + SIP API).

Контракты (официальная документация Exolve):
- Numbering API:  https://docs.exolve.ru/docs/ru/api-reference/numbering-api/
- SIP API:        https://docs.exolve.ru/docs/ru/api-reference/sip-api/
- Call forwarding to URL (IPCR):
                  https://docs.exolve.ru/docs/ru/instructions/call-forwarding-to-url/

Все методы — POST с JSON-телом и заголовком ``Authorization: Bearer <EXOLVE_API_KEY>``.
Клиент логирует каждый запрос и ответ целиком (с маскированием ключа), чтобы
интеграцию можно было подтвердить за один боевой прогон.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 20


class ExolveError(Exception):
    """Ошибка обращения к Exolve API."""

    def __init__(self, message: str, *, status: int | None = None, body: str = ''):
        super().__init__(message)
        self.status = status
        self.body = body


class ExolveClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else settings.EXOLVE_API_KEY
        self.base_url = (base_url or settings.EXOLVE_API_BASE).rstrip('/')

    # ------------------------------------------------------------------
    # Низкоуровневый POST
    # ------------------------------------------------------------------
    def _post(self, path: str, payload: dict) -> dict:
        if not self.api_key:
            raise ExolveError('EXOLVE_API_KEY не задан — провижининг невозможен')
        url = f'{self.base_url}{path}'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        logger.info('Exolve POST %s payload=%s', path, payload)
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            logger.exception('Exolve POST %s network error', path)
            raise ExolveError(f'Сеть Exolve недоступна: {exc}') from exc

        body = resp.text or ''
        logger.info('Exolve POST %s -> %s %s', path, resp.status_code, body[:2000])
        if resp.status_code >= 400:
            raise ExolveError(
                f'Exolve {path} вернул {resp.status_code}: {body[:500]}',
                status=resp.status_code,
                body=body,
            )
        try:
            return resp.json() if body.strip() else {}
        except ValueError:
            return {}

    # ------------------------------------------------------------------
    # Numbering API
    # ------------------------------------------------------------------
    def number_reference(self) -> dict:
        """GetList — справочник типов/категорий/регионов номеров."""
        return self._post('/number/reference/v1/GetList', {})

    def number_get_free(self, type_id: int, region_id: int | None = None,
                        category_id: int | None = None, mask: str = '', limit: int = 20) -> dict:
        """GetFree — список свободных для покупки номеров."""
        payload: dict = {'type_id': int(type_id), 'limit': int(limit)}
        if region_id:
            payload['region_id'] = int(region_id)
        if category_id:
            payload['category_id'] = int(category_id)
        if mask:
            payload['mask'] = str(mask)
        return self._post('/number/v1/GetFree', payload)

    def number_lock(self, number_code: int | str, seconds: int = 300) -> dict:
        """Lock — бронь номера перед покупкой (60–600 c). Возвращает {'Id': ...}."""
        return self._post('/number/v1/Lock', {'number_code': int(number_code), 'seconds': int(seconds)})

    def number_buy(self, number_code: int | str, reserve_uid: int | str,
                  call_record: bool = True) -> dict:
        """Buy — покупка забронированного номера."""
        return self._post('/number/v1/Buy', {
            'number_code': int(number_code),
            'reserve_uid': int(reserve_uid),
            'call_transcribation': False,
            'speech_analytics': False,
        })

    def number_set_forwarding_ipcr(self, number_code: int | str, url: str, reserve: str = '') -> dict:
        """SetCallForwarding type=3 (IPCR) — динамическая переадресация на наш URL."""
        ipcr: dict = {'url': url}
        if reserve:
            ipcr['reserve'] = str(reserve)
        return self._post('/number/v1/SetCallForwarding', {
            'number_code': int(number_code),
            'call_forwarding_type': 3,
            'call_forwarding_ipcr': ipcr,
        })

    def number_set_forwarding_to_sip(self, number_code: int | str, sip_username: str,
                                     event_url: str = '', timeout: int = 30,
                                     masking: bool = False) -> dict:
        """SetCallForwarding type=2 (call_forwarding_number) — статическая
        переадресация номера на SIP ID менеджера, с URL уведомлений о событиях.

        Используется, когда номер занят как CLI SIP-аккаунта и IPCR (type=3)
        недоступен (Exolve отвечает "number has sip"). Контракт: один номер →
        ринг SIP менеджера + события вызова приходят на event_url.
        """
        forwarding: dict = {
            'redirect_type': 1,
            'call_control': [{
                'redirect_number': str(sip_username),
                'timeout': int(timeout),
                'active': True,
                'name': 'CRM',
            }],
            'masking': bool(masking),
        }
        if event_url:
            forwarding['event_url'] = event_url
        return self._post('/number/v1/SetCallForwarding', {
            'number_code': int(number_code),
            'call_forwarding_type': 2,
            'call_forwarding_number': forwarding,
        })

    def number_delete_forwarding(self, number_code: int | str) -> dict:
        return self._post('/number/v1/DeleteCallForwarding', {'number_code': int(number_code)})

    # ------------------------------------------------------------------
    # SIP API
    # ------------------------------------------------------------------
    def sip_create(self, sip_name: str, number: int | str, call_record: bool = True) -> dict:
        """Create — создание SIP ID. Возвращает {'sip_resource_id', 'username'}."""
        return self._post('/sip/v1/Create', {
            'sip_name': str(sip_name),
            'number': int(number),
            'call_record': bool(call_record),
        })

    def sip_get_attributes(self, sip_resource_id: int | str) -> dict:
        """GetAttributes — настройки SIP ID, включая login/password/domain/cli."""
        return self._post('/sip/v1/GetAttributes', {'sip_resource_id': str(sip_resource_id)})

    def sip_set_display_number(self, sip_resource_id: int | str, number: int | str) -> dict:
        """SetDisplayNumber — исходящий CLI для SIP ID."""
        return self._post('/sip/v1/SetDisplayNumber', {
            'sip_resource_id': int(sip_resource_id),
            'number': int(number),
        })

    def sip_delete(self, sip_resource_id: int | str) -> dict:
        return self._post('/sip/v1/Delete', {'sip_resource_id': str(sip_resource_id)})

    # ------------------------------------------------------------------
    # Запись разговора
    # ------------------------------------------------------------------
    def download_record(self, url: str) -> bytes:
        """Скачивание файла записи по path из Call Events (crr.path)."""
        if not self.api_key:
            raise ExolveError('EXOLVE_API_KEY не задан')
        try:
            resp = requests.get(url, headers={'Authorization': f'Bearer {self.api_key}'}, timeout=60)
        except requests.RequestException as exc:
            raise ExolveError(f'Не удалось скачать запись: {exc}') from exc
        if resp.status_code >= 400:
            raise ExolveError(f'Запись недоступна: {resp.status_code}', status=resp.status_code)
        return resp.content

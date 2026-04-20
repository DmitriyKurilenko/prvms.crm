from __future__ import annotations

import base64
import logging
from dataclasses import asdict

import requests

from .adapters import CRMUser, LeadData

logger = logging.getLogger(__name__)


class AmoCRMAdapter:
    """
    Practical amoCRM adapter with graceful fallbacks.

    The adapter supports live HTTP calls when credentials contain
    `base_url`/`subdomain` + `access_token`, and still works in local/stub mode
    through `mock_users` / `mock_entities`.
    """

    def __init__(self, credentials: dict):
        self.credentials = credentials or {}
        self.timeout = int(self.credentials.get('timeout', 10))

    def get_lead(self, lead_id: str) -> LeadData:
        payload = self._mock_entity('lead', lead_id) or self._request('GET', f'/api/v4/leads/{lead_id}')
        return self._lead_from_payload(payload or {'id': lead_id, 'name': f'Lead {lead_id}'})

    def get_deal(self, deal_id: str) -> LeadData:
        payload = self._mock_entity('deal', deal_id) or self._request('GET', f'/api/v4/leads/{deal_id}')
        return self._lead_from_payload(payload or {'id': deal_id, 'name': f'Deal {deal_id}'})

    def get_contact(self, contact_id: str) -> dict:
        return self._mock_entity('contact', contact_id) or self._request('GET', f'/api/v4/contacts/{contact_id}') or {'id': contact_id}

    def update_lead(self, lead_id: str, fields: dict) -> None:
        if self._has_http_credentials():
            self._request('PATCH', f'/api/v4/leads/{lead_id}', json_data=fields or {})

    def upload_file(self, entity_type: str, entity_id: str, file: bytes, filename: str) -> str:
        if not self._has_http_credentials():
            return ''
        base_url = self._base_url()
        token = self._token()
        url = f'{base_url}/api/v4/{entity_type}s/{entity_id}/files'
        resp = requests.post(
            url,
            headers={'Authorization': f'Bearer {token}'},
            files={'file': (filename, file)},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data.get('id', data.get('_embedded', {}).get('files', [{}])[0].get('id', '')))

    def list_users(self) -> list[CRMUser]:
        mock_users = self.credentials.get('mock_users')
        if isinstance(mock_users, list):
            return [self._user_from_payload(item) for item in mock_users]

        if not self._has_http_credentials():
            return []

        response = self._request('GET', '/api/v4/users')
        items = (response or {}).get('_embedded', {}).get('users', [])
        return [self._user_from_payload(item) for item in items]

    def set_responsible(self, entity_type: str, entity_id: str, user_id: str) -> None:
        if not self._has_http_credentials():
            return
        payload = {'responsible_user_id': int(user_id)}
        self._request('PATCH', f'/api/v4/{entity_type}/{entity_id}', json_data=payload)

    def register_chat_channel(self, channel_id: str, channel_name: str, webhook_url: str) -> str:
        if not self._has_http_credentials():
            return ''
        amojo_id = self.credentials.get('amojo_id', '')
        if not amojo_id:
            logger.warning('amoCRM amojo_id not configured, cannot register chat channel')
            return ''
        base_url = self._base_url()
        token = self._token()
        resp = requests.post(
            f'{base_url}/api/v2/chats/channels',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={
                'name': channel_name,
                'hook_api_version': 'v2',
                'is_2way': True,
                'origin': channel_id,
                'description': f'Channel {channel_name}',
                'outgoing_messages': {'url': webhook_url} if webhook_url else {},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data.get('id', data.get('scope_id', '')))

    def send_message_to_crm(self, scope_id: str, chat_id: str, sender: dict, text: str, attachments: list = None) -> str:
        if not self._has_http_credentials():
            return ''
        amojo_id = self.credentials.get('amojo_id', '')
        if not amojo_id:
            return ''
        import uuid as _uuid
        msg_id = str(_uuid.uuid4())
        base_url = self._base_url()
        token = self._token()
        payload = {
            'conversation_id': chat_id,
            'sender': {'id': sender.get('id', scope_id), 'name': sender.get('name', 'Client')},
            'message': {'type': 'text', 'text': text},
            'msgid': msg_id,
        }
        resp = requests.post(
            f'{base_url}/api/v2/chats/messages',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return msg_id

    def receive_outgoing_message(self, payload: dict) -> dict:
        if not payload:
            return {}
        message = payload.get('message', {})
        return {
            'text': message.get('text', ''),
            'chat_id': payload.get('conversation_id', ''),
            'sender': payload.get('receiver', {}),
            'attachments': message.get('media', []) if isinstance(message.get('media'), list) else [],
        }

    def register_call(self, call_data: dict) -> str:
        if not self._has_http_credentials():
            return ''
        payload = {
            'direction': call_data.get('direction', 'inbound'),
            'uniq': call_data.get('uuid', ''),
            'duration': call_data.get('duration', 0),
            'source': 'prvms',
            'phone': call_data.get('caller_number', call_data.get('called_number', '')),
            'call_result': call_data.get('result', ''),
            'responsible_user_id': int(call_data['responsible_user_id']) if call_data.get('responsible_user_id') else None,
            'created_at': call_data.get('started_at_ts'),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        resp = self._request('POST', '/api/v4/calls', json_data=[payload])
        if resp and isinstance(resp, dict):
            calls = resp.get('_embedded', {}).get('calls', [])
            if calls:
                return str(calls[0].get('id', ''))
        return ''

    def attach_call_record(self, call_id: str, record_url: str) -> None:
        if not self._has_http_credentials() or not call_id:
            return
        self._request('PATCH', f'/api/v4/calls/{call_id}', json_data={'link': record_url})

    def _base_url(self) -> str | None:
        direct = str(self.credentials.get('base_url', '')).strip()
        if direct:
            return direct.rstrip('/')
        subdomain = str(self.credentials.get('subdomain', '')).strip()
        if subdomain:
            return f'https://{subdomain}.amocrm.ru'
        return None

    def _token(self) -> str | None:
        token = str(self.credentials.get('access_token', '')).strip()
        return token or None

    def _has_http_credentials(self) -> bool:
        return bool(self._base_url() and self._token())

    def _request(self, method: str, path: str, json_data: dict | None = None):
        base_url = self._base_url()
        token = self._token()
        if not base_url or not token:
            return None
        url = f'{base_url}{path}'
        response = requests.request(
            method=method,
            url=url,
            headers={'Authorization': f'Bearer {token}'},
            json=json_data,
            timeout=self.timeout,
        )
        response.raise_for_status()
        if not response.text:
            return {}
        return response.json()

    def _mock_entity(self, entity_type: str, entity_id: str) -> dict | None:
        entities = self.credentials.get('mock_entities') or {}
        if not isinstance(entities, dict):
            return None
        bucket = entities.get(entity_type, {})
        if not isinstance(bucket, dict):
            return None
        return bucket.get(str(entity_id))

    @staticmethod
    def _user_from_payload(payload: dict) -> CRMUser:
        return CRMUser(
            id=str(payload.get('id', '')),
            name=str(payload.get('name', 'Unknown')),
            email=payload.get('email'),
            is_active=not bool(payload.get('is_active') is False or payload.get('active') is False),
        )

    @staticmethod
    def _lead_from_payload(payload: dict) -> LeadData:
        contacts = payload.get('contacts') or payload.get('_embedded', {}).get('contacts') or []
        return LeadData(
            id=str(payload.get('id', '')),
            name=str(payload.get('name', '')),
            price=payload.get('price'),
            responsible_user_id=str(payload.get('responsible_user_id')) if payload.get('responsible_user_id') is not None else None,
            contacts=[item if isinstance(item, dict) else asdict(item) for item in contacts],
            custom_fields=payload.get('custom_fields_values') or payload.get('custom_fields') or {},
            created_at=str(payload.get('created_at', '')),
            updated_at=str(payload.get('updated_at', '')),
        )

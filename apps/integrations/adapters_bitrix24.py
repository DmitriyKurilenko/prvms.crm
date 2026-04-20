from __future__ import annotations

import base64
import logging
from dataclasses import asdict

import requests

from .adapters import CRMUser, LeadData

logger = logging.getLogger(__name__)


class Bitrix24Adapter:
    """
    Bitrix24 adapter with webhook mode support and deterministic fallbacks.

    Supported credentials:
    - webhook_url: full REST webhook base URL
    - base_url + access_token (+ user_id optional): OAuth-based REST URL composition
    - mock_users / mock_entities for offline development
    """

    def __init__(self, credentials: dict):
        self.credentials = credentials or {}
        self.timeout = int(self.credentials.get('timeout', 10))

    def get_lead(self, lead_id: str) -> LeadData:
        payload = self._mock_entity('lead', lead_id) or self._call('crm.lead.get', {'id': lead_id}) or {}
        result = payload.get('result', payload)
        return self._lead_from_payload(result or {'ID': lead_id, 'TITLE': f'Lead {lead_id}'})

    def get_deal(self, deal_id: str) -> LeadData:
        payload = self._mock_entity('deal', deal_id) or self._call('crm.deal.get', {'id': deal_id}) or {}
        result = payload.get('result', payload)
        return self._lead_from_payload(result or {'ID': deal_id, 'TITLE': f'Deal {deal_id}'})

    def get_contact(self, contact_id: str) -> dict:
        payload = self._mock_entity('contact', contact_id) or self._call('crm.contact.get', {'id': contact_id}) or {}
        return payload.get('result', payload) or {'ID': contact_id}

    def update_lead(self, lead_id: str, fields: dict) -> None:
        if not self._can_call():
            return
        self._call('crm.lead.update', {'id': lead_id, 'fields': fields or {}})

    def upload_file(self, entity_type: str, entity_id: str, file: bytes, filename: str) -> str:
        if not self._can_call():
            return ''
        b64 = base64.b64encode(file).decode('ascii')
        result = self._call('disk.folder.uploadfile', {
            'id': 0,
            'data': {'NAME': filename},
            'fileContent': [filename, b64],
        }) or {}
        file_id = result.get('result', {}).get('ID', '')
        return str(file_id)

    def list_users(self) -> list[CRMUser]:
        mock_users = self.credentials.get('mock_users')
        if isinstance(mock_users, list):
            return [self._user_from_payload(item) for item in mock_users]
        if not self._can_call():
            return []
        payload = self._call('user.get', {}) or {}
        users = payload.get('result', [])
        return [self._user_from_payload(item) for item in users]

    def set_responsible(self, entity_type: str, entity_id: str, user_id: str) -> None:
        if not self._can_call():
            return
        method = {
            'lead': 'crm.lead.update',
            'deal': 'crm.deal.update',
            'contact': 'crm.contact.update',
        }.get(entity_type, 'crm.deal.update')
        self._call(method, {'id': entity_id, 'fields': {'ASSIGNED_BY_ID': user_id}})

    def register_chat_channel(self, channel_id: str, channel_name: str, webhook_url: str) -> str:
        if not self._can_call():
            return ''
        result = self._call('imconnector.register', {
            'ID': channel_id,
            'NAME': channel_name,
            'ICON': {},
            'PLACEMENT_HANDLER': webhook_url,
        }) or {}
        connector_id = result.get('result', '')
        return str(connector_id) if connector_id else channel_id

    def send_message_to_crm(self, scope_id: str, chat_id: str, sender: dict, text: str, attachments: list = None) -> str:
        if not self._can_call():
            return ''
        messages = [{
            'user': {
                'id': sender.get('id', scope_id),
                'name': sender.get('name', 'Client'),
            },
            'message': {'text': text},
            'chat': {'id': chat_id},
        }]
        result = self._call('imconnector.send.messages', {
            'CONNECTOR': 'prvms',
            'LINE': chat_id,
            'MESSAGES': messages,
        }) or {}
        msg_result = result.get('result', {})
        return str(msg_result.get('MESSAGES', [{}])[0].get('id', '')) if isinstance(msg_result, dict) else ''

    def receive_outgoing_message(self, payload: dict) -> dict:
        if not payload:
            return {}
        data = payload.get('data', payload)
        messages = data.get('MESSAGES', [data]) if isinstance(data, dict) else [data]
        if not messages:
            return {}
        msg = messages[0] if isinstance(messages, list) else messages
        return {
            'text': msg.get('message', {}).get('text', '') if isinstance(msg.get('message'), dict) else str(msg.get('message', '')),
            'chat_id': str(msg.get('chat', {}).get('id', '')) if isinstance(msg.get('chat'), dict) else '',
            'sender': msg.get('user', {}),
            'attachments': msg.get('files', []),
        }

    def register_call(self, call_data: dict) -> str:
        if not self._can_call():
            return ''
        result = self._call('telephony.externalcall.register', {
            'USER_PHONE_INNER': call_data.get('extension', ''),
            'USER_ID': call_data.get('responsible_user_id', ''),
            'PHONE_NUMBER': call_data.get('caller_number', call_data.get('called_number', '')),
            'TYPE': '1' if call_data.get('direction') == 'outbound' else '2',
            'CALL_START_DATE': call_data.get('started_at', ''),
            'CRM_CREATE': '0',
        }) or {}
        call_id = result.get('result', {}).get('CALL_ID', '')
        return str(call_id)

    def attach_call_record(self, call_id: str, record_url: str) -> None:
        if not self._can_call() or not call_id:
            return
        self._call('telephony.externalcall.attachRecord', {
            'CALL_ID': call_id,
            'FILENAME': f'record_{call_id}.wav',
            'FILE_URL': record_url,
        })

    def _can_call(self) -> bool:
        return bool(self._rest_url())

    def _rest_url(self) -> str | None:
        webhook_url = str(self.credentials.get('webhook_url', '')).strip()
        if webhook_url:
            return webhook_url.rstrip('/')
        base_url = str(self.credentials.get('base_url', '')).strip().rstrip('/')
        token = str(self.credentials.get('access_token', '')).strip()
        user_id = str(self.credentials.get('user_id', '1')).strip()
        if base_url and token:
            return f'{base_url}/rest/{user_id}/{token}'
        return None

    def _call(self, method: str, params: dict):
        rest_url = self._rest_url()
        if not rest_url:
            return None
        response = requests.post(
            f'{rest_url}/{method}.json',
            json=params,
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
        name = payload.get('NAME') or payload.get('name') or ''
        last_name = payload.get('LAST_NAME') or payload.get('last_name') or ''
        full_name = f'{name} {last_name}'.strip() or 'Unknown'
        return CRMUser(
            id=str(payload.get('ID', payload.get('id', ''))),
            name=full_name,
            email=payload.get('EMAIL') or payload.get('email'),
            is_active=str(payload.get('ACTIVE', payload.get('active', 'Y'))).upper() in {'Y', 'TRUE', '1'},
        )

    @staticmethod
    def _lead_from_payload(payload: dict) -> LeadData:
        contacts = payload.get('CONTACT_IDS') or payload.get('contacts') or []
        contacts_as_dict = []
        for item in contacts:
            if isinstance(item, dict):
                contacts_as_dict.append(item)
            else:
                contacts_as_dict.append({'id': str(item)})
        if hasattr(payload, '__dataclass_fields__'):
            payload = asdict(payload)
        return LeadData(
            id=str(payload.get('ID', payload.get('id', ''))),
            name=str(payload.get('TITLE', payload.get('name', ''))),
            price=int(payload.get('OPPORTUNITY') or payload.get('price') or 0) or None,
            responsible_user_id=str(payload.get('ASSIGNED_BY_ID', payload.get('responsible_user_id'))) if payload.get('ASSIGNED_BY_ID', payload.get('responsible_user_id')) is not None else None,
            contacts=contacts_as_dict,
            custom_fields=payload.get('UF_CRM_FIELDS') or payload.get('custom_fields') or {},
            created_at=str(payload.get('DATE_CREATE', payload.get('created_at', ''))),
            updated_at=str(payload.get('DATE_MODIFY', payload.get('updated_at', ''))),
        )

from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class LeadData:
    id: str
    name: str
    price: int | None
    responsible_user_id: str | None
    contacts: list[dict]
    custom_fields: dict
    created_at: str
    updated_at: str


@dataclass
class CRMUser:
    id: str
    name: str
    email: str | None
    is_active: bool


@runtime_checkable
class CRMAdapter(Protocol):
    """Единый интерфейс для работы с любой CRM."""

    def get_lead(self, lead_id: str) -> LeadData: ...
    def get_deal(self, deal_id: str) -> LeadData: ...
    def get_contact(self, contact_id: str) -> dict: ...
    def update_lead(self, lead_id: str, fields: dict) -> None: ...
    def upload_file(self, entity_type: str, entity_id: str, file: bytes, filename: str) -> str: ...
    def list_users(self) -> list[CRMUser]: ...
    def set_responsible(self, entity_type: str, entity_id: str, user_id: str) -> None: ...
    def register_chat_channel(self, channel_id: str, channel_name: str, webhook_url: str) -> str: ...
    def send_message_to_crm(self, scope_id: str, chat_id: str, sender: dict, text: str, attachments: list = None) -> str: ...
    def receive_outgoing_message(self, payload: dict) -> dict: ...
    def register_call(self, call_data: dict) -> str: ...
    def attach_call_record(self, call_id: str, record_url: str) -> None: ...


def get_adapter(connection) -> CRMAdapter:
    from apps.integrations.adapters_amocrm import AmoCRMAdapter
    from apps.integrations.adapters_bitrix24 import Bitrix24Adapter

    adapters = {
        'amocrm': AmoCRMAdapter,
        'bitrix24': Bitrix24Adapter,
    }
    cls = adapters[connection.crm_type]
    return cls(connection.credentials)


def get_adapter_for_tenant(tenant) -> CRMAdapter:
    """Получить адаптер с учётом crm_mode тенанта."""
    if tenant.crm_mode == 'builtin':
        from apps.crm.adapter import BuiltinCRMAdapter
        return BuiltinCRMAdapter()
    from apps.integrations.models import CRMConnection
    connection = CRMConnection.objects.filter(
        crm_type=tenant.crm_mode, is_active=True
    ).first()
    if not connection:
        raise ValueError(f'No active {tenant.crm_mode} connection')
    return get_adapter(connection)

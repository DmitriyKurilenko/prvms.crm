from dataclasses import dataclass

from django.core.files.base import ContentFile

from .models import Activity, Contact, Deal


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


class BuiltinCRMAdapter:
    """CRM-адаптер для встроенного CRM. Работает напрямую с ORM."""

    def get_lead(self, lead_id: str) -> LeadData:
        deal = Deal.objects.select_related('contact', 'company').get(id=lead_id)
        contacts = []
        if deal.contact:
            contacts.append({
                'id': str(deal.contact.id),
                'name': str(deal.contact),
                'phone': deal.contact.phone,
                'email': deal.contact.email,
            })
        return LeadData(
            id=str(deal.id),
            name=deal.name,
            price=int(deal.amount) if deal.amount else None,
            responsible_user_id=str(deal.responsible_id) if deal.responsible else None,
            contacts=contacts,
            custom_fields=deal.custom_fields,
            created_at=deal.created_at.isoformat(),
            updated_at=deal.updated_at.isoformat(),
        )

    def get_deal(self, deal_id: str) -> LeadData:
        return self.get_lead(deal_id)

    def get_contact(self, contact_id: str) -> dict:
        c = Contact.objects.get(id=contact_id)
        return {
            'id': str(c.id),
            'name': str(c),
            'phone': c.phone,
            'email': c.email,
        }

    def update_lead(self, lead_id: str, fields: dict) -> None:
        Deal.objects.filter(id=lead_id).update(**fields)

    def upload_file(self, entity_type: str, entity_id: str, file: bytes, filename: str) -> str:
        activity = Activity.objects.create(
            activity_type='note',
            **({'deal_id': entity_id} if entity_type in ('lead', 'deal') else {'contact_id': entity_id}),
            title=f'Загружен файл: {filename}',
        )
        # Save file via Activity - use a custom approach with Django ContentFile
        from django.core.files.storage import default_storage
        path = default_storage.save(f'crm/files/{entity_type}_{entity_id}/{filename}', ContentFile(file))
        activity.body = default_storage.url(path)
        activity.save(update_fields=['body'])
        return default_storage.url(path)

    def list_users(self):
        from django.db import connection

        from apps.users.models import Membership
        members = Membership.objects.filter(
            tenant=connection.tenant, is_active=True,
        ).exclude(role='viewer').select_related('user')
        return [
            CRMUser(
                id=str(m.user_id),
                name=m.user.get_full_name() or m.user.email,
                email=m.user.email,
                is_active=True,
            )
            for m in members
        ]

    def set_responsible(self, entity_type, entity_id, user_id):
        model = Deal if entity_type in ('lead', 'deal') else Contact
        model.objects.filter(id=entity_id).update(responsible_id=user_id)

    def register_chat_channel(self, channel_id, channel_name, webhook_url):
        activity = Activity.objects.create(
            activity_type='system',
            title=f'Мессенджер-канал подключён: {channel_name}',
            body=f'channel_id={channel_id}',
        )
        return str(activity.id)

    def send_message_to_crm(self, scope_id, chat_id, sender, text, attachments=None):
        activity = Activity.objects.create(
            activity_type='message',
            contact_id=scope_id,
            title=f'Сообщение от {sender["name"]}',
            body=text,
        )
        return str(activity.id)

    def receive_outgoing_message(self, payload):
        if not payload:
            return {}
        return {
            'text': payload.get('text', ''),
            'chat_id': payload.get('chat_id', ''),
            'sender': payload.get('sender', {}),
            'attachments': payload.get('attachments', []),
        }

    def register_call(self, call_data):
        activity = Activity.objects.create(
            activity_type='call',
            deal_id=call_data.get('deal_id'),
            contact_id=call_data.get('contact_id'),
            title=call_data.get('title', 'Звонок'),
            related_call_id=call_data.get('call_record_id'),
        )
        return str(activity.id)

    def attach_call_record(self, call_id, record_url):
        Activity.objects.filter(
            related_call_id=call_id,
        ).update(body=record_url)
        # Also update any activities without direct call FK that reference this call
        Activity.objects.filter(
            activity_type='call',
            related_call_id=call_id,
            body='',
        ).update(body=f'Запись звонка: {record_url}')


def get_crm_adapter() -> BuiltinCRMAdapter:
    """Единственный CRM-адаптер продукта — встроенный CRM.

    Раньше выбор адаптера зависел от внешней CRM (`crm_mode`); после удаления
    внешних интеграций остался только встроенный, поэтому диспетчеризации нет.
    """
    return BuiltinCRMAdapter()

"""Поиск дублей и слияние контактов/компаний.

Слияние необратимо: связанные сделки/активности переносятся на основную
запись, пустые поля основной записи заполняются из дублей, дубли удаляются.
Транзакция атомарна; вызывающий слой пишет операцию в аудит через `log_event`.
"""
from __future__ import annotations

from collections import defaultdict

from django.db import transaction

from apps.crm.models import Activity, Company, Contact, Deal

# Поля основной записи, которые дозаполняются из дублей, если пусты.
_CONTACT_FILL_FIELDS = ('phone', 'email', 'position', 'messenger_id', 'source', 'company_id')
_COMPANY_FILL_FIELDS = ('inn', 'phone', 'email', 'address', 'website')


def _normalize_ids(primary_id: int, merged_ids: list[int]) -> list[int]:
    """Исключает primary из списка дублей и убирает повторы, сохраняя детерминизм."""
    seen: list[int] = []
    for mid in merged_ids:
        if mid != primary_id and mid not in seen:
            seen.append(mid)
    return seen


def find_duplicate_contacts() -> list[dict]:
    """Группы контактов-дублей по непустому телефону или email."""
    by_phone: dict[str, list[Contact]] = defaultdict(list)
    by_email: dict[str, list[Contact]] = defaultdict(list)
    for c in Contact.objects.all().only('id', 'first_name', 'last_name', 'phone', 'email'):
        if c.phone:
            by_phone[c.phone.strip()].append(c)
        if c.email:
            by_email[c.email.strip().lower()].append(c)
    groups: list[dict] = []
    _append_groups(groups, 'phone', by_phone, _contact_label)
    _append_groups(groups, 'email', by_email, _contact_label)
    return groups


def find_duplicate_companies() -> list[dict]:
    """Группы компаний-дублей по непустому ИНН или совпадению названия."""
    by_inn: dict[str, list[Company]] = defaultdict(list)
    by_name: dict[str, list[Company]] = defaultdict(list)
    for c in Company.objects.all().only('id', 'name', 'inn'):
        if c.inn:
            by_inn[c.inn.strip()].append(c)
        if c.name:
            by_name[c.name.strip().lower()].append(c)
    groups: list[dict] = []
    _append_groups(groups, 'inn', by_inn, _company_label)
    _append_groups(groups, 'name', by_name, _company_label)
    return groups


def _append_groups(groups, key_type, buckets, label_fn):
    for key, items in buckets.items():
        if len(items) > 1:
            groups.append({
                'key_type': key_type,
                'key': key,
                'items': [{'id': obj.id, 'label': label_fn(obj)} for obj in items],
            })


def _contact_label(c: Contact) -> str:
    name = f'{c.first_name} {c.last_name}'.strip()
    extra = c.phone or c.email or ''
    return f'{name} ({extra})' if extra else name


def _company_label(c: Company) -> str:
    return f'{c.name} (ИНН {c.inn})' if c.inn else c.name


@transaction.atomic
def merge_contacts(primary_id: int, merged_ids: list[int]) -> dict:
    merged_ids = _normalize_ids(primary_id, merged_ids)
    if not merged_ids:
        return {'primary_id': primary_id, 'moved_deals': 0, 'moved_activities': 0, 'merged': 0}
    primary = Contact.objects.get(id=primary_id)
    moved_deals = Deal.objects.filter(contact_id__in=merged_ids).update(contact=primary)
    moved_acts = Activity.objects.filter(contact_id__in=merged_ids).update(contact=primary)
    for dup in Contact.objects.filter(id__in=merged_ids):
        for field in _CONTACT_FILL_FIELDS:
            if not getattr(primary, field) and getattr(dup, field):
                setattr(primary, field, getattr(dup, field))
    primary.save()
    deleted = Contact.objects.filter(id__in=merged_ids).delete()[0]
    return {
        'primary_id': primary_id,
        'moved_deals': moved_deals,
        'moved_activities': moved_acts,
        'merged': deleted,
    }


@transaction.atomic
def merge_companies(primary_id: int, merged_ids: list[int]) -> dict:
    merged_ids = _normalize_ids(primary_id, merged_ids)
    if not merged_ids:
        return {'primary_id': primary_id, 'moved_contacts': 0, 'moved_deals': 0, 'merged': 0}
    primary = Company.objects.get(id=primary_id)
    moved_contacts = Contact.objects.filter(company_id__in=merged_ids).update(company=primary)
    moved_deals = Deal.objects.filter(company_id__in=merged_ids).update(company=primary)
    for dup in Company.objects.filter(id__in=merged_ids):
        for field in _COMPANY_FILL_FIELDS:
            if not getattr(primary, field) and getattr(dup, field):
                setattr(primary, field, getattr(dup, field))
    primary.save()
    deleted = Company.objects.filter(id__in=merged_ids).delete()[0]
    return {
        'primary_id': primary_id,
        'moved_contacts': moved_contacts,
        'moved_deals': moved_deals,
        'merged': deleted,
    }

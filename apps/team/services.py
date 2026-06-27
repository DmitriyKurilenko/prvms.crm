"""Сервисы домена «команда»."""
from __future__ import annotations


def ensure_team_members() -> None:
    """Синхронизирует `team.Manager` из активных Membership текущего тенанта.

    Создаёт недостающие профили, обновляет имя, деактивирует профили выбывших
    участников. Наблюдатели (`viewer`) менеджерами не становятся.
    """
    from django.db import connection as db_connection

    from apps.users.models import Membership

    from .models import Manager

    tenant = db_connection.tenant
    memberships = (
        Membership.objects.filter(tenant=tenant, is_active=True)
        .exclude(role='viewer')
        .select_related('user')
    )
    active_user_ids = set()
    for m in memberships:
        active_user_ids.add(m.user_id)
        name = m.user.get_full_name() or m.user.email
        Manager.objects.update_or_create(
            user=m.user,
            defaults={'display_name': name, 'is_active': True},
        )
    if active_user_ids:
        Manager.objects.exclude(user_id__in=active_user_ids).update(is_active=False)

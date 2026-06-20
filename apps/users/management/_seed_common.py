"""Общие помощники для seed-management-команд.

Команды `create_test_users` и `seed_demo_users` решают разные задачи
(параметризованный QA-bootstrap против простого демо-сидера) и не объединяются
в одну. Но приведение существующего Membership к каноническому «joined»-состоянию
дублировалось в них дословно трижды — эта логика вынесена сюда.
"""
from __future__ import annotations

from django.utils import timezone


def reconcile_membership(membership, role: str, *, now=None) -> list[str]:
    """Привести существующий Membership к каноническому seed-состоянию.

    Возвращает список изменённых полей (пустой, если объект уже канонический),
    чтобы вызывающая команда могла построить свою отчётность.
    """
    now = now or timezone.now()
    updates: list[str] = []
    if membership.role != role:
        membership.role = role
        updates.append('role')
    if not membership.is_active:
        membership.is_active = True
        updates.append('is_active')
    if membership.joined_at is None:
        membership.joined_at = now
        updates.append('joined_at')
    if membership.invite_token is not None:
        membership.invite_token = None
        updates.append('invite_token')
    if membership.invited_at is not None:
        membership.invited_at = None
        updates.append('invited_at')
    if updates:
        membership.save(update_fields=updates)
    return updates

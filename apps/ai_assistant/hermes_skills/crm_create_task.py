#!/usr/bin/env python3
"""
Hermes Skill: CRM Create Task
Creates a task in the CRM for the current tenant.
Usage in Hermes: "Создай задачу" or "Напомни про..."

This script should be placed in:
  ~/.hermes/profiles/{tenant_slug}/skills/crm_create_task.py
"""

import json
import logging
import os
import sys

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django_tenants.utils import schema_context

from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


def handle(args: dict) -> dict:
    """
    Handle the skill invocation.
    Expected args: {
        "tenant_slug": "mycompany",
        "title": "Проверить сделку",
        "body": "Проверить статус оплаты",
        "deal_id": "123",  (optional)
        "user_id": "456",  (optional, defaults to responsible)
    }
    """
    tenant_slug = args.get('tenant_slug', '')
    title = args.get('title', '')
    body = args.get('body', '')
    deal_id = args.get('deal_id')
    user_id = args.get('user_id')

    if not tenant_slug:
        return {'error': 'tenant_slug is required'}

    if not title:
        return {'error': 'title is required'}

    try:
        with schema_context('public'):
            tenant = Tenant.objects.filter(slug=tenant_slug).first()
            if not tenant:
                return {'error': f'Tenant not found: {tenant_slug}'}

        with schema_context(tenant.schema_name):
            from django.utils import timezone

            from apps.crm.models import Activity, Deal
            from apps.users.models import User

            task_data = {
                'activity_type': 'task',
                'title': title,
                'body': body or '',
                'status': 'planned',
                'created_at': timezone.now(),
            }

            if deal_id:
                try:
                    deal = Deal.objects.get(id=deal_id)
                    task_data['deal'] = deal
                except Deal.DoesNotExist:
                    pass

            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    task_data['responsible'] = user
                except User.DoesNotExist:
                    pass

            activity = Activity.objects.create(**task_data)

            return {
                'success': True,
                'task_id': activity.id,
                'title': activity.title,
                'status': activity.status,
            }

    except Exception as e:  # noqa: BLE001 — граница skill→Hermes: ошибка возвращается агенту структурно
        logger.exception('crm_create_task skill failed for tenant=%s', tenant_slug)
        return {'error': str(e)}


if __name__ == '__main__':
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    result = handle(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
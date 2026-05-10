#!/usr/bin/env python3
"""
Hermes Skill: CRM Get Deal
Returns deal information from the CRM for the current tenant.
Usage in Hermes: "Найди сделку {deal_id}" or "Что по сделке {deal_id}"

This script should be placed in:
  ~/.hermes/profiles/{tenant_slug}/skills/crm_get_deal.py

The skill will be auto-discovered by Hermes.
"""

import json
import os
import sys

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django_tenants.utils import schema_context
from apps.tenants.models import Tenant


def handle(args: dict) -> dict:
    """
    Handle the skill invocation.
    Expected args: {"deal_id": "123", "tenant_slug": "mycompany"}
    """
    deal_id = args.get('deal_id', '')
    tenant_slug = args.get('tenant_slug', '')

    if not tenant_slug:
        return {'error': 'tenant_slug is required'}

    if not deal_id:
        return {'error': 'deal_id is required'}

    try:
        with schema_context('public'):
            tenant = Tenant.objects.filter(slug=tenant_slug).first()
            if not tenant:
                return {'error': f'Tenant not found: {tenant_slug}'}

        with schema_context(tenant.schema_name):
            from apps.crm.models import Deal, Stage, Pipeline

            try:
                deal = Deal.objects.select_related('stage', 'pipeline', 'contact', 'company', 'responsible').get(id=deal_id)
            except Deal.DoesNotExist:
                return {'error': f'Deal not found: {deal_id}'}

            result = {
                'id': deal.id,
                'name': deal.name,
                'stage': deal.stage.name if deal.stage else None,
                'pipeline': deal.pipeline.name if deal.pipeline else None,
                'amount': str(deal.amount) if deal.amount else None,
                'currency': deal.currency,
                'responsible': deal.responsible.get_full_name() if deal.responsible else None,
                'contact': deal.contact.get_full_name() if deal.contact else None,
                'company': deal.company.name if deal.company else None,
                'expected_close_date': str(deal.expected_close_date) if deal.expected_close_date else None,
                'status': deal.stage.stage_type if deal.stage else None,
            }
            return result

    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    import sys
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    result = handle(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
"""System document templates seeding.

Called during tenant provisioning and data migrations. Keeps template
content close to the models it operates on.
"""
from __future__ import annotations

from django_tenants.utils import schema_context

from apps.tenants.models import Tenant

from .models import DocumentTemplate, DocumentType

COMMON_SCHEMA = [
    {'key': 'deal_id', 'sample': '42'},
    {'key': 'deal_name', 'sample': 'Тестовая сделка'},
    {'key': 'amount', 'sample': '100 000'},
    {'key': 'currency', 'sample': 'RUB'},
    {'key': 'contact_name', 'sample': 'Иванов И.И.'},
    {'key': 'company_name', 'sample': 'ООО «Пример»'},
    {'key': 'created_at', 'sample': '2026-01-01T00:00:00'},
]


SYSTEM_TEMPLATES = [
    {
        'name': 'Договор купли-продажи',
        'document_type': DocumentType.CONTRACT,
        'html_body': '<h1 style="text-align:center">Договор купли-продажи № {{ deal_id }}</h1>\n<p>г. ________________ &laquo;___&raquo; ____________ 20__ г.</p>\n<p><strong>Продавец:</strong> {{ company_name }}, в лице ________________, действующего на основании ________________,</p>\n<p><strong>Покупатель:</strong> {{ contact_name }},</p>\n<p>заключили настоящий Договор о нижеследующем:</p>\n<h2>1. Предмет договора</h2>\n<p>1.1. Продавец обязуется передать в собственность Покупателю, а Покупатель — принять и оплатить товар.</p>\n<p>1.2. Наименование сделки: {{ deal_name }}.</p>\n<h2>2. Цена и порядок расчётов</h2>\n<p>2.1. Стоимость товара составляет {{ amount }} {{ currency }}.</p>\n<p>2.2. Оплата производится в течение 5 банковских дней с момента подписания.</p>\n<h2>3. Ответственность сторон</h2>\n<p>3.1. За неисполнение обязательств стороны несут ответственность в соответствии с законодательством РФ.</p>\n<h2>4. Реквизиты и подписи сторон</h2>\n<table style="width:100%"><tr><td style="width:50%"><strong>Продавец</strong><br/>________________</td><td style="width:50%"><strong>Покупатель</strong><br/>________________</td></tr></table>',
    },
    {
        'name': 'Договор оказания услуг',
        'document_type': DocumentType.CONTRACT,
        'html_body': '<h1 style="text-align:center">Договор оказания услуг № {{ deal_id }}</h1>\n<p>г. ________________ &laquo;___&raquo; ____________ 20__ г.</p>\n<p><strong>Исполнитель:</strong> {{ company_name }}, в лице ________________, действующего на основании ________________,</p>\n<p><strong>Заказчик:</strong> {{ contact_name }},</p>\n<p>заключили настоящий Договор о нижеследующем:</p>\n<h2>1. Предмет договора</h2>\n<p>1.1. Исполнитель обязуется оказать Заказчику услуги, а Заказчик — принять и оплатить их.</p>\n<p>1.2. Описание: {{ deal_name }}.</p>\n<h2>2. Стоимость и порядок оплаты</h2>\n<p>2.1. Стоимость услуг составляет {{ amount }} {{ currency }}.</p>\n<p>2.2. Оплата — в течение 10 рабочих дней после подписания акта приёмки.</p>\n<h2>3. Сроки оказания услуг</h2>\n<p>3.1. Услуги оказываются в течение 30 календарных дней с момента подписания Договора.</p>\n<h2>4. Реквизиты и подписи сторон</h2>\n<table style="width:100%"><tr><td style="width:50%"><strong>Исполнитель</strong><br/>________________</td><td style="width:50%"><strong>Заказчик</strong><br/>________________</td></tr></table>',
    },
    {
        'name': 'Договор аренды',
        'document_type': DocumentType.CONTRACT,
        'html_body': '<h1 style="text-align:center">Договор аренды № {{ deal_id }}</h1>\n<p>г. ________________ &laquo;___&raquo; ____________ 20__ г.</p>\n<p><strong>Арендодатель:</strong> {{ company_name }}, в лице ________________, действующего на основании ________________,</p>\n<p><strong>Арендатор:</strong> {{ contact_name }},</p>\n<p>заключили настоящий Договор о нижеследующем:</p>\n<h2>1. Предмет договора</h2>\n<p>1.1. Арендодатель предоставляет Арендатору во временное пользование имущество.</p>\n<p>1.2. Описание: {{ deal_name }}.</p>\n<h2>2. Арендная плата</h2>\n<p>2.1. Ежемесячная арендная плата: {{ amount }} {{ currency }}.</p>\n<p>2.2. Оплата — не позднее 5-го числа текущего месяца.</p>\n<h2>3. Срок действия</h2>\n<p>3.1. Договор вступает в силу с момента подписания и действует 12 месяцев.</p>\n<h2>4. Реквизиты и подписи сторон</h2>\n<table style="width:100%"><tr><td style="width:50%"><strong>Арендодатель</strong><br/>________________</td><td style="width:50%"><strong>Арендатор</strong><br/>________________</td></tr></table>',
    },
    {
        'name': 'Акт выполненных работ',
        'document_type': DocumentType.ACT,
        'html_body': '<h1 style="text-align:center">Акт выполненных работ № {{ deal_id }}</h1>\n<p>г. ________________ &laquo;___&raquo; ____________ 20__ г.</p>\n<p><strong>Исполнитель:</strong> {{ company_name }}</p>\n<p><strong>Заказчик:</strong> {{ contact_name }}</p>\n<p>Оказаны следующие услуги по сделке «{{ deal_name }}»:</p>\n<ul>\n<li>Услуга 1 — {{ amount }} {{ currency }};</li>\n<li>Услуга 2 — 0 {{ currency }};</li>\n</ul>\n<p><strong>Итого:</strong> {{ amount }} {{ currency }}.</p>\n<p>Претензий по объёму, стоимости и качеству оказанных услуг не имеется.</p>\n<table style="width:100%"><tr><td style="width:50%"><strong>Исполнитель</strong><br/>________________</td><td style="width:50%"><strong>Заказчик</strong><br/>________________</td></tr></table>',
    },
    {
        'name': 'Счёт на оплату',
        'document_type': DocumentType.INVOICE,
        'html_body': '<h1 style="text-align:center">Счёт на оплату № {{ deal_id }}</h1>\n<p>г. ________________ &laquo;___&raquo; ____________ 20__ г.</p>\n<p><strong>Плательщик:</strong> {{ company_name }}</p>\n<p><strong>Контакт:</strong> {{ contact_name }}</p>\n<p><strong>Назначение платежа:</strong> Оплата по сделке «{{ deal_name }}».</p>\n<table style="width:100%;border-collapse:collapse">\n<tr><th style="border:1px solid #ccc;padding:6px">№</th><th style="border:1px solid #ccc;padding:6px">Наименование</th><th style="border:1px solid #ccc;padding:6px">Сумма</th></tr>\n<tr><td style="border:1px solid #ccc;padding:6px">1</td><td style="border:1px solid #ccc;padding:6px">{{ deal_name }}</td><td style="border:1px solid #ccc;padding:6px">{{ amount }} {{ currency }}</td></tr>\n</table>\n<p><strong>Итого к оплате:</strong> {{ amount }} {{ currency }}.</p>',
    },
    {
        'name': 'Публичная оферта',
        'document_type': DocumentType.OFFER,
        'html_body': '<h1 style="text-align:center">Публичная оферта</h1>\n<p>Настоящая публичная оферта адресована любым физическим и юридическим лицам (далее — Клиент).</p>\n<h2>1. Общие положения</h2>\n<p>1.1. {{ company_name }} (далее — Исполнитель) предлагает Клиенту услуги в соответствии с настоящей Офертой.</p>\n<h2>2. Предмет оферты</h2>\n<p>2.1. Предметом оферты являются услуги по сделке «{{ deal_name }}» на сумму {{ amount }} {{ currency }}.</p>\n<h2>3. Порядок акцепта</h2>\n<p>3.1. Акцептом считается совершение Клиентом действий, предусмотренных настоящей Офертой.</p>',
    },
    {
        'name': 'Дополнительное соглашение',
        'document_type': DocumentType.ADDENDUM,
        'html_body': '<h1 style="text-align:center">Дополнительное соглашение № {{ deal_id }}</h1>\n<p>г. ________________ &laquo;___&raquo; ____________ 20__ г.</p>\n<p><strong>Стороны:</strong> {{ company_name }} и {{ contact_name }}.</p>\n<p>Настоящим Стороны договорились внести следующие изменения в основной договор по сделке «{{ deal_name }}»:</p>\n<ul>\n<li>Изменение 1: сумма договора устанавливается в размере {{ amount }} {{ currency }};</li>\n<li>Изменение 2: иные условия остаются без изменения.</li>\n</ul>\n<table style="width:100%"><tr><td style="width:50%"><strong>{{ company_name }}</strong><br/>________________</td><td style="width:50%"><strong>{{ contact_name }}</strong><br/>________________</td></tr></table>',
    },
    {
        'name': 'Прочий документ',
        'document_type': DocumentType.OTHER,
        'html_body': '<h1 style="text-align:center">{{ deal_name }}</h1>\n<p>Дата: {{ created_at }}.</p>\n<p><strong>Участники:</strong> {{ company_name }} и {{ contact_name }}.</p>\n<p>Сумма: {{ amount }} {{ currency }}.</p>\n<p>Текст документа...</p>',
    },
]


def _create_missing_templates() -> None:
    """Create system templates that do not yet exist in the current schema."""
    for tpl in SYSTEM_TEMPLATES:
        if not DocumentTemplate.objects.filter(name=tpl['name'], is_system=True).exists():
            DocumentTemplate.objects.create(
                name=tpl['name'],
                document_type=tpl['document_type'],
                html_body=tpl['html_body'],
                variable_schema=COMMON_SCHEMA,
                is_system=True,
                is_active=True,
            )


def seed_system_templates_for_tenant(tenant) -> None:
    """Idempotently seed system document templates inside a tenant schema."""
    with schema_context(tenant.schema_name):
        _create_missing_templates()


def seed_system_templates_for_all_tenants() -> None:
    """Seed system templates for every existing tenant. Used in data migrations."""
    for tenant in Tenant.objects.all():
        seed_system_templates_for_tenant(tenant)

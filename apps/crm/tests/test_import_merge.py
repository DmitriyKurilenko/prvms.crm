from __future__ import annotations

import io

from apps.crm.models import Activity, Company, Contact, Deal, ImportJob, Pipeline, Stage
from apps.crm.services.import_export import (
    export_contacts_csv,
    export_deals_csv,
    parse_file,
    suggest_mapping,
)
from apps.crm.services.merge import (
    find_duplicate_companies,
    find_duplicate_contacts,
    merge_companies,
    merge_contacts,
)
from apps.crm.tasks import import_records
from apps.users.tests.base import TenantAPITestCase


class ParseAndExportTest(TenantAPITestCase):
    def test_parse_csv_headers_and_rows(self):
        content = 'Имя,Телефон\nИван,+7900\nПётр,+7901\n'.encode('utf-8')
        headers, rows = parse_file('contacts.csv', content)
        self.assertEqual(headers, ['Имя', 'Телефон'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['Имя'], 'Иван')

    def test_parse_xlsx_headers_and_rows(self):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(['Название', 'ИНН'])
        ws.append(['ООО Ромашка', '7700000000'])
        ws.append(['ИП Петров', None])
        buf = io.BytesIO()
        wb.save(buf)

        headers, rows = parse_file('companies.xlsx', buf.getvalue())
        self.assertEqual(headers, ['Название', 'ИНН'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['Название'], 'ООО Ромашка')
        self.assertEqual(rows[1]['ИНН'], '')  # None → пустая строка

    def test_suggest_mapping_matches_russian_headers(self):
        mapping = suggest_mapping('contacts', ['Имя', 'Телефон', 'Неизвестно'])
        self.assertEqual(mapping['Имя'], 'first_name')
        self.assertEqual(mapping['Телефон'], 'phone')
        self.assertNotIn('Неизвестно', mapping)

    def test_export_contacts_csv_has_bom(self):
        Contact.objects.create(first_name='Иван', phone='+7900', source='manual')
        body = export_contacts_csv(Contact.objects.all())
        self.assertTrue(body.startswith('﻿'))
        self.assertIn('Иван', body)


class ImportRecordsTest(TenantAPITestCase):
    def test_import_creates_and_dedups_contacts_by_phone(self):
        Contact.objects.create(first_name='Старый', phone='+7900', email='')
        rows = [
            {'Имя': 'Иван', 'Телефон': '+7900', 'Заметка': 'апдейт'},   # дубль по телефону → update
            {'Имя': 'Пётр', 'Телефон': '+7901', 'Заметка': 'новый'},     # новый
            {'Имя': '', 'Телефон': '', 'Заметка': 'пусто'},               # ошибка: пустая строка
        ]
        mapping = {'Имя': 'first_name', 'Телефон': 'phone', 'Заметка': 'note'}
        job = ImportJob.objects.create(entity='contacts')

        import_records(self.tenant.schema_name, job.id, 'contacts', rows, mapping)

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.created, 1)
        self.assertEqual(job.updated, 1)
        self.assertEqual(len(job.errors), 1)
        self.assertEqual(job.errors[0]['row'], 4)

        updated = Contact.objects.get(phone='+7900')
        self.assertEqual(updated.first_name, 'Иван')
        self.assertEqual(updated.custom_fields.get('note'), 'апдейт')  # неизвестное поле → custom_fields
        self.assertTrue(Contact.objects.filter(phone='+7901', first_name='Пётр').exists())


class MergeTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True)
        self.stage = Stage.objects.create(pipeline=self.pipeline, name='New', stage_type='open')

    def test_merge_contacts_moves_deals_and_activities(self):
        primary = Contact.objects.create(first_name='Основной', phone='+7900')
        dup = Contact.objects.create(first_name='Дубль', phone='', email='dup@example.com')
        deal = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.stage, contact=dup)
        act = Activity.objects.create(activity_type='note', contact=dup, title='note')

        result = merge_contacts(primary.id, [dup.id])

        deal.refresh_from_db()
        act.refresh_from_db()
        primary.refresh_from_db()
        self.assertEqual(deal.contact_id, primary.id)
        self.assertEqual(act.contact_id, primary.id)
        self.assertEqual(primary.email, 'dup@example.com')  # пустое поле дозаполнено из дубля
        self.assertFalse(Contact.objects.filter(id=dup.id).exists())
        self.assertEqual(result['moved_deals'], 1)
        self.assertEqual(result['moved_activities'], 1)

    def test_merge_contacts_ignores_primary_in_merged_ids(self):
        primary = Contact.objects.create(first_name='Основной', phone='+7900')
        result = merge_contacts(primary.id, [primary.id])
        self.assertTrue(Contact.objects.filter(id=primary.id).exists())
        self.assertEqual(result['merged'], 0)

    def test_merge_companies_moves_contacts_and_deals(self):
        primary = Company.objects.create(name='Основная', inn='7700000001')
        dup = Company.objects.create(name='Дубль', inn='', email='c@example.com')
        contact = Contact.objects.create(first_name='K', company=dup)
        deal = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.stage, company=dup)

        result = merge_companies(primary.id, [dup.id])

        contact.refresh_from_db()
        deal.refresh_from_db()
        primary.refresh_from_db()
        self.assertEqual(contact.company_id, primary.id)
        self.assertEqual(deal.company_id, primary.id)
        self.assertEqual(primary.email, 'c@example.com')
        self.assertFalse(Company.objects.filter(id=dup.id).exists())
        self.assertEqual(result['moved_contacts'], 1)
        self.assertEqual(result['moved_deals'], 1)

    def test_find_duplicate_contacts_groups_by_phone(self):
        Contact.objects.create(first_name='A', phone='+7900')
        Contact.objects.create(first_name='B', phone='+7900')
        Contact.objects.create(first_name='C', phone='+7999')
        groups = find_duplicate_contacts()
        phone_groups = [g for g in groups if g['key_type'] == 'phone']
        self.assertEqual(len(phone_groups), 1)
        self.assertEqual(len(phone_groups[0]['items']), 2)

    def test_find_duplicate_companies_groups_by_inn(self):
        Company.objects.create(name='X', inn='7700000002')
        Company.objects.create(name='Y', inn='7700000002')
        groups = find_duplicate_companies()
        inn_groups = [g for g in groups if g['key_type'] == 'inn']
        self.assertEqual(len(inn_groups), 1)


class ExportApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='exp_owner@example.com', username='exp_owner')

    def test_export_contacts_endpoint_returns_csv(self):
        Contact.objects.create(first_name='Иван', phone='+7900')
        resp = self.client.get('/api/crm/export/contacts/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])

    def test_export_rejects_unknown_entity(self):
        resp = self.client.get('/api/crm/export/orders/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 400)

    def test_export_deals_endpoint_returns_csv(self):
        p = Pipeline.objects.create(name='Main', is_default=True)
        s = Stage.objects.create(pipeline=p, name='New', stage_type='open')
        Deal.objects.create(name='Сделка1', pipeline=p, stage=s)
        resp = self.client.get('/api/crm/export/deals/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('Сделка1', resp.content.decode('utf-8'))


class DealImportExportServiceTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Продажи', is_default=True)
        self.s_new = Stage.objects.create(pipeline=self.pipeline, name='Новая', stage_type='open', sort_order=0)
        self.s_work = Stage.objects.create(pipeline=self.pipeline, name='В работе', stage_type='open', sort_order=1)
        self.contact = Contact.objects.create(first_name='Иван', last_name='Петров', phone='+7900')

    def test_import_creates_deal_resolves_fk_and_dedups(self):
        rows = [
            {'Название': 'Сделка А', 'Воронка': 'Продажи', 'Стадия': 'В работе', 'Сумма': '1000', 'Контакт': '+7900'},
            {'Название': 'Сделка А', 'Воронка': 'Продажи', 'Стадия': 'В работе', 'Сумма': '2000', 'Контакт': '+7900'},
            {'Название': 'Сделка Б', 'Контакт': 'Неизвестный'},
        ]
        mapping = {'Название': 'name', 'Воронка': 'pipeline', 'Стадия': 'stage', 'Сумма': 'amount', 'Контакт': 'contact'}
        job = ImportJob.objects.create(entity='deals')
        import_records(self.tenant.schema_name, job.id, 'deals', rows, mapping)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.created, 2)  # Сделка А + Сделка Б
        self.assertEqual(job.updated, 1)  # повтор Сделка А по name+contact

        a = Deal.objects.get(name='Сделка А')
        self.assertEqual(a.contact_id, self.contact.id)
        self.assertEqual(a.stage_id, self.s_work.id)
        self.assertEqual(float(a.amount), 2000.0)  # обновлено вторым рядом

        b = Deal.objects.get(name='Сделка Б')
        self.assertEqual(b.pipeline_id, self.pipeline.id)  # дефолтная воронка
        self.assertEqual(b.stage_id, self.s_new.id)        # первая стадия
        self.assertIsNone(b.contact_id)                    # контакт не найден

    def test_import_deal_requires_name(self):
        rows = [{'Название': '', 'Сумма': '100'}]
        mapping = {'Название': 'name', 'Сумма': 'amount'}
        job = ImportJob.objects.create(entity='deals')
        import_records(self.tenant.schema_name, job.id, 'deals', rows, mapping)
        job.refresh_from_db()
        self.assertEqual(job.created, 0)
        self.assertEqual(len(job.errors), 1)

    def test_export_deals_csv_has_bom_and_fields(self):
        Deal.objects.create(name='Экспорт', pipeline=self.pipeline, stage=self.s_new,
                            contact=self.contact, amount=500, currency='RUB')
        body = export_deals_csv(
            Deal.objects.select_related('pipeline', 'stage', 'contact').all(),
        )
        self.assertTrue(body.startswith('﻿'))
        self.assertIn('Экспорт', body)
        self.assertIn('Продажи', body)
        self.assertIn('Иван Петров', body)

from __future__ import annotations

import json

from django.db import connection
from django_tenants.utils import schema_context

from apps.crm.models import Contact, Deal, Pipeline, Stage
from apps.tenants.models import ExolveNumberLookup
from apps.telephony.models import CallRecord, ExolveChannel, ExolveSIPAccount
from apps.telephony.tasks import process_exolve_event
from apps.users.tests.base import TenantAPITestCase

TENANT_NUMBER = '79991110000'
CLIENT_NUMBER = '79995550011'


class ExolveInboundTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Продажи', is_default=True, sort_order=0, is_active=True)
        self.stage = Stage.objects.create(pipeline=self.pipeline, name='Новый', stage_type='open', sort_order=0)
        self.channel = ExolveChannel.objects.create(
            exolve_number=TENANT_NUMBER, number_code=TENANT_NUMBER, status='active', is_active=True,
        )
        with schema_context('public'):
            ExolveNumberLookup.objects.create(number=TENANT_NUMBER, number_code=TENANT_NUMBER, tenant=self.tenant)

    def _sip_for(self, user, username, name='Менеджер'):
        manager = self.create_manager_profile(name=name, user=user, crm_user_id=str(user.id))
        return ExolveSIPAccount.objects.create(
            manager=manager, sip_resource_id='1', username=username,
            password='secret', display_number=TENANT_NUMBER, status='active', is_active=True,
        )

    def _ipcr(self, numberA=CLIENT_NUMBER):
        body = {
            'id': '1', 'jsonrpc': '2.0', 'method': 'getControlCallFollowMe',
            'params': {'sip_id': TENANT_NUMBER, 'numberA': numberA, 'call_sid': f'call-{numberA}'},
        }
        resp = self.client.post(
            '/telephony/exolve/ipcr/', data=json.dumps(body),
            content_type='application/json', HTTP_HOST='localhost',
        )
        # после публичного запроса (host=localhost) middleware оставляет схему
        # public — возвращаем схему тенанта для ORM-проверок теста.
        connection.set_tenant(self.tenant)
        return resp

    def test_inbound_creates_deal_and_routes_to_sip(self):
        owner = self.create_user(role='owner')
        sip = self._sip_for(owner, '8831000001')

        resp = self._ipcr()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        targets = data['result']['followme_struct'][1]
        self.assertTrue(any(t['REDIRECT_NUMBER'] == sip.username for t in targets))

        self.assertEqual(Deal.objects.count(), 1)
        self.assertEqual(Contact.objects.filter(phone=CLIENT_NUMBER).count(), 1)
        self.assertTrue(CallRecord.objects.filter(call_sid=f'call-{CLIENT_NUMBER}', direction='inbound').exists())

    def test_inbound_dedup_does_not_duplicate_active_deal(self):
        owner = self.create_user(role='owner')
        self._sip_for(owner, '8831000002')

        self._ipcr()
        self._ipcr()
        self.assertEqual(Deal.objects.count(), 1)

    def test_inbound_prefers_responsible_manager(self):
        responsible = self.create_user(role='manager', email='resp@example.com')
        other = self.create_user(role='manager', email='other@example.com')
        resp_sip = self._sip_for(responsible, '8831000010', name='Ответственный')
        self._sip_for(other, '8831000011', name='Другой')

        contact = Contact.objects.create(first_name='Клиент', phone=CLIENT_NUMBER, responsible=responsible)
        # активная сделка у контакта → дедуп вернёт её, ответственного берём с контакта
        Deal.objects.create(name='Существующая', pipeline=self.pipeline, stage=self.stage, contact=contact)

        data = self._ipcr().json()
        first = data['result']['followme_struct'][1][0]
        self.assertEqual(first['REDIRECT_NUMBER'], resp_sip.username)
        self.assertEqual(first['I_FOLLOW_ORDER'], 1)
        self.assertEqual(Deal.objects.count(), 1)

    def test_unknown_number_returns_empty_route(self):
        body = {
            'id': '7', 'jsonrpc': '2.0', 'method': 'getControlCallFollowMe',
            'params': {'sip_id': '70000000000', 'numberA': CLIENT_NUMBER, 'call_sid': 'x'},
        }
        resp = self.client.post(
            '/telephony/exolve/ipcr/', data=json.dumps(body),
            content_type='application/json', HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['result']['followme_struct'][1], [])

    def test_begin_event_creates_deal_with_dedup(self):
        begin = {
            'type': 'b', 'call_sid': 'in-1', 'from': CLIENT_NUMBER, 'to': TENANT_NUMBER,
            'date_time': '2026-06-15T08:35:34Z', 'call_id': 555,
        }
        process_exolve_event(self.tenant.id, begin)
        self.assertEqual(Deal.objects.count(), 1)
        self.assertEqual(Contact.objects.filter(phone=CLIENT_NUMBER).count(), 1)
        rec = CallRecord.objects.get(call_sid='in-1')
        self.assertEqual(rec.direction, 'inbound')
        self.assertTrue(rec.crm_lead_id)

        # второй входящий с того же номера → дедуп, новая сделка не создаётся
        process_exolve_event(self.tenant.id, {**begin, 'call_sid': 'in-2'})
        self.assertEqual(Deal.objects.count(), 1)

    def test_call_event_marks_answered(self):
        CallRecord.objects.create(
            call_sid='evt-1', direction='inbound', caller_number=CLIENT_NUMBER,
            called_number=TENANT_NUMBER, result='missed', started_at=self.channel.created_at,
        )
        payload = {
            'type': 'd', 'call_sid': 'evt-1', 'to': TENANT_NUMBER, 'from': CLIENT_NUMBER,
            'duration': 25000, 'wait_time': 5000, 'talk_time': 20000, 'cause_code': '16',
            'date_time': '2026-06-15T08:35:34Z',
        }
        process_exolve_event(self.tenant.id, payload)
        record = CallRecord.objects.get(call_sid='evt-1')
        self.assertEqual(record.result, 'answered')
        self.assertEqual(record.talk_time, 20)
        self.assertEqual(record.duration, 25)

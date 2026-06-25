from __future__ import annotations

import uuid
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone

from apps.crm.models import Activity, Deal, Pipeline, Stage
from apps.telephony.deepgram_client import DeepgramError, transcribe
from apps.telephony.models import CallRecord, CallTranscript
from apps.telephony.tasks import summarize_call, transcribe_call_record
from apps.users.tests.base import TenantAPITestCase

_FAKE_ASR = {'text': 'Здравствуйте, по заявке.', 'confidence': 0.95,
             'language': 'ru', 'duration': 12.0, 'request_id': 'req-1'}


class CallIntelligenceTaskTest(TenantAPITestCase):
    def _call(self, with_audio=True, crm_lead_id=''):
        rec = CallRecord.objects.create(
            call_sid=f'cs-{uuid.uuid4()}', direction='inbound',
            caller_number='+79990000000', called_number='+78310000000',
            started_at=timezone.now(), crm_lead_id=crm_lead_id,
        )
        if with_audio:
            rec.record_file.save('x.mp3', ContentFile(b'fake-mp3-bytes'), save=True)
        return rec

    def test_transcribe_creates_transcript_and_chains_summary(self):
        rec = self._call()
        with patch('apps.telephony.deepgram_client.transcribe', return_value=_FAKE_ASR), \
             patch('apps.telephony.tasks.summarize_call.delay') as summary_delay:
            res = transcribe_call_record(self.tenant.id, rec.id)
        self.assertEqual(res['status'], 'ok')
        tr = CallTranscript.objects.get(call=rec)
        self.assertEqual(tr.status, 'done')
        self.assertEqual(tr.text, _FAKE_ASR['text'])
        self.assertEqual(tr.confidence, 0.95)
        summary_delay.assert_called_once()

    def test_transcribe_marks_failed_on_asr_error(self):
        rec = self._call()
        with patch('apps.telephony.deepgram_client.transcribe', side_effect=DeepgramError('boom')), \
             patch('apps.telephony.tasks.summarize_call.delay'):
            res = transcribe_call_record(self.tenant.id, rec.id)
        self.assertEqual(res['status'], 'failed')
        tr = CallTranscript.objects.get(call=rec)
        self.assertEqual(tr.status, 'failed')
        self.assertIn('boom', tr.error)

    def test_transcribe_skips_without_audio(self):
        rec = self._call(with_audio=False)
        res = transcribe_call_record(self.tenant.id, rec.id)
        self.assertEqual(res['reason'], 'no_audio')

    def test_summarize_creates_timeline_activity(self):
        pipeline = Pipeline.objects.create(name='P', is_default=True)
        stage = Stage.objects.create(pipeline=pipeline, name='New', stage_type='open')
        deal = Deal.objects.create(name='D', pipeline=pipeline, stage=stage)
        rec = self._call(crm_lead_id=str(deal.id))
        tr = CallTranscript.objects.create(call=rec, status='done', text='Клиент согласен на счёт.')
        with patch('apps.ai_assistant.services.summarize_call_text', return_value='Договорились выставить счёт.'):
            res = summarize_call(self.tenant.id, tr.id)
        self.assertEqual(res['status'], 'ok')
        tr.refresh_from_db()
        self.assertEqual(tr.summary, 'Договорились выставить счёт.')
        self.assertTrue(
            Activity.objects.filter(activity_type='note', title='Резюме звонка', deal=deal).exists()
        )


class DeepgramClientTest(TenantAPITestCase):
    @override_settings(DEEPGRAM_API_KEY='')
    def test_transcribe_requires_key(self):
        with self.assertRaises(DeepgramError):
            transcribe(b'audio')

    @override_settings(DEEPGRAM_API_KEY='k')
    def test_transcribe_rejects_empty_audio(self):
        with self.assertRaises(DeepgramError):
            transcribe(b'')


class TranscribeEndpointTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='ci_owner@example.com', username='ci_owner')

    def test_manual_transcribe_queues_task(self):
        rec = CallRecord.objects.create(
            call_sid=f'cs-{uuid.uuid4()}', direction='inbound',
            caller_number='+7', called_number='+7', started_at=timezone.now(),
        )
        rec.record_file.save('x.mp3', ContentFile(b'bytes'), save=True)
        with patch('apps.telephony.tasks.transcribe_call_record.delay') as delay:
            resp = self.client.post(f'/api/telephony/calls/{rec.id}/transcribe/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'queued')
        delay.assert_called_once()

    def test_transcribe_404_without_record_file(self):
        rec = CallRecord.objects.create(
            call_sid=f'cs-{uuid.uuid4()}', direction='inbound',
            caller_number='+7', called_number='+7', started_at=timezone.now(),
        )
        resp = self.client.post(f'/api/telephony/calls/{rec.id}/transcribe/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 400)

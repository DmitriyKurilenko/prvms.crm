from __future__ import annotations

from unittest.mock import patch

from apps.crm.models import Contact, Deal, Pipeline, Stage, WebForm
from apps.crm.services.webform_intake import intake_webform_submission
from apps.users.tests.base import TenantAPITestCase


class WebFormIntakeTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0, is_active=True)
        self.stage = Stage.objects.create(pipeline=self.pipeline, name='New', stage_type='open', sort_order=0)
        self.form = WebForm.objects.create(
            name='Сайт', pipeline=self.pipeline, stage=self.stage, source='webform', auto_distribute=False,
        )

    @patch('apps.crm.services.webform_intake.notify')
    def test_submission_creates_contact_and_deal(self, _notify):
        res = intake_webform_submission(
            self.tenant, self.form.public_token,
            {'name': 'Иван', 'phone': '+7900', 'email': 'i@e.com', 'comment': 'срочно'},
        )
        self.assertIsNotNone(res)
        deal = Deal.objects.get(id=res['deal_id'])
        self.assertEqual(deal.pipeline_id, self.pipeline.id)
        self.assertEqual(deal.stage_id, self.stage.id)
        contact = Contact.objects.get(id=res['contact_id'])
        self.assertEqual(contact.first_name, 'Иван')
        self.assertEqual(contact.phone, '+7900')
        self.assertEqual(contact.custom_fields.get('comment'), 'срочно')
        self.form.refresh_from_db()
        self.assertEqual(self.form.submissions_count, 1)

    @patch('apps.crm.services.webform_intake.notify')
    def test_inactive_form_returns_none(self, _notify):
        self.form.is_active = False
        self.form.save(update_fields=['is_active'])
        res = intake_webform_submission(self.tenant, self.form.public_token, {'name': 'Пётр'})
        self.assertIsNone(res)

    @patch('apps.crm.services.webform_intake.notify')
    def test_empty_name_falls_back(self, _notify):
        res = intake_webform_submission(self.tenant, self.form.public_token, {'phone': '+7901'})
        contact = Contact.objects.get(id=res['contact_id'])
        self.assertEqual(contact.first_name, 'Лид с формы')


class WebFormPermissionsTest(TenantAPITestCase):
    def test_webforms_entity_in_permission_matrix(self):
        from apps.users.permissions import get_role_permissions_for_role
        perms = get_role_permissions_for_role(self.tenant.id, 'owner')
        self.assertIn('webforms', perms)
        self.assertTrue(perms['webforms']['can_create'])
        viewer = get_role_permissions_for_role(self.tenant.id, 'viewer')
        self.assertFalse(viewer['webforms']['can_create'])

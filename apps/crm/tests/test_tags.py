from __future__ import annotations

from apps.crm.models import Contact, Deal, Pipeline, Segment, Stage, Tag
from apps.users.tests.base import TenantAPITestCase


class TagsTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0)
        self.stage = Stage.objects.create(pipeline=self.pipeline, name='New', stage_type='open', sort_order=0)

    def test_assign_and_filter_contacts_by_tag(self):
        tag = Tag.objects.create(name='VIP')
        c1 = Contact.objects.create(first_name='Иван')
        Contact.objects.create(first_name='Пётр')
        c1.tags.add(tag)
        self.assertEqual(Contact.objects.filter(tags__id=tag.id).count(), 1)
        self.assertEqual(Contact.objects.filter(tags__id=tag.id).first().id, c1.id)

    def test_assign_and_filter_deals_by_tag(self):
        tag = Tag.objects.create(name='Срочно')
        d = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.stage)
        d.tags.add(tag)
        self.assertEqual(Deal.objects.filter(tags__id=tag.id).count(), 1)

    def test_tag_name_unique(self):
        Tag.objects.create(name='Уник')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Tag.objects.create(name='Уник')

    def test_segment_stores_filter(self):
        seg = Segment.objects.create(name='VIP-сегмент', entity='contacts', filters={'tag_ids': [1, 2]})
        seg.refresh_from_db()
        self.assertEqual(seg.filters['tag_ids'], [1, 2])
        self.assertEqual(seg.entity, 'contacts')


class TagSerializationApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='tag_owner@example.com', username='tag_owner')
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0)
        self.stage = Stage.objects.create(pipeline=self.pipeline, name='New', stage_type='open', sort_order=0)
        self.tag = Tag.objects.create(name='VIP', color='#ff0000')

    def test_get_contact_returns_tags(self):
        c = Contact.objects.create(first_name='Иван')
        c.tags.add(self.tag)
        resp = self.client.get(f'/api/crm/contacts/{c.id}/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 200)
        tags = resp.json()['tags']
        self.assertEqual([t['id'] for t in tags], [self.tag.id])
        self.assertEqual(tags[0]['name'], 'VIP')
        self.assertEqual(tags[0]['color'], '#ff0000')

    def test_get_deal_returns_tags(self):
        d = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.stage)
        d.tags.add(self.tag)
        resp = self.client.get(f'/api/crm/deals/{d.id}/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([t['id'] for t in resp.json()['tags']], [self.tag.id])

    def test_kanban_returns_deal_tags(self):
        d = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.stage)
        d.tags.add(self.tag)
        resp = self.client.get(f'/api/crm/deals/kanban/{self.pipeline.id}/', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 200)
        columns = resp.json()
        deal_payload = next(dl for col in columns for dl in col['deals'] if dl['id'] == d.id)
        self.assertEqual([t['id'] for t in deal_payload['tags']], [self.tag.id])

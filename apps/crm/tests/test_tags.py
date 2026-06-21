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

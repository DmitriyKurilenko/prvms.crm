from __future__ import annotations

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='tenants.Tenant')
def populate_sip_domain(sender, instance, created, **kwargs):
    if created and not instance.sip_domain:
        base = getattr(settings, 'SIP_BASE_DOMAIN', 'sip.localhost')
        instance.sip_domain = f'{instance.slug}.{base}'
        instance.__class__.objects.filter(pk=instance.pk).update(sip_domain=instance.sip_domain)

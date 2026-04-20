from django.db import models
from apps.core.fields import EncryptedJSONField
from encrypted_fields.fields import EncryptedCharField


class SIPTrunk(models.Model):
    """Подключение SIP-транка к оператору связи."""
    TRUNK_TYPE_CHOICES = [
        ('zadarma', 'Zadarma'),
        ('mcn', 'MCN Telecom'),
        ('rostelecom', 'Ростелеком'),
        ('exolve', 'МТС Exolve'),
        ('custom_sip', 'Произвольный SIP'),
    ]
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('registering', 'Регистрация...'),
        ('error', 'Ошибка'),
        ('disabled', 'Отключён'),
    ]

    name = models.CharField(max_length=200)
    trunk_type = models.CharField(max_length=20, choices=TRUNK_TYPE_CHOICES)
    crm_connection = models.ForeignKey(
        'integrations.CRMConnection',
        on_delete=models.SET_NULL,
        related_name='sip_trunks',
        null=True,
        blank=True,
    )
    credentials = EncryptedJSONField()
    inbound_numbers = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registering')
    status_detail = models.TextField(blank=True)
    last_registration_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} ({self.trunk_type})'


class PhoneExtension(models.Model):
    """Внутренний номер (extension) менеджера в телефонии."""
    manager = models.OneToOneField(
        'integrations.ManagerProfile',
        on_delete=models.CASCADE,
        related_name='phone_extension',
    )
    extension = models.CharField(max_length=10)
    sip_password = EncryptedCharField(max_length=100)
    webrtc_enabled = models.BooleanField(default=True)
    voicemail_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['extension'], name='unique_extension_per_tenant'),
        ]

    def __str__(self):
        return f'ext:{self.extension} ({self.manager})'


class IVRMenu(models.Model):
    """Голосовое меню (IVR). Многоуровневое."""
    name = models.CharField(max_length=200)
    greeting_audio = models.FileField(upload_to='telephony/ivr/', blank=True)
    greeting_tts = models.TextField(blank=True)
    options = models.JSONField(default=list)
    timeout = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CallQueue(models.Model):
    """Очередь звонков."""
    STRATEGY_CHOICES = [
        ('ring_all', 'Звонок всем'),
        ('round_robin', 'По очереди'),
        ('least_recent', 'Наименее недавний'),
        ('random', 'Случайный'),
    ]

    name = models.CharField(max_length=200)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='ring_all')
    members = models.ManyToManyField(
        'integrations.ManagerProfile',
        related_name='call_queues',
        blank=True,
    )
    ring_timeout = models.PositiveIntegerField(default=20)
    max_wait_time = models.PositiveIntegerField(default=120)
    hold_music = models.FileField(upload_to='telephony/hold/', blank=True)
    announce_position = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CallRecord(models.Model):
    """Запись о звонке."""
    DIRECTION_CHOICES = [
        ('inbound', 'Входящий'),
        ('outbound', 'Исходящий'),
        ('internal', 'Внутренний'),
    ]
    RESULT_CHOICES = [
        ('answered', 'Отвечен'),
        ('missed', 'Пропущен'),
        ('busy', 'Занято'),
        ('voicemail', 'Голосовая почта'),
        ('ivr_only', 'Только IVR'),
    ]

    sip_trunk = models.ForeignKey(SIPTrunk, on_delete=models.SET_NULL, null=True, related_name='calls')
    freeswitch_uuid = models.CharField(max_length=200, unique=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    caller_number = models.CharField(max_length=50)
    called_number = models.CharField(max_length=50)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    duration = models.PositiveIntegerField(default=0)
    wait_time = models.PositiveIntegerField(default=0)
    queue = models.ForeignKey(CallQueue, on_delete=models.SET_NULL, null=True, blank=True)
    manager = models.ForeignKey(
        'integrations.ManagerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calls',
    )
    crm_call_id = models.CharField(max_length=200, blank=True)
    crm_contact_id = models.CharField(max_length=100, blank=True)
    crm_lead_id = models.CharField(max_length=100, blank=True)
    record_file = models.FileField(upload_to='calls/%Y/%m/', blank=True)
    record_uploaded_to_crm = models.BooleanField(default=False)
    started_at = models.DateTimeField()
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['-started_at']),
            models.Index(fields=['caller_number']),
            models.Index(fields=['manager', '-started_at']),
        ]

    def __str__(self):
        return f'{self.direction} {self.caller_number} → {self.called_number}'

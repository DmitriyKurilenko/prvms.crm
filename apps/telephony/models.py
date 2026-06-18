from django.db import models
from encrypted_fields.fields import EncryptedCharField


class ExolveChannel(models.Model):
    """Канал телефонии MTS Exolve тенанта.

    На один тенант — один номер на входящие и исходящие. Номер закупается
    автоматически через Numbering API (GetFree → Lock → Buy), после чего на
    него ставится переадресация на наш IPCR-URL (SetCallForwarding type=3).
    """

    STATUS_CHOICES = [
        ('draft', 'Не подключён'),
        ('connecting', 'Подключение…'),
        ('active', 'Активен'),
        ('error', 'Ошибка'),
        ('disabled', 'Отключён'),
    ]

    exolve_number = models.CharField(max_length=20, blank=True, help_text='Номер в формате E.164, например 79991112233')
    number_code = models.CharField(max_length=20, blank=True, help_text='number_code номера в Exolve')
    type_id = models.PositiveIntegerField(null=True, blank=True)
    region_id = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    status_detail = models.TextField(blank=True)
    forwarding_set_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Exolve {self.exolve_number or "—"} ({self.status})'


class ExolveSIPAccount(models.Model):
    """SIP-аккаунт менеджера в Exolve.

    Создаётся автоматически через SIP API (Create → GetAttributes →
    SetDisplayNumber). Браузер менеджера регистрируется этим аккаунтом через
    Web Voice SDK. CLI (отображаемый номер) = номер тенанта.
    """

    STATUS_CHOICES = [
        ('provisioning', 'Создаётся…'),
        ('active', 'Активен'),
        ('error', 'Ошибка'),
        ('disabled', 'Отключён'),
    ]

    manager = models.OneToOneField(
        'integrations.ManagerProfile',
        on_delete=models.CASCADE,
        related_name='exolve_sip',
    )
    sip_resource_id = models.CharField(max_length=50, blank=True)
    username = models.CharField(max_length=50, blank=True)
    password = EncryptedCharField(max_length=200, blank=True)
    display_number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='provisioning')
    status_detail = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['username'], name='unique_exolve_sip_username'),
        ]

    def __str__(self):
        return f'SIP {self.username or "—"} ({self.manager})'


class CallRecord(models.Model):
    """Запись о звонке (журнал телефонии)."""

    DIRECTION_CHOICES = [
        ('inbound', 'Входящий'),
        ('outbound', 'Исходящий'),
        ('internal', 'Внутренний'),
    ]
    RESULT_CHOICES = [
        ('answered', 'Отвечен'),
        ('missed', 'Пропущен'),
        ('busy', 'Занято'),
        ('failed', 'Ошибка'),
        ('voicemail', 'Голосовая почта'),
    ]

    call_sid = models.CharField(max_length=200, unique=True)
    exolve_call_id = models.CharField(max_length=64, blank=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    caller_number = models.CharField(max_length=50)
    called_number = models.CharField(max_length=50)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='missed')
    duration = models.PositiveIntegerField(default=0)
    wait_time = models.PositiveIntegerField(default=0)
    talk_time = models.PositiveIntegerField(default=0)
    cause_code = models.CharField(max_length=10, blank=True)
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

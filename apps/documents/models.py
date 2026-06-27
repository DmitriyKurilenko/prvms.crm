import uuid

from django.db import models


class DocumentType(models.TextChoices):
    CONTRACT = 'contract', 'Договор'
    ACT = 'act', 'Акт'
    INVOICE = 'invoice', 'Счёт'
    OFFER = 'offer', 'Оферта'
    ADDENDUM = 'addendum', 'Дополнительное соглашение'
    OTHER = 'other', 'Прочее'


class DocumentTemplate(models.Model):
    """Шаблон документа. HTML с Django template-переменными."""
    name = models.CharField(max_length=200)
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.CONTRACT,
    )
    version = models.PositiveIntegerField(default=1)
    html_body = models.TextField()
    variable_schema = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} v{self.version}'


class FieldMapping(models.Model):
    """Маппинг переменных шаблона на поля CRM."""
    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name='field_mappings')
    variable_key = models.CharField(max_length=100)
    crm_field_path = models.CharField(max_length=200)

    def __str__(self):
        return f'{self.variable_key} → {self.crm_field_path}'


class Document(models.Model):
    """Сгенерированный документ."""
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('sent', 'Отправлен'),
        ('viewed', 'Просмотрен'),
        ('signed', 'Подписан'),
        ('expired', 'Истёк'),
        ('cancelled', 'Отменён'),
    ]
    SIGNING_METHODS = [
        ('sms_otp', 'SMS-код'),
        ('email_otp', 'Email-код'),
    ]

    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.CONTRACT,
    )

    template = models.ForeignKey(DocumentTemplate, on_delete=models.SET_NULL, null=True)
    template_version = models.PositiveIntegerField()

    crm_entity_type = models.CharField(max_length=20)
    crm_entity_id = models.CharField(max_length=100)
    deal = models.ForeignKey(
        'crm.Deal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
    )

    filled_data = models.JSONField()
    pdf_file = models.FileField(upload_to='documents/%Y/%m/')
    html_snapshot = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    signing_method = models.CharField(max_length=20, choices=SIGNING_METHODS, default='sms_otp')

    signed_at = models.DateTimeField(null=True, blank=True)
    signer_ip = models.GenericIPAddressField(null=True, blank=True)
    signer_user_agent = models.TextField(blank=True, default='')

    # Cryptographic signing (simple electronic signature / ПЭП)
    pdf_hash = models.CharField(max_length=128, blank=True, default='',
                                help_text='SHA-256 hash of the PDF file at creation time')
    signature_data = models.JSONField(null=True, blank=True,
                                      help_text='Electronic signature details: hash, signer info, timestamp')

    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f'Document #{self.pk} ({self.status})'


class SigningSession(models.Model):
    """Сессия подписания. Одна на попытку подписания."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='signing_sessions')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    otp_code_hash = models.CharField(max_length=128, blank=True, default='')
    otp_sent_to = models.CharField(max_length=200)
    otp_sent_at = models.DateTimeField(auto_now_add=True)
    otp_expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')

    def __str__(self):
        return f'Signing {self.token} for Document #{self.document_id}'

from django.db import models


class Contact(models.Model):
    """Контакт (физлицо)."""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    messenger_id = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    company = models.ForeignKey(
        'Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contacts',
    )
    custom_fields = models.JSONField(default=dict)
    source = models.CharField(max_length=50, blank=True)
    responsible = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_contacts',
    )
    esign_agreement_signed_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Дата подписания соглашения об использовании ЭП',
    )
    esign_agreement_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='ID подписанного документа-соглашения об ЭП',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name}'.strip()


class Company(models.Model):
    """Компания (юрлицо)."""
    name = models.CharField(max_length=300)
    inn = models.CharField(max_length=12, blank=True, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    custom_fields = models.JSONField(default=dict)
    responsible = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_companies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name


class Pipeline(models.Model):
    """Воронка продаж."""
    name = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return self.name


class Stage(models.Model):
    """Стадия воронки."""
    STAGE_TYPE_CHOICES = [
        ('open', 'В работе'),
        ('won', 'Успешно завершена'),
        ('lost', 'Проиграна'),
    ]
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=200)
    stage_type = models.CharField(max_length=10, choices=STAGE_TYPE_CHOICES, default='open')
    color = models.CharField(max_length=7, default='#3B82F6')
    sort_order = models.PositiveIntegerField(default=0)
    auto_action = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return f'{self.pipeline.name} → {self.name}'


class Deal(models.Model):
    """Сделка — основная бизнес-сущность CRM."""
    name = models.CharField(max_length=300)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT, related_name='deals')
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name='deals')
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals',
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='RUB')
    responsible = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_deals',
    )
    expected_close_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    loss_reason = models.CharField(max_length=300, blank=True)
    custom_fields = models.JSONField(default=dict)
    source = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['stage', '-updated_at']),
            models.Index(fields=['responsible', '-updated_at']),
            models.Index(fields=['contact']),
        ]

    def __str__(self):
        return self.name


class Activity(models.Model):
    """Активность — любое событие в таймлайне сделки/контакта."""
    ACTIVITY_TYPE_CHOICES = [
        ('call', 'Звонок'),
        ('message', 'Сообщение'),
        ('task', 'Задача'),
        ('note', 'Заметка'),
        ('email', 'Email'),
        ('document', 'Документ'),
        ('stage_change', 'Смена стадии'),
        ('system', 'Системное'),
    ]
    STATUS_CHOICES = [
        ('planned', 'Запланировано'),
        ('done', 'Выполнено'),
        ('overdue', 'Просрочено'),
    ]

    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activities',
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activities',
    )
    responsible = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_activities',
    )
    title = models.CharField(max_length=300)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='done')
    due_date = models.DateTimeField(null=True, blank=True)

    related_call = models.ForeignKey(
        'telephony.CallRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
    )
    related_document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
    )
    related_message = models.ForeignKey(
        'messenger_channels.MessageLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
    )

    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deal', '-created_at']),
            models.Index(fields=['contact', '-created_at']),
            models.Index(fields=['responsible', 'status', '-due_date']),
        ]
        verbose_name_plural = 'activities'

    def __str__(self):
        return self.title

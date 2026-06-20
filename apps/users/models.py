from django.contrib.auth.models import AbstractUser
from django.db import models

MEMBERSHIP_ROLE_CHOICES = [
    ('owner', 'Owner'),
    ('admin', 'Admin'),
    ('manager', 'Manager'),
    ('viewer', 'Viewer'),
]


class User(AbstractUser):
    """Пользователь платформы. Один аккаунт — доступ к нескольким организациям."""
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']


class Membership(models.Model):
    """Связь пользователя с тенантом. Shared schema — виден из любого контекста."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    role = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_ROLE_CHOICES,
    )
    is_active = models.BooleanField(default=True)
    invite_token = models.UUIDField(null=True, blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'tenant')

    def __str__(self):
        return f'{self.user.email} → {self.tenant.name} ({self.role})'


class RolePermission(models.Model):
    """Матрица прав роли по CRM-сущностям внутри конкретной организации."""

    ENTITY_CHOICES = [
        ('deals', 'Deals'),
        ('contacts', 'Contacts'),
        ('companies', 'Companies'),
    ]
    SCOPE_CHOICES = [
        ('all', 'All records'),
        ('team', 'Team records'),
        ('own', 'Own records'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='role_permissions',
    )
    role = models.CharField(max_length=20, choices=MEMBERSHIP_ROLE_CHOICES)
    entity = models.CharField(max_length=20, choices=ENTITY_CHOICES)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='all')

    class Meta:
        unique_together = ('tenant', 'role', 'entity')
        indexes = [
            models.Index(fields=['tenant', 'role']),
            models.Index(fields=['tenant', 'entity']),
        ]

    def __str__(self):
        return f'{self.tenant.slug}:{self.role}:{self.entity}'

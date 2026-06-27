from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Domain, SigningTokenLookup, Tenant


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'slug', 'plan', 'is_active', 'created_at')
    list_filter = ('is_active', 'plan')
    search_fields = ('name', 'slug')
    readonly_fields = ('created_at',)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')
    list_filter = ('is_primary',)


@admin.register(SigningTokenLookup)
class SigningTokenLookupAdmin(admin.ModelAdmin):
    list_display = ('token', 'tenant', 'created_at', 'used_at')
    search_fields = ('token', 'tenant__slug', 'tenant__name')
    readonly_fields = ('created_at',)

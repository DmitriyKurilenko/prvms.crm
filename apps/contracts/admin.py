from django.contrib import admin
from .models import ContractTemplate, FieldMapping, Contract, SigningSession


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'is_active', 'created_at')
    list_filter = ('is_active',)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('id', 'template', 'status', 'signing_method', 'created_at', 'signed_at')
    list_filter = ('status', 'signing_method')
    readonly_fields = ('created_at',)


@admin.register(SigningSession)
class SigningSessionAdmin(admin.ModelAdmin):
    list_display = ('token', 'contract', 'otp_sent_to', 'attempts', 'verified_at')
    readonly_fields = ('token', 'otp_code_hash')

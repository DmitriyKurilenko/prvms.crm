from django.contrib import admin
from .models import DocumentTemplate, FieldMapping, Document, SigningSession


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'is_active', 'created_at')
    list_filter = ('is_active',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'document_type', 'template', 'status', 'signing_method', 'created_at', 'signed_at')
    list_filter = ('document_type', 'status', 'signing_method')
    readonly_fields = ('created_at',)


@admin.register(SigningSession)
class SigningSessionAdmin(admin.ModelAdmin):
    list_display = ('token', 'document', 'otp_sent_to', 'attempts', 'verified_at')
    readonly_fields = ('token', 'otp_code_hash')

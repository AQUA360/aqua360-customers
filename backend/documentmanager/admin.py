from django.contrib import admin

from .models import Document, DocumentSign

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id','entity', 'field', 'entity_id', 'document_name', 'location', 'service')
    list_filter = ('entity', 'field', 'entity_id', 'service')
    search_fields = ('entity', 'field', 'entity_id', 'document_name', 'location')

@admin.register(DocumentSign)
class DocumentSignAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'contract', 'contract_request', 'status', 'otp_name', 'otp_email', 'signed_at', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('token', 'otp_name', 'otp_email', 'otp_phone')

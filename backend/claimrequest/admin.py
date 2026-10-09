from django.contrib import admin
from .models import ClaimRequest, ClaimRequestStatus, ClaimRequestStepTemplate, ClaimRequestStep, ClaimDocumentType, ClaimRequestTemplate, VulnerabilityRequest, VulnerabilityRequestStatus, VulnerabilityRequestDocumentation, ClaimRequestPayment

@admin.register(ClaimRequest)
class ClaimRequestAdmin(admin.ModelAdmin):
    list_display = ('token', 'status', 'template', 'current_step', 'created_at')
    search_fields = ('token', 'description')
    list_filter = ('status', 'template')

@admin.register(ClaimRequestStatus)
class ClaimRequestStatusAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'color', 'position', 'is_default')
    search_fields = ('token', 'name')
    list_filter = ('is_default',)

@admin.register(ClaimRequestStepTemplate)
class ClaimRequestStepTemplateAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'template', 'position', 'duration', 'duration_type')
    search_fields = ('token', 'name')
    list_filter = ('template', 'duration_type')

@admin.register(ClaimRequestStep)
class ClaimRequestStepAdmin(admin.ModelAdmin):
    list_display = ('claim_request', 'step_template', 'position', 'is_completed', 'due_date')
    search_fields = ('claim_request__token', 'step_template__name')
    list_filter = ('is_completed', 'step_template__template')

@admin.register(ClaimDocumentType)
class ClaimDocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'position', 'is_default')
    search_fields = ('token', 'name')
    list_filter = ('is_default',)

@admin.register(ClaimRequestTemplate)
class ClaimRequestTemplateAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'is_default')
    search_fields = ('token', 'name')
    list_filter = ('is_default',)

@admin.register(VulnerabilityRequest)
class VulnerabilityRequestAdmin(admin.ModelAdmin):
    list_display = ('token', 'request_at', 'status', 'person', 'contract', 'created_at')
    search_fields = ('token', 'request_at', 'person__name', 'contract__token')
    list_filter = ('status', 'person', 'contract')

@admin.register(VulnerabilityRequestStatus)
class VulnerabilityRequestStatusAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'color', 'position', 'is_default')
    search_fields = ('token', 'name')
    list_filter = ('is_default',)

@admin.register(VulnerabilityRequestDocumentation)
class VulnerabilityRequestDocumentationAdmin(admin.ModelAdmin):
    list_display = ('vulnerability_request', 'file')

@admin.register(ClaimRequestPayment)
class ClaimRequestPaymentAdmin(admin.ModelAdmin):
    list_display = ('claim_request', 'payment', 'contract')
    search_fields = ('claim_request__token', 'payment__token', 'contract__token')
    list_filter = ('claim_request', 'payment', 'contract')

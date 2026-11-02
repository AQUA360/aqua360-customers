from django.contrib import admin

from .models import (
    ContractSigningSession,
    IntegrationRequestLog,
    SendBatch,
    SendBatchObservation,
    SendBatchProvider,
    SendBatchStatus,
    SendBatchType,
)


@admin.register(SendBatchProvider)
class SendBatchProviderAdmin(admin.ModelAdmin):
    list_display = ["token", "name", "position", "is_default", "updated_at"]
    search_fields = ["token", "name"]
    ordering = ["position", "token"]


@admin.register(SendBatchType)
class SendBatchTypeAdmin(admin.ModelAdmin):
    list_display = [
        "provider",
        "token",
        "name",
        "endpoint",
        "position",
        "is_default",
        "updated_at",
    ]
    list_filter = ["provider", "is_default"]
    search_fields = ["token", "name", "endpoint", "provider__token", "provider__name"]
    ordering = ["provider", "position", "token"]
    raw_id_fields = ["provider"]


@admin.register(SendBatchStatus)
class SendBatchStatusAdmin(admin.ModelAdmin):
    list_display = ["token", "name", "color", "position", "is_default", "updated_at"]
    search_fields = ["token", "name"]
    ordering = ["position", "token"]


@admin.register(SendBatch)
class SendBatchAdmin(admin.ModelAdmin):
    list_display = [
        "token",
        "batch_type",
        "billing",
        "instant_status_code",
        "status",
        "sent_at",
        "finished_at",
        "related_batch",
    ]
    list_filter = ["batch_type", "status", "instant_status_code"]
    search_fields = ["token", "billing__token"]
    raw_id_fields = ["billing", "related_batch"]
    filter_horizontal = ["invoices", "payments", "commitment_deposits"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SendBatchObservation)
class SendBatchObservationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "send_batch",
        "user",
        "is_important",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "is_important", "created_at"]
    search_fields = ["observation", "send_batch__token"]
    raw_id_fields = ["send_batch", "user"]


@admin.register(IntegrationRequestLog)
class IntegrationRequestLogAdmin(admin.ModelAdmin):
    list_display = [
        "provider",
        "direction",
        "method",
        "endpoint",
        "status_code",
        "success",
        "created_at",
    ]
    list_filter = [
        "provider",
        "direction",
        "success",
        "created_at",
    ]
    search_fields = [
        "provider",
        "endpoint",
        "error_message",
        "object_type",
        "object_id",
    ]
    readonly_fields = [
        "provider",
        "direction",
        "method",
        "endpoint",
        "request_payload",
        "response_payload",
        "status_code",
        "success",
        "error_message",
        "object_type",
        "object_id",
        "created_at",
    ]

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "provider",
                    "direction",
                    "method",
                    "endpoint",
                    "status_code",
                    "success",
                    "created_at",
                ]
            },
        ),
        (
            "Dades",
            {
                "fields": [
                    "request_payload",
                    "response_payload",
                    "error_message",
                    "object_type",
                    "object_id",
                ]
            },
        ),
    ]


@admin.register(ContractSigningSession)
class ContractSigningSessionAdmin(admin.ModelAdmin):
    list_display = [
        "session_id",
        "contract_request",
        "status",
        "recipient_email",
        "email_sent",
        "signed_at",
        "created_at",
    ]
    list_filter = ["status", "email_sent", "created_at"]
    search_fields = [
        "session_id",
        "external_reference",
        "recipient_name",
        "recipient_email",
        "contract_request__token",
    ]
    readonly_fields = [
        "session_id",
        "external_reference",
        "signing_url",
        "created_at",
        "updated_at",
    ]

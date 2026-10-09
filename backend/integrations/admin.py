from django.contrib import admin

from .models import ContractSigningSession, IntegrationRequestLog


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

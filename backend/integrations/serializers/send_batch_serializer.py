from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from integrations.models import (
    SendBatch,
    SendBatchObservation,
    SendBatchProvider,
    SendBatchStatus,
    SendBatchType,
)


class SendBatchProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SendBatchProvider
        fields = ["id", "token", "name", "position", "is_default"]


class SendBatchTypeSerializer(serializers.ModelSerializer):
    provider = SendBatchProviderSerializer(read_only=True)

    class Meta:
        model = SendBatchType
        fields = ["id", "provider", "token", "name", "position", "is_default"]


class SendBatchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SendBatchStatus
        fields = ["id", "token", "name", "color", "position", "is_default"]


class SendBatchObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)

    class Meta:
        model = SendBatchObservation
        fields = "__all__"


class SendBatchListSerializer(serializers.ModelSerializer):
    batch_type = SendBatchTypeSerializer(read_only=True)
    status = SendBatchStatusSerializer(read_only=True)
    invoices_count = serializers.SerializerMethodField()
    payments_count = serializers.SerializerMethodField()
    commitment_deposits_count = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    billing_token = serializers.CharField(
        source="billing.token", read_only=True, default=None, allow_null=True
    )
    related_batch_token = serializers.CharField(
        source="related_batch.token", read_only=True, default=None, allow_null=True
    )
    error_count = serializers.SerializerMethodField()
    ok_count = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    observations_count = serializers.SerializerMethodField()
    send_error = serializers.SerializerMethodField()

    class Meta:
        model = SendBatch
        fields = [
            "id",
            "token",
            "batch_type",
            "billing",
            "billing_token",
            "related_batch",
            "related_batch_token",
            "sent_at",
            "instant_status_code",
            "status",
            "received_at",
            "finished_at",
            "summary",
            "invoices_count",
            "payments_count",
            "commitment_deposits_count",
            "items_count",
            "error_count",
            "ok_count",
            "pending_count",
            "observations_count",
            "send_error",
            "created_at",
            "updated_at",
        ]

    def _annotated_or_count(self, obj, ann_attr, relation_name):
        value = getattr(obj, ann_attr, None)
        if value is not None:
            return value
        return getattr(obj, relation_name).count()

    def get_invoices_count(self, obj):
        return self._annotated_or_count(obj, "invoices_count_ann", "invoices")

    def get_payments_count(self, obj):
        return self._annotated_or_count(obj, "payments_count_ann", "payments")

    def get_commitment_deposits_count(self, obj):
        return self._annotated_or_count(
            obj, "commitment_deposits_count_ann", "commitment_deposits"
        )

    def get_items_count(self, obj):
        return (
            self.get_invoices_count(obj)
            + self.get_payments_count(obj)
            + self.get_commitment_deposits_count(obj)
        )

    def _summary_count(self, obj, key):
        summary = obj.summary or {}
        if isinstance(summary, dict) and key in summary:
            return summary.get(key) or 0
        results = (obj.final_response or {}).get("results") or []
        if key == "error":
            return sum(
                1 for r in results if isinstance(r, dict) and r.get("status") == "error"
            )
        if key == "ok":
            return sum(
                1
                for r in results
                if isinstance(r, dict) and r.get("status") in ("ok", "duplicate_ignored")
            )
        if key == "pending":
            return sum(
                1
                for r in results
                if isinstance(r, dict) and r.get("status") == "pending"
            )
        return 0

    def get_error_count(self, obj):
        return self._summary_count(obj, "error")

    def get_ok_count(self, obj):
        return self._summary_count(obj, "ok")

    def get_pending_count(self, obj):
        return self._summary_count(obj, "pending")

    def get_observations_count(self, obj):
        value = getattr(obj, "observations_count_ann", None)
        if value is not None:
            return value
        return obj.observations.filter(is_active=True).count()

    def get_send_error(self, obj):
        if obj.instant_status_code and obj.instant_status_code >= 400:
            payload = obj.instant_response or {}
            if isinstance(payload, dict):
                return payload.get("detail") or payload.get("message") or str(payload)
            return str(payload)
        if isinstance(obj.instant_response, dict) and obj.instant_response.get("detail"):
            if not obj.sent_at or (obj.instant_status_code in (None, 0)):
                return obj.instant_response.get("detail")
            if obj.instant_status_code and obj.instant_status_code >= 400:
                return obj.instant_response.get("detail")
        return None


class SendBatchDetailSerializer(SendBatchListSerializer):
    error_results = serializers.SerializerMethodField()
    receive_error = serializers.SerializerMethodField()

    class Meta(SendBatchListSerializer.Meta):
        fields = SendBatchListSerializer.Meta.fields + [
            "instant_response",
            "final_response",
            "error_results",
            "receive_error",
        ]

    def get_error_results(self, obj):
        results = (obj.final_response or {}).get("results") or []
        return [
            r for r in results if isinstance(r, dict) and r.get("status") == "error"
        ]

    def get_receive_error(self, obj):
        payload = obj.final_response
        if not isinstance(payload, dict):
            return None
        if payload.get("detail") and payload.get("status") not in (
            "done",
            "pending",
            "processing",
        ):
            return payload.get("detail")
        return None

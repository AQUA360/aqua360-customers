from rest_framework import serializers

from billing.serializers.reading_batch_serializer import ReadingBatchMinimalSerializer
from communication.serializers.communication_process_serializer import CommunicationProcessListSerializer
from service.serializers.route_serializer import RouteListSerializer
from ..models import Billing, BillingStatus, Invoice, Reading, ReadingBatch

class BillingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingStatus
        fields = '__all__'

class BillingListSerializer(serializers.ModelSerializer):
    status = BillingStatusSerializer(read_only=True, required=False, allow_null=True)
    send_at = serializers.SerializerMethodField()

    class Meta:
        model = Billing
        fields = '__all__'
        
    def get_send_at(self, obj):
        if hasattr(obj, 'effective_send_at'):
            return obj.effective_send_at
        if obj.send_at:
            return obj.send_at
        first_invoice = Invoice.objects.filter(billing=obj, send_at__isnull=False).first()
        return first_invoice.send_at if first_invoice else None

class BillingSerializer(serializers.ModelSerializer):
    routes = RouteListSerializer(many=True, read_only=True)
    status = BillingStatusSerializer(read_only=True, required=False, allow_null=True)
    communication_process = CommunicationProcessListSerializer(read_only=True, allow_null=True)
    total_invoices = serializers.SerializerMethodField()
    total_readings = serializers.SerializerMethodField()
    reading_batches = serializers.SerializerMethodField()
    send_at = serializers.SerializerMethodField()
    og_billing = serializers.SerializerMethodField()

    class Meta:
        model = Billing
        fields = '__all__'

    def validate_token(self, value):
        # Evita codis duplicats també en editar (a la creació ja ho valida
        # StartBillingView abans de crear el registre).
        if not value:
            return value

        queryset = Billing.objects.filter(token=value, is_active=True)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(f"Ja existeix una facturació amb el codi '{value}'.")

        return value

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['missing_batch'] = ReadingBatchMinimalSerializer(instance.missing_batch.all(), many=True).data if instance.missing_batch.all() else None
        return representation
    
    def get_og_billing(self, obj):
        
        first_billing_reading = obj.readings.select_related('batch').first()
        ref_batch = first_billing_reading.batch if first_billing_reading and first_billing_reading.batch and first_billing_reading.batch.billing_missing else None
        
        return {
            'id': ref_batch.id,
            'name': ref_batch.name,
            'token': ref_batch.token,
            'num_total_readings': ref_batch.readings.filter(copied_from__isnull=True).count(),
            'billing_missing_id': ref_batch.billing_missing.id if ref_batch and ref_batch.billing_missing else None,
            'billing_missing_name': ref_batch.billing_missing.name if ref_batch and ref_batch.billing_missing else None,
        } if ref_batch else None
    
    def get_send_at(self, obj):
        if hasattr(obj, 'effective_send_at'):
            return obj.effective_send_at
        if obj.send_at:
            return obj.send_at
        first_invoice = Invoice.objects.filter(billing=obj, send_at__isnull=False).first()
        return first_invoice.send_at if first_invoice else None
    
    def get_reading_batches(self, obj):
        batches = ReadingBatch.objects.filter(
            readings__billing=obj,
            is_active=True
        ).distinct()
        batch_data = []
        for batch in batches:
            batch_data.append({
                'id': batch.id,
                'token': batch.token,
                'created_at': batch.created_at,
                'status_name': batch.status.name,
                'status_color': batch.status.color,
                'num_total_readings': batch.readings.filter(copied_from__isnull=True).count(),
            })
        return batch_data
    
    def get_total_invoices(self, obj):
        return Invoice.objects.filter(
            billing=obj,
            is_active=True
        ).count()
        
    def get_total_readings(self, obj):
        return Reading.objects.filter(
            billing=obj,
            is_active=True
        ).count()
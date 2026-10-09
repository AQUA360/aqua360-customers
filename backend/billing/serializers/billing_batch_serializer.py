from rest_framework import serializers

from billing.serializers.invoice_serializer import InvoiceMinimalListSerializer
from service.models import Route
from service.serializers.route_serializer import RouteListSerializer


from ..models import BillingBatch, BillingBatchStatus
class BillingBatchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingBatchStatus
        fields = '__all__'
class BillingBatchSerializer(serializers.ModelSerializer):
    status = BillingBatchStatusSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = BillingBatch
        fields = '__all__'
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['num_invoices'] = instance.invoices.count()
        return representation

class BillingBatchProgressSerializer(serializers.ModelSerializer):
    invoices = InvoiceMinimalListSerializer(many=True, read_only=True, required=False, allow_null=True)
    class Meta:
        model = BillingBatch
        fields = '__all__'

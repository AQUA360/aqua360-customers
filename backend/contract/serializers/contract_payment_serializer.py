from rest_framework import serializers
from billing.models import Payment, PaymentStatus
from billing.serializers.value_objects_serializer import PaymentStatusSerializer, PaymentStatusMinimalSerializer

class ContractPaymentSerializer(serializers.ModelSerializer):
    status = PaymentStatusMinimalSerializer(read_only=True)
    invoice_id = serializers.IntegerField(source='invoice.id')
    invoice_token = serializers.CharField(source='invoice.token')
    invoice_serie_final = serializers.CharField(source='invoice.serie_final')
    
    class Meta:
        model = Payment 
        fields = ['id', 'token', 'status', 
                  'invoice_id', 'invoice_token', 'invoice_serie_final', 
                  'due_date', 'amount', 'payment_type', 
                  'payment_type_token', 'payment_bank']


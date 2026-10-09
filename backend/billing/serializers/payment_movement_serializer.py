from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from billing.serializers.payment_remittance_serializer import PaymentRemittanceSerializer
from billing.serializers.value_objects_serializer import PaymentStatusSerializer, RejectMotiveSerializer
from contract.serializers.value_objects_serializer import PaymentTypeSerializer
from ..models import PaymentMovement

class PaymentMovementSerializer(serializers.ModelSerializer):
    
    payment_type = PaymentTypeSerializer(read_only=True, required=False, allow_null=True)
    previous_status = PaymentStatusSerializer(read_only=True, required=False, allow_null=True)
    current_status = PaymentStatusSerializer(read_only=True, required=False, allow_null=True)
    reject_motive = RejectMotiveSerializer(read_only=True, required=False, allow_null=True)
    payment_remittance = PaymentRemittanceSerializer(read_only=True, required=False, allow_null=True)
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = PaymentMovement
        fields = '__all__'
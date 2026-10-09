from rest_framework import serializers
from ..models import ClaimRequestPayment
from billing.serializers.payment_serializer import PaymentMinimalSerializer
from contract.serializers.contract_serializer import ContractMinimalSerializer
from contract.models import Contract
from contract.serializers.value_objects_serializer import (
    ContractUseTypeSerializer,
    ContractClientTypeSerializer,
    ContractCategorySerializer,
    ContractDebtManagementSerializer,
    ContractStatusSerializer
)

class ClaimRequestPaymentSerializer(serializers.ModelSerializer):
    payment = PaymentMinimalSerializer(read_only=True)
    contract = ContractMinimalSerializer(read_only=True)
    
    joined_payment = serializers.SerializerMethodField()
    
    class Meta:
        model = ClaimRequestPayment
        fields = '__all__'
    
    def get_joined_payment(self, obj):
        joined_payment = obj.payment.joined_payments.filter(claim_request=obj.claim_request).first()
        return {
            'id': joined_payment.id,
            'token': joined_payment.token,
            'total_final': joined_payment.total_final
        } if joined_payment else None

class ClaimRequestPaymentMinimalSerializer(serializers.ModelSerializer):
    payment = PaymentMinimalSerializer(read_only=True)
    claim_step_id = serializers.IntegerField(source='claim_step.id', read_only=True)
    
    class Meta:
        model = ClaimRequestPayment
        fields = ['id', 'token', 'is_paid', 'is_excluded', 'is_vulnerable', 'payment', 'claim_step_id']

class ContractWithClaimPaymentsSerializer(serializers.ModelSerializer):
    is_excluded = serializers.SerializerMethodField()
    holder_name = serializers.CharField(source='holder.name', read_only=True)
    holder_surname = serializers.CharField(source='holder.surname', read_only=True)
    holder_token = serializers.CharField(source='holder.token', read_only=True)
    use_type = ContractUseTypeSerializer(read_only=True)
    client_type = ContractClientTypeSerializer(read_only=True)
    category = ContractCategorySerializer(read_only=True)
    debt_management = ContractDebtManagementSerializer(read_only=True)
    status = ContractStatusSerializer(read_only=True)
    
    class Meta:
        model = Contract
        fields = [
            'id', 'token', 'is_excluded',
            'holder_name', 'holder_surname', 'holder_token',
            'use_type', 'client_type', 'category', 'debt_management', 'status'
        ]
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['holder_vulnerability_level'] = instance.holder.vulnerability_level
        #representation['holder_is_vulnerable'] = instance.holder.is_vulnerable
        representation['holder_is_juridic'] = instance.holder.is_juridic
        
        claim_request_id = self.context.get('claim_request_id')
        step_id = self.context.get('step_id')
        claim_payments = []
        representation['claim_payments'] = []
        if claim_request_id:
            claim_payments = instance.claim_requests.filter(claim_request_id=claim_request_id)
            representation['claim_payments'] = ClaimRequestPaymentMinimalSerializer(claim_payments, many=True).data
            claim_step_payments = []
            if step_id:
                claim_step_payments = claim_payments.filter(claim_step__id=step_id)
            representation['has_claim_step_payments'] = len(claim_step_payments) > 0
        
        representation['pending_payments_amount'] = sum(claim_payment.payment.amount for claim_payment in claim_payments)
        representation['pending_payments_count'] = claim_payments.count()
        
        return representation
    
    def get_is_excluded(self, obj):
        claim_request_id = self.context.get('claim_request_id')
        if claim_request_id:
            claim_payments = obj.claim_requests.filter(claim_request_id=claim_request_id)
            # Si hi ha pagaments i tots estan exclosos, el contracte està exclòs
            return claim_payments.exists() and claim_payments.filter(is_excluded=False).count() == 0
        return False 
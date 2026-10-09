from rest_framework import serializers

from auth.serializers import UserMinimalSerializer


from ..models import ( PiggyBankMovement )

class PiggyBankMovementSerializer(serializers.ModelSerializer):
    payment = serializers.SerializerMethodField()
    user = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = PiggyBankMovement
        fields = '__all__'
    
    def get_payment(self, obj):
        from billing.serializers.payment_serializer import PaymentMinimalSerializer
        if obj.payment:
            return PaymentMinimalSerializer(obj.payment).data
        return None
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['bail'] = {
            'id': instance.bail.id,
            'token': instance.bail.token,
        } if instance.bail else None
        representation['commitment_deposit'] = {
            'id': instance.commitment_deposit.id,
            'token': instance.commitment_deposit.token,
        } if instance.commitment_deposit else None
        
        return representation

class PiggyBankMovementMinimalSerializer(serializers.ModelSerializer):
    piggy_bank_token = serializers.CharField(source='piggy_bank.token', read_only=True)
    piggy_bank_id = serializers.IntegerField(source='piggy_bank.id', read_only=True)
    payment_token = serializers.CharField(source='payment.token', read_only=True)
    payment_id = serializers.IntegerField(source='payment.id', read_only=True)
    
    class Meta:
        model = PiggyBankMovement
        fields = ['id', 'token', 'amount', 'is_positive', 'piggy_bank_token', 'piggy_bank_id', 'payment_token', 'payment_id']
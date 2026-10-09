from django.db.models import Sum
from rest_framework import serializers
from billing.models import PaymentRemittanceReturn
from billing.serializers.payment_serializer import PaymentSEPASerializer
from coredata.models import ConfigProject

class PaymentRemittanceReturnSerializer(serializers.ModelSerializer):
    payments = PaymentSEPASerializer(many=True, read_only=True)
    returned_by_username = serializers.CharField(source='returned_by.username', read_only=True)
    total_payments = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentRemittanceReturn
        fields = '__all__'
    
    def get_total_payments(self, obj):
        return obj.payments.count()
    
    def get_total_amount(self, obj):
        return obj.payments.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    

class PaymentRemittanceReturnListSerializer(serializers.ModelSerializer):
    returned_by_username = serializers.CharField(source='returned_by.username', read_only=True)
    total_payments = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentRemittanceReturn
        fields = '__all__'
    
    def get_total_payments(self, obj):
        return obj.payments.count()
    
    def get_total_amount(self, obj):
        return obj.payments.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    
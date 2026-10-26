from django.db.models import Sum
from rest_framework import serializers
from billing.models import PaymentRemittanceReturn
from billing.serializers.payment_serializer import PaymentSEPASerializer
from billing.utils.sepa_service import contract_holder_data
from coredata.models import ConfigProject


class PaymentSEPAReturnSerializer(PaymentSEPASerializer):
    # Afegeix el titular del contracte només al detall de retorns, per no
    # carregar les llistes de generació de remeses amb una consulta més per pagament
    def get_contract(self, obj):
        contract = super().get_contract(obj)
        if contract:
            holder = contract_holder_data(self._payment_contract(obj))
            contract['holder_name'] = holder['contract_holder_name']
            contract['holder_nif'] = holder['contract_holder_nif']
        return contract

    @staticmethod
    def _payment_contract(obj):
        return obj.invoice.contract if obj.invoice else obj.commitment_deposit.contract if obj.commitment_deposit else obj.contract


class PaymentRemittanceReturnSerializer(serializers.ModelSerializer):
    payments = PaymentSEPAReturnSerializer(many=True, read_only=True)
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
    
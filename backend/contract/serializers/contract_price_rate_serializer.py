from rest_framework import serializers
from billing.serializers.value_objects_serializer import PaymentStatusSerializer, PaymentStatusMinimalSerializer
from contract.models import ContractPriceRate
from pricing.serializers.price_rate_serializer import PriceRateSerializer

class ContractPriceRateSerializer(serializers.ModelSerializer):
    price_rate = PriceRateSerializer(read_only=True)
    supply_point = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractPriceRate
        fields = '__all__'
    
    def get_supply_point(self, obj):
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
        return SupplyPointMinimalSerializer(obj.supply_point).data


from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from billing.models import ConfigAca
from contract.serializers.value_objects_serializer import ContractUseTypeSerializer, VariableTypeSerializer
from coredata.serializers import ConfigProjectSerializer
from pricing.serializers.price_rate_serializer import PriceRateMinimalSerializer
from pricing.serializers.product_serializer import ProductListSerializer
from service.serializers.exploitation_serializer import ExploitationMinimalSerializer


class ConfigAcaSerializer(serializers.ModelSerializer):
    
    config_project = ConfigProjectSerializer(read_only=True)
    exploitation = ExploitationMinimalSerializer(read_only=True)
    
    contract_use_types = ContractUseTypeSerializer(many=True, read_only=True)
    price_rates = PriceRateMinimalSerializer(many=True, read_only=True)
    products = ProductListSerializer(many=True, read_only=True)
    variable_types = VariableTypeSerializer(many=True, read_only=True)
    
    user = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = ConfigAca
        fields = '__all__'
    
    def create(self, validated_data):
        instance = super().create(validated_data)
        return instance
    
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        return instance
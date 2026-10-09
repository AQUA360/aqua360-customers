from rest_framework import serializers

from contract.serializers.value_objects_serializer import BailStatusSerializer
from pricing.serializers.product_serializer import ProductMinimalSerializer

from ..models import ( Bail )

class BailSerializer(serializers.ModelSerializer):
    
    contract = serializers.SerializerMethodField()
    product = ProductMinimalSerializer(read_only=True, required=False, allow_null=True)
    invoice = serializers.SerializerMethodField()
    
    class Meta:
        model = Bail
        fields = '__all__'
    
    def get_contract(self, obj):
        from contract.serializers.contract_serializer import ContractListSerializer
        return ContractListSerializer(obj.contract).data
    
    def get_invoice(self, obj):
        from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
        return InvoiceMinimalSerializer(obj.invoice).data
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['status'] = BailStatusSerializer(instance.status).data
        return representation

class BailListSerializer(serializers.ModelSerializer):
    
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    contract_holder = serializers.CharField(source='contract.holder.name', read_only=True)
    contract_holder_surname = serializers.CharField(source='contract.holder.surname', read_only=True)
    contract_status_color = serializers.CharField(source='contract.status.color', read_only=True)
    contract_status_name = serializers.CharField(source='contract.status.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    
    class Meta:
        model = Bail
        fields = [
            'id', 'token', 'contract_token', 
            'contract_holder', 'status_name', 'status_color',
            'created_at', 'payment_date', 'amount',
            'contract_holder_surname', 'contract_status_color', 'contract_status_name',
            'product_name', 'return_date'
            ]

class BailMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bail
        fields = ['id', 'token', 'amount']
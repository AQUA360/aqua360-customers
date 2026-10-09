from rest_framework import serializers
from django_filters import rest_framework as filters

from contract.serializers.clause_template_serializer import ClauseTemplateSerializer
from pricing.serializers.price_rate_serializer import PriceRateSerializer
from ..models import ( ContractRequest, ContractRequestType )
from .value_objects_serializer import ContractRequestDocumentationTypeSerializer, VariableTypeSerializer
from order.serializers.value_objects_serializer import OrderTypeSerializer

class ContractRequestTypeSerializer(serializers.ModelSerializer):
    
    variable_types = VariableTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    documentation_types = ContractRequestDocumentationTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    order_types = OrderTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    clause_templates = serializers.SerializerMethodField()
    
    registration_price_rates = serializers.SerializerMethodField()
    price_rates = serializers.SerializerMethodField()
    #write only
    variable_types_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    order_types_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    clause_templates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    price_rates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    registration_price_rates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)

    
    class Meta:
        model = ContractRequestType
        fields = '__all__'


    def get_registration_price_rates(self, obj):
        return PriceRateSerializer(obj.registration_price_rates.filter(product__origin__token="contracte"), many=True).data

    def get_price_rates(self, obj):
        return PriceRateSerializer(obj.price_rates.filter(product__origin__token="aigua"), many=True).data

    def get_clause_templates(self, obj):
        # Logically deleted templates are hidden from the type and not copied into new requests
        return ClauseTemplateSerializer(obj.clause_templates.filter(is_active=True), many=True).data

    
    def update(self, instance, validated_data):
        variable_types_ids = validated_data.pop('variable_types_ids', None)
        order_types_ids = validated_data.pop('order_types_ids', None)
        clause_templates_ids = validated_data.pop('clause_templates_ids', None)
        price_rates_ids = validated_data.pop('price_rates_ids', None)
        registration_price_rates_ids = validated_data.pop('registration_price_rates_ids', None)
        
        instance = super().update(instance, validated_data)
        
        if variable_types_ids is not None:
            instance.variable_types.set(variable_types_ids)
        
        if order_types_ids is not None:
            instance.order_types.set(order_types_ids)
        
        if clause_templates_ids is not None:
            instance.clause_templates.set(clause_templates_ids)
        
        if price_rates_ids is not None:
            instance.price_rates.set(price_rates_ids)
        
        if registration_price_rates_ids is not None:
            instance.registration_price_rates.set(registration_price_rates_ids)
        
        instance.save()
        
        return instance


class ContractRequestTypeListSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ContractRequestType
        fields = '__all__'

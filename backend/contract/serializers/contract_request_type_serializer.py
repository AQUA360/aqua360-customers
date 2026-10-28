from django.db import transaction
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
    change_of_name_registration_price_rates = serializers.SerializerMethodField()
    price_rates = serializers.SerializerMethodField()
    #write only
    variable_types_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    order_types_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    clause_templates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    price_rates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    registration_price_rates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    change_of_name_registration_price_rates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)

    
    class Meta:
        model = ContractRequestType
        fields = '__all__'


    def get_registration_price_rates(self, obj):
        return PriceRateSerializer(obj.registration_price_rates.filter(product__origin__token="contracte"), many=True).data

    def get_change_of_name_registration_price_rates(self, obj):
        return PriceRateSerializer(obj.change_of_name_registration_price_rates.filter(product__origin__token="contracte"), many=True).data

    def get_price_rates(self, obj):
        return PriceRateSerializer(obj.price_rates.filter(product__origin__token="aigua"), many=True).data

    def get_clause_templates(self, obj):
        # Logically deleted templates are hidden from the type and not copied into new requests
        return ClauseTemplateSerializer(obj.clause_templates.filter(is_active=True), many=True).data

    
    # Camps d'escriptura amb els ids de cada relació M2M del tipus
    RELATION_IDS_FIELDS = {
        'variable_types_ids': 'variable_types',
        'order_types_ids': 'order_types',
        'clause_templates_ids': 'clause_templates',
        'price_rates_ids': 'price_rates',
        'registration_price_rates_ids': 'registration_price_rates',
        'change_of_name_registration_price_rates_ids': 'change_of_name_registration_price_rates',
    }

    def _pop_relation_ids(self, validated_data):
        return {relation: validated_data.pop(field, None) for field, relation in self.RELATION_IDS_FIELDS.items()}

    def _set_relations(self, instance, relation_ids):
        for relation, ids in relation_ids.items():
            if ids is not None:
                getattr(instance, relation).set(ids)

    @transaction.atomic
    def create(self, validated_data):
        relation_ids = self._pop_relation_ids(validated_data)
        instance = super().create(validated_data)
        self._set_relations(instance, relation_ids)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        relation_ids = self._pop_relation_ids(validated_data)
        instance = super().update(instance, validated_data)
        self._set_relations(instance, relation_ids)
        instance.save()
        return instance


class ContractRequestTypeListSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ContractRequestType
        fields = '__all__'

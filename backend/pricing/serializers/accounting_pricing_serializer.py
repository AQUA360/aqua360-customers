from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from contract.serializers.value_objects_serializer import PaymentTypeSerializer
from coredata.serializers import BankSerializer
from pricing.models import AccountingType, AccountingConcept, AccountingPricing, AccountingCostCenter, AccountingAdditionalLine
from pricing.serializers.line_item_type_serializer import LineItemTypeListSerializer
from pricing.serializers.price_interval_serializer import PriceIntervalSerializer
from pricing.serializers.price_rate_serializer import PriceRateMinimalSerializer
from pricing.serializers.price_variable_interval_serializer import PriceVariableIntervalSerializer
from pricing.serializers.product_serializer import ProductListSerializer
from pricing.serializers.value_objects_serializer import ProductOriginSerializer
from service.serializers.company_serializer import CompanyMinimalSerializer
from service.serializers.exploitation_serializer import ExploitationMinimalSerializer


class AccountingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingType
        fields = '__all__'

class AccountingCostCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingCostCenter
        fields = '__all__'


class AccountingConceptSerializer(serializers.ModelSerializer):
    type = AccountingTypeSerializer(read_only=True, required=False, allow_null=True)
    type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = AccountingConcept
        fields = '__all__'
    
    def create(self, validated_data):
        type_id = validated_data.pop('type_id', None)
        if type_id:
            type = AccountingType.objects.get(id=type_id)
            validated_data['type'] = type
        return super().create(validated_data)

    def update(self, instance, validated_data):
        type_id = validated_data.pop('type_id', None)
        if type_id:
            type = AccountingType.objects.get(id=type_id)
            validated_data['type'] = type
        return super().update(instance, validated_data)


class AccountingPricingListSerializer(serializers.ModelSerializer):
    
    created_by = serializers.CharField(read_only=True, source='user.username')
    last_updated_by = serializers.CharField(read_only=True, source='user.username')
    company_name = serializers.CharField(read_only=True, source='company.name')
    exploitation_name = serializers.CharField(read_only=True, source='exploitation.name')
    
    class Meta:
        model = AccountingPricing
        fields = '__all__'


class AccountingAdditionalLineSerializer(serializers.ModelSerializer):
    accounting_pricing = AccountingPricingListSerializer(read_only=True, required=False, allow_null=True)
    accounting_pricing_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    accounting_concept = AccountingConceptSerializer(read_only=True, required=False, allow_null=True)
    accounting_concept_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = AccountingAdditionalLine
        fields = '__all__'

    def create(self, validated_data):
        accounting_pricing_id = validated_data.pop('accounting_pricing_id', None)
        accounting_concept_id = validated_data.pop('accounting_concept_id', None)
        if accounting_pricing_id:
            validated_data['accounting_pricing'] = AccountingPricing.objects.get(id=accounting_pricing_id)
        if accounting_concept_id:
            validated_data['accounting_concept'] = AccountingConcept.objects.get(id=accounting_concept_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        accounting_pricing_id = validated_data.pop('accounting_pricing_id', None)
        accounting_concept_id = validated_data.pop('accounting_concept_id', None)
        if accounting_pricing_id is not None:
            validated_data['accounting_pricing'] = (
                AccountingPricing.objects.get(id=accounting_pricing_id) if accounting_pricing_id else None
            )
        if accounting_concept_id is not None:
            validated_data['accounting_concept'] = (
                AccountingConcept.objects.get(id=accounting_concept_id) if accounting_concept_id else None
            )
        return super().update(instance, validated_data)


class AccountingAdditionalLineNestedSerializer(serializers.ModelSerializer):
    accounting_concept = AccountingConceptSerializer(read_only=True, required=False, allow_null=True)

    class Meta:
        model = AccountingAdditionalLine
        fields = (
            'id',
            'token',
            'token_return',
            'name',
            'declared_as',
            'accounting_concept',
            'is_negative',
            'is_active',
            'created_at',
            'updated_at',
        )


class AccountingPricingSerializer(serializers.ModelSerializer):
    
    created_by = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    last_updated_by = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    accounting_concept = AccountingConceptSerializer(read_only=True, required=False, allow_null=True)
    accounting_cost_center = AccountingCostCenterSerializer(read_only=True, required=False, allow_null=True)
    
    origins = ProductOriginSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    products = ProductListSerializer(many=True, read_only=True, required=False, allow_null=True)
    price_rates = PriceRateMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    line_item_types = LineItemTypeListSerializer(many=True, read_only=True, required=False, allow_null=True)
    price_intervals = PriceIntervalSerializer(many=True, read_only=True, required=False, allow_null=True)
    price_variables = PriceVariableIntervalSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    payment_types = PaymentTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    banks = BankSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    company = CompanyMinimalSerializer(read_only=True, required=False, allow_null=True)
    exploitation = ExploitationMinimalSerializer(read_only=True, required=False, allow_null=True)
    aditional_lines = AccountingAdditionalLineNestedSerializer(many=True, read_only=True)

    class Meta:
        model = AccountingPricing
        fields = '__all__'

class AccountingPricingGroupedSerializer(serializers.Serializer):
    accounting_concept = AccountingConceptSerializer(read_only=True, allow_null=True)
    items = AccountingPricingSerializer(many=True, read_only=True)

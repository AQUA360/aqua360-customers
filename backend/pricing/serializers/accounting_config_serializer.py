from rest_framework import serializers

from pricing.models import AccountingConfig, AccountingPricing
from pricing.serializers.accounting_pricing_serializer import AccountingPricingListSerializer


class AccountingConfigSerializer(serializers.ModelSerializer):
    incoming_counter_pricing = AccountingPricingListSerializer(read_only=True, allow_null=True)
    return_counter_pricing = AccountingPricingListSerializer(read_only=True, allow_null=True)
    incoming_counter_pricing_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True,
    )
    return_counter_pricing_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True,
    )

    class Meta:
        model = AccountingConfig
        fields = (
            'id',
            'created_at',
            'updated_at',
            'piggybank_as_negative',
            'include_piggy_status_payments',
            'incoming_declare_as',
            'incoming_sign',
            'incoming_counter_declare_as',
            'incoming_counter_pricing',
            'incoming_counter_pricing_id',
            'return_declare_as',
            'return_sign',
            'return_counter_declare_as',
            'return_counter_pricing',
            'return_counter_pricing_id',
            'is_active',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def _set_pricing(self, validated_data, field_name, id_name):
        pricing_id = validated_data.pop(id_name, serializers.empty)
        if pricing_id is serializers.empty:
            return
        if pricing_id is None:
            validated_data[field_name] = None
        else:
            validated_data[field_name] = AccountingPricing.objects.get(id=pricing_id)

    def update(self, instance, validated_data):
        self._set_pricing(validated_data, 'incoming_counter_pricing', 'incoming_counter_pricing_id')
        self._set_pricing(validated_data, 'return_counter_pricing', 'return_counter_pricing_id')
        return super().update(instance, validated_data)

    def create(self, validated_data):
        self._set_pricing(validated_data, 'incoming_counter_pricing', 'incoming_counter_pricing_id')
        self._set_pricing(validated_data, 'return_counter_pricing', 'return_counter_pricing_id')
        return super().create(validated_data)

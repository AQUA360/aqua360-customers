from rest_framework import serializers

from logger.models import LogPriceRateChange

from ..models import PriceRate

from pricing.serializers.billing_range_serializer import BillingRangeSerializer
from pricing.serializers.translatable_mixin import TranslatableFieldMixin
from pricing.utils.return_fee_service import sync_return_fee_config
#from service.serializers import ExploitationMinimalSerializer
from .product_serializer import  ProductMinimalSerializer

def create_price_rate_log(instance, changed_field, previous_value, new_value, user, line_item_type_name = None):
    LogPriceRateChange.objects.create(
        object=instance,
        changed_field=changed_field,
        previous_value=str(previous_value) if previous_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        user=user,
        line_item_type_name=line_item_type_name
    )
class PriceRateSerializer(TranslatableFieldMixin, serializers.ModelSerializer):

    #exploitation = ExploitationMinimalSerializer(read_only=True, required=False, allow_null=True)
    product = ProductMinimalSerializer(read_only=True, required=False, allow_null=True)
    billing_ranges = BillingRangeSerializer(read_only=True, required=False, many=True, allow_null=True)
    billing_range_active = BillingRangeSerializer(read_only=True, required=False, allow_null=True)

    class Meta:
        model = PriceRate
        fields = '__all__'


class PriceRateSaveSerializer(TranslatableFieldMixin, serializers.ModelSerializer):

    token = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = PriceRate
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        is_return_fee = attrs.get(
            'is_return_fee',
            self.instance.is_return_fee if self.instance else False,
        )
        if is_return_fee:
            token = attrs.get('token', self.instance.token if self.instance else None)
            if not token:
                # Els ConfigProject de despeses de devolució guarden el token de
                # la tarifa: sense token la vinculació no es podria fer.
                raise serializers.ValidationError({
                    'token': "Cal un identificador per marcar la tarifa com a despeses de devolució."
                })
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        sync_return_fee_config(instance)
        return instance

    def update(self, instance, validated_data):
        translations = validated_data.pop('name_translations', None)
        user = self.context['request'].user
        for attr, value in validated_data.items():
            previous_value = getattr(instance, attr)
            if previous_value != value:
                create_price_rate_log(instance, attr, previous_value, value, user)
            setattr(instance, attr, value)

        instance.save()
        if translations is not None:
            self._apply_translations(instance, translations)
        # Es crida sempre, no només quan canvia `is_return_fee`: si la tarifa
        # marcada canvia de token, els ConfigProject han de seguir-lo.
        sync_return_fee_config(instance)
        return instance

class PriceRateMinimalSerializer(serializers.ModelSerializer):
    product = ProductMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = PriceRate
        fields = '__all__'

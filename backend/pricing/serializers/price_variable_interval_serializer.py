from rest_framework import serializers


from ..models import PriceVariableInterval
from .price_variable_interval_stretch_serializer import PriceVariableIntervalStretchSerializer

class PriceVariableIntervalSerializer(serializers.ModelSerializer):
    
    price_variable_interval_stretches = PriceVariableIntervalStretchSerializer(many=True, read_only=True)
    
    class Meta:
        model = PriceVariableInterval
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        line_items = []
        for line_item in instance.line_item_types.all():
            line_items.append({
                'id': line_item.id,
                'token': line_item.token,
                'name': line_item.name,
                'price_rate_name': line_item.billing_range.price_rate.name if line_item.billing_range and line_item.billing_range.price_rate else None,
            })
        representation['line_item_types'] = line_items
        return representation
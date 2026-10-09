from rest_framework import serializers
from ..models import OrderStatus, OrderType, OrderReason, OrderPriority

class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatus
        fields = '__all__'
class OrderReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderReason
        fields = '__all__'
        
class OrderReasonMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderReason
        fields = ['id', 'name']

class OrderTypeMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderType
        fields = ['id', 'name', 'token']
        
class OrderTypeSerializer(serializers.ModelSerializer):
    reasons = OrderReasonSerializer(many=True, read_only=True) 
    
    #write only
    order_reasons_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    class Meta:
        model = OrderType
        fields = '__all__'
    
    def update(self, instance, validated_data):
        order_reasons_ids = validated_data.pop('order_reasons_ids', None)
        
        instance = super().update(instance, validated_data)
        
        if order_reasons_ids is not None:
            instance.reasons.set(order_reasons_ids)
        
        return instance

class OrderPrioritySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderPriority
        fields = '__all__'
        
from rest_framework import serializers
from django_filters import rest_framework as filters

from billing.serializers.estimated_bag_movement_serializer import EstimatedBagMovementSerializer

from ..models import ( EstimatedBag )

class EstimatedBagSerializer(serializers.ModelSerializer):
    
    supply_point = serializers.SerializerMethodField()
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    
    class Meta:
        model = EstimatedBag
        fields = '__all__'
    
    def get_supply_point(self, obj):
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
        return SupplyPointMinimalSerializer(obj.supply_point).data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['movements'] = EstimatedBagMovementSerializer(instance.movements.all().order_by('-movement_date', '-created_at'), many=True).data
        return representation

class EstimatedBagMinimalSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = EstimatedBag
        fields = ['id', 'token', 'total_consumption']
from rest_framework import serializers

from service.models import Route
from service.serializers.route_serializer import RouteListSerializer
from ..models import Biller


def _with_exploitation(instance, representation):
    exploitation = instance.exploitation
    representation['exploitation_name'] = exploitation.name if exploitation else None
    representation['exploitation_token'] = exploitation.token if exploitation else None
    return representation

class BillerSerializer(serializers.ModelSerializer):
    
    # billing_batch_templates = BillingBatchTemplateSerializer(many=True, read_only=True)
    routes = RouteListSerializer(many=True, read_only=True)
    class Meta:
        model = Biller
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['num_routes'] = instance.routes.count()
        return _with_exploitation(instance, representation)

class BillerMinimalSerializer(serializers.ModelSerializer):
    
    route_ids = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all(), many=True, write_only=True, required=False, allow_null=True)
    
    # billing_batch_templates = BillingBatchTemplateSerializer(many=True, read_only=True, required=False, allow_null=True)
    class Meta:
        model = Biller
        fields = '__all__'

    def create(self, validated_data):
        route_ids = validated_data.pop('route_ids', [])  # Extract templates
        biller = Biller.objects.create(**validated_data)
        biller.routes.set(route_ids)
        return biller
    
    def update(self, instance, validated_data):
        route_ids = validated_data.pop('route_ids', None)  # Extract templates if provided
        instance = super().update(instance, validated_data)
        
        if route_ids is not None:
            instance.routes.set(route_ids)
            
        return instance
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['num_routes'] = instance.routes.count()
        return _with_exploitation(instance, representation)


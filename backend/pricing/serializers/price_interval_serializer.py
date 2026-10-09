from rest_framework import serializers


from ..models import PriceInterval
from .price_interval_stretch_serializer import PriceIntervalStretchSerializer

class PriceIntervalSerializer(serializers.ModelSerializer):
    
    price_interval_stretches = PriceIntervalStretchSerializer(many=True, read_only=True)
    
    class Meta:
        model = PriceInterval
        fields = '__all__'
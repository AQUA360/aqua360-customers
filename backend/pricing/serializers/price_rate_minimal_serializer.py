from rest_framework import serializers
from django.db import transaction

from ..models import PriceRate
from .product_serializer import  ProductMinimalSerializer

class PriceRateMinimalSerializer(serializers.ModelSerializer):
    product = ProductMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = PriceRate
        fields = '__all__'
    

from rest_framework import serializers
from django_filters import rest_framework as filters
from ..models import ( DMA )

class DMASerializer(serializers.ModelSerializer):
    class Meta:
        model = DMA
        fields = '__all__'
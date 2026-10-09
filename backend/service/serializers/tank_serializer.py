from rest_framework import serializers
from django_filters import rest_framework as filters
from ..models import ( Tank )

class TankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tank
        fields = '__all__'
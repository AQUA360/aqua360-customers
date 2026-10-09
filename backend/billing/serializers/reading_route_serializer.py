from rest_framework import serializers

from billing.serializers.reading_serializer import ReadingSerializer
from django.db.models import Count, Sum
from service.utils.route_positions_service import route_count_total_readings

from ..models import ReadingRoute


class ReadingRouteMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingRoute
        fields = '__all__'
        
        
class ReadingRouteSerializer(serializers.ModelSerializer):
    readings = ReadingSerializer(many=True, read_only=True, required=False, allow_null=True)
    class Meta:
        model = ReadingRoute
        fields = '__all__'
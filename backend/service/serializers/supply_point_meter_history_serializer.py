from rest_framework import serializers

from service.models import SupplyPointMeterHistory


class SupplyPointMeterHistorySerializer(serializers.ModelSerializer):
    """Fila de l'historial de canvis de comptador, per mostrar dins la fitxa del punt."""
    old_meter_code = serializers.CharField(source='old_meter.code', read_only=True, default=None)
    new_meter_code = serializers.CharField(source='new_meter.code', read_only=True, default=None)
    source_name = serializers.CharField(source='get_source_display', read_only=True)
    order_token = serializers.CharField(source='order.token', read_only=True, default=None)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = SupplyPointMeterHistory
        fields = [
            'id', 'created_at', 'change_date',
            'old_meter', 'old_meter_code', 'new_meter', 'new_meter_code',
            'old_reading', 'new_reading',
            'source', 'source_name', 'order', 'order_token',
            'user_name', 'observation',
        ]

    def get_user_name(self, obj):
        if not obj.user:
            return None
        return obj.user.get_full_name() or obj.user.username

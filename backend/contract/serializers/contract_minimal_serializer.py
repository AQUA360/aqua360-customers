from rest_framework import serializers

from billing.models import Reading
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
from ..models import Contract

class ContractMinimalSerializer(serializers.ModelSerializer):
    holder_token = serializers.CharField(read_only=True, source='holder.token', allow_null=True)
    holder_id = serializers.CharField(read_only=True, source='holder.id', allow_null=True)
    supply_points = serializers.SerializerMethodField()
    last_readings = serializers.SerializerMethodField()
    is_fire = serializers.BooleanField(read_only=True)
    class Meta:
        model = Contract
        fields = ['id', 'token', 'holder_token', 'holder_id', 'supply_points', 'last_readings', 'is_fire'] 
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.holder:
            representation['holder_full_name'] = f"{instance.holder.name} {instance.holder.surname}"
        else:
            representation['holder_full_name'] = ''
        return representation
    
    def get_supply_points(self, instance):
        return SupplyPointMinimalSerializer(instance.supply_points.all(), many=True, read_only=True).data
    
    def get_last_readings(self, instance):
        supply_points = instance.supply_points.all()
        readings = []
        for supply_point in supply_points:
            reading = Reading.objects.filter(
                supply_point=supply_point, contract=instance, is_active=True
            ).order_by('-reading_date').first()
            if reading:
                readings.append({
                    'id': reading.id,
                    "reading_date": reading.reading_date,
                    "reading_value": reading.reading_value,
                    "leak_value": reading.leak_value,
                    "calculated_value": reading.calculated_value,
                    "estimated_used": reading.estimated_used,
                    "supply_point": supply_point.id,
                    "meter": reading.meter.id if reading.meter else None,
                })
        return readings


class ContractMinimalNoSuppliesSerializer(serializers.ModelSerializer):
    holder_token = serializers.CharField(read_only=True, source='holder.token', allow_null=True)
    holder_id = serializers.CharField(read_only=True, source='holder.id', allow_null=True)
    status_token = serializers.CharField(read_only=True, source='status.token', allow_null=True)
    status_name = serializers.CharField(read_only=True, source='status.name', allow_null=True)
    status_color = serializers.CharField(read_only=True, source='status.color', allow_null=True)
    owner_id = serializers.CharField(read_only=True, source='owner.id', allow_null=True)
    tenant_id = serializers.CharField(read_only=True, source='tenant.id', allow_null=True)
    total_piggy_bank = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            'id',
            'token',
            'holder_token',
            'holder_id',
            'status_token',
            'status_name',
            'status_color',
            'owner_id',
            'tenant_id',
            'total_piggy_bank',
        ]

    def get_total_piggy_bank(self, instance):
        if instance.piggy_bank:
            return instance.piggy_bank.amount
        return 0

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.holder:
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder'] = f"{holder_name} {holder_surname}".strip()
        else:
            representation['holder'] = ''
        return representation
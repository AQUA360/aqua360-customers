from rest_framework import serializers

from billing.serializers.reading_batch_serializer import ReadingBatchMinimalSerializer
from billing.serializers.reading_serializer import ReadingMinimalSerializer
from coredata.utils.name_utils import generate_token
from statistics.models import ReadingBatchImportTemplate
from statistics.serializers import ReadingBatchImportTemplateSerializer
from ..models import ( Reading, ReadingDocument, ReadingDocumentNotFound )

class ReadingDocumentNotFoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingDocumentNotFound
        fields = '__all__'

class ReadingDocumentSerializer(serializers.ModelSerializer):

    #readings = ReadingMinimalSerializer(many=True, read_only=True)
    batch = ReadingBatchMinimalSerializer(read_only=True)
    template = serializers.PrimaryKeyRelatedField(
        queryset=ReadingBatchImportTemplate.objects.all(),
        required=False,
        allow_null=True,
    )
    # meters = serializers.SerializerMethodField()
    not_found_readings = ReadingDocumentNotFoundSerializer(many=True, read_only=True)
    status = serializers.CharField(read_only=True)
    task_id = serializers.CharField(read_only=True)
    processed_at = serializers.DateTimeField(read_only=True)
    last_preview = serializers.JSONField(read_only=True)
    auto_process = serializers.BooleanField(write_only=True, required=False, default=True)
    
    class Meta:
        model = ReadingDocument
        fields = [
            'id', 'created_at', 'updated_at', 'token', 'file', 'batch', 'template',
            'status', 'task_id', 'processed_at', 'last_preview', 'not_found_readings',
            'auto_process',
        ]
        
    def create(self, validated_data):
        validated_data.pop('auto_process', None)
        validated_data['token'] = generate_token(ReadingDocument)
        reding_document = ReadingDocument.objects.create(**validated_data)

        return reding_document

    def update(self, instance, validated_data):
        validated_data.pop('auto_process', None)
        return super().update(instance, validated_data)
    
    # def update(self, instance, validated_data):
        
    #     status_id = validated_data.get('status_id', None)
    #     if status_id:
    #         instance.status = ACADocumentStatus.objects.get(id=status_id)
    #         instance.save()
        
    #     return instance
    
    """ def get_meters(self, instance):
        from service.models import Meter
        meters = Meter.objects.filter(supply_points__in=instance.readings.all().values_list('supply_point', flat=True)).distinct()
        return meters.values_list('id',flat=True).distinct()
     """
    """ def get_meters(self, instance):
        from service.serializers.meter_serializer import MeterMinimalSerializer
        from service.models import Meter
        meters = Meter.objects.filter(supply_points__in=instance.readings.all().values_list('supply_point', flat=True)).distinct()
        meter_data = []
        for meter in meters:
            meter_data.append({
                'id': meter.id,
                'code': meter.code,
                'supply_points': [{'id': supply_point.id, 'token': supply_point.token} for supply_point in meter.supply_points.all()],
                'readings': [ {
                    'id': reading.id,
                    'reading_date': reading.reading_date,
                    'reading_value': reading.reading_value,
                    'calculated_value': reading.calculated_value,
                    'leak_value': reading.leak_value,
                    'is_control': reading.is_control,
                    'is_estimated': reading.is_estimated,
                    'origin': reading.origin,
                    'estimated_used': reading.estimated_used,
                    'alert': reading.alert.name if reading.alert else None,
                    'remote_alert': reading.remote_alert.name if reading.remote_alert else None,
                    } for reading in instance.readings.filter(meter=meter)],
            })
        return meter_data """
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['num_readings'] = instance.readings.count()
        if instance.template_id:
            representation['template'] = ReadingBatchImportTemplateSerializer(instance.template).data
        else:
            representation['template'] = None
        # last_preview pot ser molt gran (totes les entrades); al detall només
        # exposem metadades. El detall paginat/filtrat va per /validate/.
        last_preview = representation.get('last_preview')
        if isinstance(last_preview, dict):
            representation['last_preview'] = {
                'stats': last_preview.get('stats'),
                'total_rows': last_preview.get('total_rows'),
                'complete': last_preview.get('complete', False),
                'template_is_liters': last_preview.get('template_is_liters'),
            }
        return representation
    
    
class ReadingDocumentListSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReadingDocument
        fields = [
            'id', 'created_at', 'updated_at', 'token', 'file', 'batch', 'template',
            'status', 'task_id', 'processed_at',
        ]
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['num_readings'] = instance.readings.count()
        representation['num_not_found_readings'] = instance.not_found_readings.count()
        return representation
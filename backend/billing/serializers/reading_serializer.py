import uuid
from rest_framework import serializers

from billing.serializers.value_objects_serializer import RemoteReadingAlertSerializer
from contract.models import Contract
from coredata.models import ConfigProject
from service.models import Meter, SupplyPoint
from service.serializers.meter_serializer import MeterMinimalSerializer
from service.serializers.supply_point_serializer import SupplyPointAppSerializer, SupplyPointMinimalSerializer
from contract.serializers.contract_minimal_serializer import ContractMinimalNoSuppliesSerializer, ContractMinimalSerializer
from billing.utils.reading_service import calculate_estimated_bag, check_billing_period, copy_new_reading_to_all, get_existing_reading, get_reading_alerts_config, get_reading_minimal_object
from ..models import EstimatedBag, EstimatedBagMovement, InvoiceStatus, ReaderAlert, Reading, ReadingAlert

class ReaderAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReaderAlert
        fields = '__all__'
        
class ReadingAlertTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingAlert
        fields = '__all__'


class ReadingSerializer(serializers.ModelSerializer):
    
    meter = MeterMinimalSerializer(required=False, allow_null=True)
    supply_point = SupplyPointAppSerializer(required=False, allow_null=True)
    contract = ContractMinimalNoSuppliesSerializer(required=False, allow_null=True)
    #batch = ReadingBatchMinimalSerializer(required=False, allow_null=True)
    invoice = serializers.SerializerMethodField()
    reader_alert = ReaderAlertSerializer(required=False, allow_null=True)
    remote_alert = RemoteReadingAlertSerializer(required=False, allow_null=True)
    alert = serializers.SerializerMethodField()

    last_modified_reading = serializers.SerializerMethodField()
    original_reading = serializers.SerializerMethodField()
    pending_billing = serializers.SerializerMethodField()

    class Meta:
        model = Reading
        fields = '__all__'

    def get_alert(self, instance):
        return instance.alert.name if instance.alert else None

    def get_pending_billing(self, instance):
        config_status_tokens = [
            "billing_batch_processing_documents",
            "billing_batch_pending",
            "billing_batch_processing"
        ]
        billing_status_pending_token = ConfigProject.objects.filter(token__in=config_status_tokens).values_list('value', flat=True)
        
        return instance.billing.status.token in billing_status_pending_token if instance.billing else False
    
    def get_last_modified_reading(self, instance):
        last_modified_reading = instance.modified_readings.filter(is_control=False).first()
        return {
            'id': last_modified_reading.id,
            'reading_date': last_modified_reading.reading_date,
            'reading_value': last_modified_reading.reading_value,
            'leak_value': last_modified_reading.leak_value,
            'calculated_value': last_modified_reading.calculated_value,
            'meter_code': last_modified_reading.meter.code,
            } if last_modified_reading else None
    
    def get_original_reading(self, instance):
        original_reading = instance.original_readings.first()
        return {
            'id': original_reading.id,
            'reading_date': original_reading.reading_date,
            'reading_value': original_reading.reading_value,
            'leak_value': original_reading.leak_value,
            'calculated_value': original_reading.calculated_value,
            'meter_code': original_reading.meter.code,
        } if original_reading else None
    
    def get_invoice(self, instance):
        invoice_pending_status = ConfigProject.objects.get(token='invoice_status_pending_token').value
        invoice_cancelled_status = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
        invoices = instance.invoices.all().exclude(status__token__in=[invoice_pending_status, invoice_cancelled_status])
        if invoices.count() > 0:
            used_invoice = invoices.order_by('-created_at').first()
            return { 'id': used_invoice.id, 'token': used_invoice.token, 'number': used_invoice.number, 'status': used_invoice.status.token, 'serie_final': used_invoice.serie_final }
        return None

    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['batch'] = {'id': instance.batch.id, 'name': instance.batch.name, 'processed_at': instance.batch.processed_at, 'status_name': instance.batch.status.name, 'status_color': instance.batch.status.color } if instance.batch else None
        representation['real_consumption'] = instance.real_consumption if instance.real_consumption else instance.calculated_value
        representation['is_fire'] = instance.is_fire
        # Facturada = té factura definitiva (mateix criteri que BILLED_READING_FILTER). El
        # frontal ho fa servir per limitar quines lectures es poden triar com a inicials d'una alta.
        representation['is_billed'] = instance.invoices.filter(type_final='F').exists()
        return representation
    
    def update(self, instance, validated_data):

        reading = super().update(instance, validated_data)

        if 'reading_date' in validated_data and reading.batch_id:
            batch = reading.batch
            # La correccio (p.ex. omplir un reading_date que faltava) nomes arregla
            # la data: cal tornar a classificar la lectura (alert/consumption_days/
            # calculated_value) perque el processament original la va saltar per
            # l'excepcio, altrament compta erroniament com "correcta" als counters.
            try:
                alerts_cfg = get_reading_alerts_config()
                get_reading_minimal_object(
                    reading, reading.origin,
                    alerts_cfg['negative'], alerts_cfg['zero'], alerts_cfg['meter_cycle'],
                    alerts_cfg['unusual_consumption'], alerts_cfg['estimated'], batch,
                    alerts_cfg['min_consumption'], alerts_cfg['low_consumption'],
                )
            except Exception as e:
                print(f"Error recalculating reading after fix: {e}")

            if batch.last_task_errors:
                remaining_errors = [
                    err for err in batch.last_task_errors
                    if not (err.get('reading_id') == reading.id and err.get('code') == 'missing_reading_date')
                ]
                if len(remaining_errors) != len(batch.last_task_errors):
                    batch.last_task_errors = remaining_errors
                    batch.last_task_status = 'partial' if remaining_errors else 'ok'
                    batch.save(update_fields=['last_task_errors', 'last_task_status'])

        if instance.is_estimated:
            try:
                estimated_bag = EstimatedBag.objects.get(contract=instance.contract, supply_point=instance.supply_point)
                estimated_bag_movement = EstimatedBagMovement.objects.get(reading=instance)
                estimated_bag.total_consumption = estimated_bag.total_consumption - instance.calculated_value
                if estimated_bag.total_consumption < 0:
                    estimated_bag.total_consumption = 0
                estimated_bag.save()
                estimated_bag_movement.delete()
            except Exception as e:
                print(f"Error deleting estimated bag movement: {e}")
            print("estimated bag movement deleted")
            instance.is_estimated = False
            instance.save()
        
        if reading.calculated_value and reading.calculated_value < 0:
            original_calc = reading.calculated_value
            try:
                alert_token = ConfigProject.objects.get(token='reading_alert_negative').value
                reading.alert = ReadingAlert.objects.get(token=alert_token)
                reading.alert_notes = reading.alert.name
                reading.save(update_fields=['alert', 'alert_notes'])
            except:
                pass
            
        return reading
class ReadingSaveSerializer(serializers.ModelSerializer):
    
    meter = serializers.PrimaryKeyRelatedField(queryset=Meter.objects.all(), required=False, allow_null=True)
    supply_point = serializers.PrimaryKeyRelatedField(queryset=SupplyPoint.objects.all(), required=False, allow_null=True)
    contract = serializers.PrimaryKeyRelatedField(queryset=Contract.objects.all(), required=False, allow_null=True)
    #batch = ReadingBatchMinimalSerializer(required=False, allow_null=True)
    
    previous_reading_id = serializers.CharField(required=False, allow_null=True, write_only=True)
    add_to_all = serializers.BooleanField(required=False, allow_null=True, write_only=True)
    supply_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    
    class Meta:
        model = Reading
        fields = '__all__'
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['batch'] = {'id': instance.batch.id, 'name': instance.batch.name} if instance.batch else None
        return representation
    
    def create(self, validated_data):
        add_to_all = validated_data.pop('add_to_all', False)
        previous_reading_id = validated_data.pop('previous_reading_id', None)
        supply_id = validated_data.pop('supply_id', None)
        is_estimated = validated_data.get('is_estimated', False)
        meter = validated_data.get('meter', None)
        validated_data['origin'] = validated_data.get('origin', '-').upper()
        
        reading = None
        existing_reading = None
        
        previous_reading = None
        if previous_reading_id:
            previous_reading = Reading.objects.filter(id=previous_reading_id).first()
        
        if not previous_reading or previous_reading.reading_date > validated_data['reading_date']:
            previous_reading = Reading.objects.filter(
                supply_point=validated_data['supply_point'],
                meter=validated_data['meter'],
                reading_date__lt=validated_data['reading_date']).exclude(is_control=True).order_by('-reading_date').first()
        
        if previous_reading and not previous_reading.reading_value:
            existing_reading = previous_reading
            previous_reading = Reading.objects.filter(
                supply_point=validated_data['supply_point'],
                meter=validated_data['meter'],
                reading_value__isnull=False,
                reading_date__lt=validated_data['reading_date']).exclude(is_control=True).order_by('-reading_date').first()
        
        if not validated_data['is_control'] and previous_reading:
            if not existing_reading:
                validated_data['previous_reading'] = previous_reading
            validated_data['consumption_days'] = (validated_data['reading_date'] - previous_reading.reading_date).days
        
        
        if 'calculated_value' in validated_data and validated_data['calculated_value'] != None:
            validated_data['calculated_value'] = float(validated_data['calculated_value'])
        else:
            validated_data['calculated_value'] = validated_data['reading_value'] - previous_reading.reading_value if previous_reading and previous_reading.reading_value else validated_data['reading_value']
            if not previous_reading:   # first readings, either by new contract or changed meter
                validated_data['calculated_value'] = 0
        validated_data['real_consumption'] = validated_data['calculated_value'] - validated_data['estimated_used'] if 'estimated_used' in validated_data and validated_data['estimated_used'] > 0 else validated_data['calculated_value']
        
            
        if is_estimated:
            validated_data['reading_value'] = previous_reading.reading_value if previous_reading else 0
        
        if (previous_reading and previous_reading.contract != validated_data['contract']) or not previous_reading:
            validated_data['consumption_days'] = 0
            validated_data['real_consumption'] = 0
            validated_data['calculated_value'] = 0
            validated_data['is_initial'] = True
            validated_data['is_estimated'] = False
        
        if supply_id:
            readings = Reading.objects.filter(
                supply_point_id=supply_id, reading_date=validated_data['reading_date'])
            if meter:
                readings = readings.filter(meter=meter)
            for reading in readings:
                for key, value in validated_data.items():
                    if key not in ['supply_point', 'meter', 'contract', 'previous_reading']:
                        setattr(reading, key, value)
                reading = reading_update(previous_reading, reading, validated_data, add_to_all, is_estimated)
                reading.save()
                if reading.calculated_value and reading.calculated_value < 0:
                    original_calc = reading.calculated_value
                    try:
                        alert_token = ConfigProject.objects.get(token='reading_alert_negative').value
                        reading.alert = ReadingAlert.objects.get(token=alert_token)
                        reading.alert_notes = reading.alert.name
                        reading.save(update_fields=['alert', 'alert_notes'])
                    except:
                        pass
        else:
            if not existing_reading:
                new_reading = super().create(validated_data)
            else:
                new_reading = super().update(existing_reading, validated_data)
            reading = reading_update(previous_reading, new_reading, validated_data, add_to_all, is_estimated)
            if reading.calculated_value and reading.calculated_value < 0:
                original_calc = reading.calculated_value
                try:
                    alert_token = ConfigProject.objects.get(token='reading_alert_negative').value
                    reading.alert = ReadingAlert.objects.get(token=alert_token)
                    reading.alert_notes = reading.alert.name
                    reading.save(update_fields=['alert', 'alert_notes'])
                except:
                    pass
        
        
        if not reading:
            if not existing_reading:
                print("creating new reading")
                new_reading = super().create(validated_data)
            else:
                print("updating existing reading")
                new_reading = super().update(existing_reading, validated_data)
            reading = reading_update(previous_reading, new_reading, validated_data, add_to_all, is_estimated)
                
        return reading
    

def reading_update(previous_reading, reading, validated_data, add_to_all, is_estimated):
    has_future_reading = False
    contract = validated_data.get('contract', None)
    try:
        future_readings = future_reading = Reading.objects.filter(
            supply_point=validated_data['supply_point'],
            meter=validated_data['meter'],
            contract=validated_data['contract'],
            reading_date__gt=validated_data['reading_date'])
        if contract and future_readings.exists():
            future_readings = future_readings.filter(contract=contract)
        has_future_reading = future_readings.exists()
    except:
        pass
    if not has_future_reading and not reading.is_control:
        try:
            estimated_bags = EstimatedBag.objects.filter(
                supply_point=validated_data['supply_point'])
            if contract:
                estimated_bags = estimated_bags.filter(contract=contract)
        except:
            estimated_bags = []
        for estimated_bag in estimated_bags:
            calculate_estimated_bag(validated_data['calculated_value'], is_estimated, reading, estimated_bag)
            
    
    if 'is_control' in validated_data and not validated_data['is_control']:
        contract = validated_data.get('contract', None)
        # check if newly added reading has a reading with future reading date, not is_control, to set it as previous reading
        future_readings = Reading.objects.filter(
            supply_point=validated_data['supply_point'],
            meter=validated_data['meter'],
            reading_date__gt=validated_data['reading_date']).exclude(is_control=True).order_by('reading_date')
        if future_readings.exists() and contract:
            future_readings = future_readings.filter(contract=contract)
        future_reading = future_readings.first() if future_readings.exists() else None
        if future_reading:
            future_reading.previous_reading = previous_reading
    
    if add_to_all:
        copy_new_reading_to_all(reading, has_future_reading)
            
    return reading

class ReadingByBatchSerializer(serializers.ModelSerializer):
    contract = ContractMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = Reading
        fields = '__all__'
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        existing_reading = get_existing_reading(instance)
        representation['read1'] = existing_reading['read1']        
        representation['read2'] = existing_reading['read2']  
        representation['previous_leak'] = existing_reading['previous_leak']  
        representation['period_from'] = instance.previous_reading.reading_date if instance.previous_reading else None
        representation['period_to'] = instance.reading_date
        representation['is_fire'] = instance.is_fire
        return representation
class ReadingByBatchMinimalSerializer(serializers.ModelSerializer):
    contract = serializers.CharField(read_only=True, source='contract.token', required=False, allow_null=True)
    meter_code = serializers.CharField(read_only=True, source='meter.code', required=False, allow_null=True)
    meter_is_general = serializers.BooleanField(read_only=True, source='meter.is_general', required=False, allow_null=True)
    routeposition_code = serializers.CharField(
        read_only=True,
        source='supply_point.property.route_position.token',
        required=False,
        allow_null=True,
    )
    routeposition_position = serializers.IntegerField(
        read_only=True,
        source='supply_point.property.route_position.position',
        required=False,
        allow_null=True,
    )
    
    remote_alert_name = serializers.CharField(read_only=True, source='remote_alert.name', required=False, allow_null=True)
    reader_alert_name = serializers.CharField(read_only=True, source='reader_alert.name', required=False, allow_null=True)

    class Meta:
        model = Reading
        fields = '__all__'
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        existing_reading = get_existing_reading(instance)
        representation['read1'] = existing_reading['read1']        
        representation['read2'] = existing_reading['read2']  
        representation['previous_leak'] = existing_reading['previous_leak']  
        representation['period_from'] = instance.previous_reading.reading_date if instance.previous_reading else None
        representation['period_to'] = instance.reading_date
        representation['is_fire'] = instance.is_fire
        representation['in_communication_process'] = existing_reading['in_communication_process']
        alert_notes = representation['alert_notes']
        reader_alert = representation['reader_alert']
        remote_alert = representation['remote_alert']
        if not alert_notes and (reader_alert or remote_alert):
            representation['alert_notes'] = representation['reader_alert_name'] if reader_alert else representation['remote_alert_name'] if remote_alert else ''
            
        
        return representation

class ReadingMinimalSerializer(serializers.ModelSerializer):
    contract = ContractMinimalSerializer(required=False, allow_null=True)
    supply_point = SupplyPointMinimalSerializer(required=False, allow_null=True)
    original_reading = serializers.SerializerMethodField()
    class Meta:
        model = Reading
        fields = '__all__'
    
    def get_original_reading(self, instance):
        original_reading = instance.original_readings.first()
        return {
            'id': original_reading.id,
            'reading_date': original_reading.reading_date,
            'reading_value': original_reading.reading_value,
            'leak_value': original_reading.leak_value,
            'calculated_value': original_reading.calculated_value,
            'meter_code': original_reading.meter.code,
        } if original_reading else None
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['contract'] = representation['contract']['token'] if representation['contract'] else None
        representation['supply_point'] = representation['supply_point']['address_complete'] if representation['supply_point'] else None
        representation['meter_code'] = instance.meter.code if instance.meter else None
        representation['meter_caliber'] = instance.meter.caliber.token if instance.meter and instance.meter.caliber else None
        return representation
    
class HistoricReadingSerializer(serializers.ModelSerializer):
    contract = ContractMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = Reading
        fields = '__all__'
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['contract'] = representation['contract']['token'] if representation['contract'] else None
        representation['meter_code'] = instance.meter.code if instance.meter else None
        representation['meter_caliber'] = instance.meter.caliber.token if instance.meter and instance.meter.caliber else None
        representation['is_fire'] = instance.is_fire
        return representation

class ReadingDetailSerializer(serializers.ModelSerializer):
    contract = ContractMinimalSerializer(required=False, allow_null=True)
    supply_point = SupplyPointMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = Reading
        fields = '__all__'
    reading_history_page_size = 5

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['supply_point'] = representation['supply_point']
        representation['holder_id'] = instance.contract.holder.id

        # `-id` as a tie-breaker: several readings commonly share the exact same
        # `reading_date` (e.g. a whole reading batch on the same day), and without
        # a deterministic secondary key the DB doesn't guarantee the same order
        # across requests — offset-based pagination (`[start:end]` below) would
        # then return duplicated/skipped rows across pages for those ties.
        previous_readings = Reading.objects.filter(reading_date__lt=instance.reading_date).filter(supply_point=instance.supply_point, contract=instance.contract).order_by('-reading_date', '-id')

        request = self.context.get('request')
        try:
            page = max(1, int(request.query_params.get('page', 1))) if request else 1
        except (TypeError, ValueError):
            page = 1
        page_size = self.reading_history_page_size
        start = (page - 1) * page_size
        end = start + page_size

        representation['reading_history'] = {
            'count': previous_readings.count(),
            'results': HistoricReadingSerializer(previous_readings[start:end], many=True).data,
        }

        representation['meter_code'] = instance.meter.code if instance.meter else None
        representation['meter_caliber'] = instance.meter.caliber.token if instance.meter and instance.meter.caliber else None
        return representation
from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from billing.models import Reading
from coredata.models import ConfigProject, Person
from coredata.serializers import PersonSerializer
from coredata.utils.name_utils import generate_token
from service.models import SupplyPoint
from .value_objects_serializer import ContractTerminationRequestStatusSerializer, ContractTerminationRequestTypeSerializer
from order.serializers.order_serializer import OrderMinimalSerializer, OrderSerializer
from order.models import Order
from ..models import Contract, ContractTerminationRequest, ContractTerminationRequestObservation
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from billing.serializers.reading_serializer import ReadingMinimalSerializer
from billing.utils.invoice_service import reading_has_blocking_invoices

class ContractTerminationRequestObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = ContractTerminationRequestObservation
        fields = '__all__'


class ContractTerminationRequestSerializer(serializers.ModelSerializer):
    
    orders = OrderSerializer(many=True, read_only=True, required=False, allow_null=True)
    invoices = serializers.SerializerMethodField()
    readings = ReadingMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    contract_last_readings = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractTerminationRequest
        fields = '__all__'
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def get_contract_last_readings(self, obj):
        supply_points = obj.contract.supply_points.all()
        readings = []
        for supply_point in supply_points:
            reading = Reading.objects.filter(supply_point=supply_point, contract=obj.contract).order_by('-reading_date').first()
            if reading:
                readings.append({
                    'id': reading.id,
                    "reading_date": reading.reading_date,
                    "reading_value": reading.reading_value,
                    "leak_value": reading.leak_value,
                    "calculated_value": reading.calculated_value,
                    "estimated_used": reading.estimated_used,
                    "supply_point": supply_point.id,
                    "meter": reading.meter.id,
                })
        return readings
    
    def get_invoices(self, obj):
        from billing.models import Invoice
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        token_returned_invoice_serie = ConfigProject.objects.get(token='token_returned_invoice_serie').value
        invoice_data = []
        invoices = Invoice.objects.filter(contract_termination=obj, is_active=True).exclude(serie_token_final=token_returned_invoice_serie).distinct()
        for invoice in invoices:
            has_invoice = Invoice.objects.filter(budget_token=invoice.token, type__token=invoice_type_token).order_by('-created_at').first()
            invoice_data.append({
                'id': invoice.id,
                'token': invoice.token,
                'serie_final': invoice.serie_final,
                'title_final': invoice.title_final,
                'total_final': invoice.total_final,
                'status_name': invoice.status.name,
                'status_id': invoice.status.id,
                'status_token': invoice.status.token,
                'status_color': invoice.status.color,
                'type_token': invoice.type.token,
                'invoice_file_template': invoice.invoice_file_template is not None,
                'invoice_file': invoice.invoice_file.id if invoice.invoice_file else None,
                'budget_token': invoice.budget_token,
                'has_invoice': has_invoice is not None,
                'refactored_token': invoice.refactored_token,
                'entity': 'contract_termination_request',
                'object_id': obj.id,
                'type_token': invoice.type.token
            })
        return invoice_data
        
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        ContractSerializer = import_string('contract.serializers.contract_serializer.ContractSerializer')
        
        representation['contract'] = ContractSerializer(instance.contract, context=self.context).data if instance.contract else None
        representation['person'] = PersonSerializer(instance.person, context=self.context).data if instance.person else None
        representation['type'] = ContractTerminationRequestTypeSerializer(instance.type).data
        representation['status'] = ContractTerminationRequestStatusSerializer(instance.status).data
        return representation
    
class ContractTerminationRequestMinimalSerializer(serializers.ModelSerializer):
    
    orders = OrderMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    readings = ReadingMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = ContractTerminationRequest
        fields = '__all__'
    
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['person'] = PersonSerializer(instance.person, context=self.context).data if instance.person else None
        representation['type'] = ContractTerminationRequestTypeSerializer(instance.type).data
        representation['status'] = ContractTerminationRequestStatusSerializer(instance.status).data
        return representation
        
class ContractTerminationRequestSaveSerializer(serializers.ModelSerializer):
    last_reading = serializers.FloatField(required=False, allow_null=True)
    last_leak_reading = serializers.FloatField(required=False, allow_null=True)
    last_reading_at = serializers.DateTimeField(required=False, allow_null=True)
    supply_point_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    meter_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    orders = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), many=True, required=False, allow_null=True)

    
    class Meta:
        model = ContractTerminationRequest
        fields = '__all__'
    
    def create(self, validated_data):
        token = generate_token(ContractTerminationRequest)
        validated_data['token'] = token
        orders = validated_data.pop('orders', [])
        instance = super().create(validated_data)
        if orders:
            instance.orders.set(orders)
        return instance
    
    def update(self, instance, validated_data):
        orders = validated_data.pop('orders', None)
        if orders is not None:
            instance.orders.set(orders)

        if 'termination_file' in validated_data:
            termination_file = validated_data.pop('termination_file')
            instance.termination_file = termination_file
            instance.save()
            return instance
        
        last_reading = validated_data.get('last_reading', None)
        last_leak_reading = validated_data.get('last_leak_reading', None)
        last_reading_at = validated_data.get('last_reading_at', None)
        supply_point_id = validated_data.get('supply_point_id', None)
        meter_id = validated_data.get('meter_id', None)
        
        #readings = validated_data.get('readings', None) #avoid update error
        
        if last_reading != None and last_reading_at:
            from billing.models import Reading
            supply_point = SupplyPoint.objects.get(id=supply_point_id)
            existing_reading = Reading.objects.filter(
                supply_point=supply_point, reading_date=last_reading_at, contract=instance.contract, is_close=False
                ).exclude(is_control=True).exclude(is_initial=True)
            if meter_id:
                existing_reading = Reading.objects.filter(
                    supply_point=supply_point, meter__id=meter_id, reading_date=last_reading_at, contract=instance.contract, is_close=False
                    ).exclude(is_control=True).exclude(is_initial=True)
            if existing_reading.exists() and existing_reading.first() and not reading_has_blocking_invoices(existing_reading.first()):
                ex_reading = existing_reading.first()
                ex_reading.reading_value = last_reading
                ex_reading.leak_value = last_leak_reading if last_leak_reading else 0
                ex_reading.calculated_value = float(last_reading) - float(ex_reading.previous_reading.reading_value) if ex_reading.previous_reading else float(last_reading)
                ex_reading.real_consumption = float(ex_reading.calculated_value) - float(ex_reading.estimated_used if ex_reading.estimated_used else 0)
                ex_reading.save()
                new_reading = ex_reading
            elif existing_reading.exists() and existing_reading.first():
                # The reading for this date already has non-cancelled invoices linked to it
                # (e.g. it was already billed by an ordinary billing cycle). Mutating it here
                # would silently change the consumption of an already-issued invoice, so
                # instead we create a new reading that only carries the not-yet-billed delta,
                # chained after the already-billed one.
                ex_reading = existing_reading.first()
                total_days = (last_reading_at.date() - ex_reading.reading_date.date()).days if hasattr(ex_reading.reading_date, 'date') else (last_reading_at.date() - ex_reading.reading_date).days
                reading_data = {
                    'token': f"{supply_point.meter.code}/MANUAL",
                    'reading_date': last_reading_at,
                    'reading_value': last_reading,
                    'leak_value': last_leak_reading if last_leak_reading else 0,
                    'origin': 'Manual',
                    'calculated_value': float(last_reading) - float(ex_reading.reading_value),
                    'supply_point': supply_point,
                    'meter': ex_reading.meter,
                    'previous_reading': ex_reading,
                    'consumption_days': total_days,
                    'contract': instance.contract,
                    'is_control': False,
                    'is_estimated': False,
                    'is_active': True,
                }
                new_reading = Reading.objects.create(**reading_data)
                new_reading.real_consumption = float(new_reading.calculated_value) - float(new_reading.estimated_used if new_reading.estimated_used else 0)
                new_reading.save()
            else:
                previous_reading = Reading.objects.filter(
                    supply_point=supply_point, reading_date__lt=last_reading_at, contract=instance.contract
                    ).exclude(is_control=True).order_by('-reading_date').first()
                if meter_id:
                    previous_reading = Reading.objects.filter(
                        supply_point=supply_point, meter__id=meter_id, reading_date__lt=last_reading_at, contract=instance.contract
                        ).exclude(is_control=True).order_by('-reading_date').first()
                
                if previous_reading.reading_value == None:
                    og_previous_reading = previous_reading
                    previous_reading = og_previous_reading.previous_reading
                    og_previous_reading.is_control = True
                    og_previous_reading.save()
                
                total_days = (last_reading_at.date() - previous_reading.reading_date).days if previous_reading else 0
                reading_data = {
                    'token': f"{supply_point.meter.code}/MANUAL",
                    'reading_date': last_reading_at,
                    'reading_value': last_reading,
                    'leak_value': last_leak_reading,
                    'origin': 'Manual',
                    'calculated_value': float(last_reading) - float(previous_reading.reading_value) if previous_reading else float(last_reading),
                    'supply_point': supply_point,
                    'meter': previous_reading.meter if previous_reading else supply_point.meter,
                    'previous_reading': previous_reading,
                    'consumption_days': total_days,
                    'contract': instance.contract,
                    'is_control': False,
                    'is_estimated': False,
                    'is_active': True,
                }
                new_reading = Reading.objects.create(**reading_data)
            
            instance_readings = instance.readings.all()
            #check if reading with same supply point and meter already exists, if they do, remove it from intance
            for reading in instance_readings:
                if reading.supply_point.id == supply_point.id and reading.meter.id == supply_point.meter.id:
                    instance.readings.remove(reading)
            instance.readings.add(new_reading)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance
    
class ContractTerminationRequestListSerializer(serializers.ModelSerializer):
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    contract_name = serializers.CharField(source='contract.name', read_only=True)
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_surname = serializers.CharField(source='person.surname', read_only=True)
    
    class Meta:
        model = ContractTerminationRequest
        fields = [
            'id',
            'token',
            'created_at',
            'approved_at',
            'status_token',
            'status_name',
            'status_color',
            'contract_name',
            'contract_token',
            'person_name',
            'person_surname',
            'ignore_invoice',
        ]
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
      
        if instance.contract and instance.contract.supply_point_default:
            representation['supply_point'] = str(instance.contract.supply_point_default.address)
        
        from billing.models import Invoice
        invoices = Invoice.objects.filter(contract_termination=instance)
        representation['has_invoice'] = False
        
        if instance.contract.holder:
            representation['holder_name'] = f"{instance.contract.holder.name} {instance.contract.holder.surname}" if instance.contract.holder.surname else instance.contract.holder.name
        
        if invoices.count() > 0:
            invoice_type_invoice_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
            invoice_status_cancelled_token = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
            final_invoice = invoices.filter(type__token=invoice_type_invoice_token).exclude(status__token=invoice_status_cancelled_token).first()
            if final_invoice:
                representation['has_invoice'] = True

        return representation

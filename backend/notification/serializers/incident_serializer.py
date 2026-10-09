from rest_framework import serializers
from django_filters import rest_framework as filters

from auth.serializers import UserMinimalSerializer
from billing.serializers.commitment_deposit_serializer import CommitmentDepositListSerializer
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from coredata.utils.name_utils import generate_token
from logger.models import LogIncidentStatusChange
from notification.serializers.calendar_task_serializer import CalendarTaskSerializer
from notification.serializers.value_objects_serializer import IncidentReportSerializer, IncidentStatusSerializer, IncidentTypeSerializer
from order.serializers.order_serializer import OrderMinimalSerializer
from service.serializers.cluster_serializer import ClusterListSerializer
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
from ..models import *

class IncidentObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = IncidentObservation
        fields = '__all__'

class IncidentSerializer(serializers.ModelSerializer):
    
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    invoice = InvoiceMinimalSerializer(read_only=True, required=False, allow_null=True)
    commitment_deposit = CommitmentDepositListSerializer(read_only=True, required=False, allow_null=True)
    order_incident = OrderMinimalSerializer(read_only=True, required=False, allow_null=True)
    supply_point = SupplyPointMinimalSerializer(read_only=True, required=False, allow_null=True)
    cluster = ClusterListSerializer(read_only=True, required=False, allow_null=True)
    orders = OrderMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    reports = IncidentReportSerializer(many=True, read_only=True, required=False, allow_null=True)
    status = IncidentStatusSerializer(read_only=True, required=False, allow_null=True)
    type = IncidentTypeSerializer(read_only=True, required=False, allow_null=True)
    tasks = CalendarTaskSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Incident
        fields = '__all__'


class IncidentListSerializer(serializers.ModelSerializer):
    
    status_color = serializers.CharField(source='status.color', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    type_name = serializers.CharField(source='type.name', read_only=True)
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    invoice_token = serializers.CharField(source='invoice.token', read_only=True)
    order_token = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    supply_point = SupplyPointMinimalSerializer(read_only=True, required=False, allow_null=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'token', 'name',
            'status_color', 'status_name',
            'contract_token', 'invoice_token',
            'total_tasks', 'type_name', 'created_at',
            'order_token', 'supply_point'
        ]
    
    def get_total_tasks(self, obj):
        return obj.tasks.count()
    
    def get_order_token(self, obj):
        if obj.order_incident:
            return obj.order_incident.token
        # Si no té order_incident, mirem si té ordres vinculades a través de Order.incident
        first_order = obj.orders.first()
        return first_order.token if first_order else None
    
        
class IncidentSaveSerializer(serializers.ModelSerializer):
    
    
    new_task = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = Incident
        fields = '__all__'
    
    def create(self, validated_data):
        default_status = IncidentStatus.objects.get(is_default=True)
        validated_data['token'] = generate_token(Incident)
        validated_data['status'] = default_status
        
        commitment = validated_data.get('commitment_deposit', None)
        invoice = validated_data.get('invoice', None)
        order = validated_data.get('order_incident', None)
        if commitment:
            validated_data['contract'] = commitment.contract
        if invoice:
            validated_data['contract'] = invoice.contract if invoice.contract else None
        if order:
            validated_data['contract'] = order.contract if order.contract else None
        
        incident = Incident.objects.create(**validated_data)
        
        LogIncidentStatusChange.objects.create(
            object=incident, 
            current_status=default_status,
            user = self.context.get('request').user if self.context.get('request') else None
            )
        
        return incident

    def update(self, instance, validated_data):
        print("updating incident")
        print(validated_data)
        new_task = validated_data.pop('new_task', None)
        
        if new_task:
            task = CalendarTask.objects.get(id=new_task)
            instance.tasks.add(task)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance
        
class IncidentAppSerializer(serializers.ModelSerializer):
    
    category_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    category_name = serializers.CharField(write_only=True, required=False, allow_null=True)
    title = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Incident
        fields = '__all__'
    
    def create(self, validated_data):
        default_status = IncidentStatus.objects.get(is_default=True)
        validated_data['token'] = generate_token(Incident)
        validated_data['status'] = default_status
        
        category_token = validated_data.pop('category_token', None)
        category_name = validated_data.pop('category_name', None)
        title = validated_data.pop('title', None)
        if title:
            validated_data['name'] = title
        
        incident = Incident.objects.create(**validated_data)
        
        if category_token and category_name:
            existing = IncidentType.objects.filter(token=category_token).first()
            if existing:
                type = existing
            else:
                type = IncidentType.objects.create(token=category_token, name=category_name)
            
        incident.type = type    
        incident.save()
        
        LogIncidentStatusChange.objects.create(
            object=incident, 
            current_status=default_status,
            user = None
            )
        
        return incident
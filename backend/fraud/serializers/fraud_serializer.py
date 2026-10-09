import datetime
from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from contract.serializers.contract_serializer import ContractMinimalSerializer
from coredata.models import ConfigProject
from fraud.models import *
from fraud.serializers.value_objects_serializer import *
from logger.models import LogFraudStatusChange
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer

class FraudObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    
    class Meta:
        model = FraudObservation
        fields = '__all__'

class FraudSerializer(serializers.ModelSerializer):
    
    status = FraudStatusSerializer(read_only=True, required=False, allow_null=True)
    type = FraudTypeSerializer(read_only=True, required=False, allow_null=True)
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    supply_point = SupplyPointMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Fraud
        fields = '__all__'

class FraudSaveSerializer(serializers.ModelSerializer):
    
    status_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta: 
        model = Fraud
        fields = '__all__'
    
    def create(self, validated_data):
        default_status = FraudStatus.objects.get(is_default=True)
        now = datetime.date.today().strftime('%Y%m%d')
        
        validated_data['token'] = f"{now}{validated_data['supply_point'].token}"
        validated_data['status'] = default_status
        
        fraud = Fraud.objects.create(**validated_data)
        
        LogFraudStatusChange.objects.create(
            object=fraud,
            previous_status=None,
            current_status=default_status,
            user=self.context['request'].user,
            timestamp=datetime.datetime.today()
        )
        
        return fraud
    
    def update(self, instance, validated_data):
        status_token = validated_data.pop('status_token', None)
        
        if status_token:
            status_instance = FraudStatus.objects.get(token=status_token)
            LogFraudStatusChange.objects.create(
                object=instance,
                previous_status=instance.status,
                current_status=status_instance,
                user=self.context['request'].user,
                timestamp=datetime.datetime.today()
            )
            instance.status = status_instance
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance
            
        
class FraudListSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    supply_point_token = serializers.CharField(source='supply_point.token', read_only=True)
    type_name = serializers.CharField(source='type.name', read_only=True)
    
    class Meta:
        model = Fraud
        fields = [
            'id',
            'token',
            'created_at',
            'detection_date',
            'status_name',
            'status_color',
            'contract_token',
            'supply_point_token',
            'is_dismissed',
            'type_name'
        ]
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        try:
            supply_point = SupplyPoint.objects.get(id=instance.supply_point_id)
            if supply_point:
                representation['supply_point'] = str(supply_point.address)
        except:
            print("supply_point not loaded")
            
        reports = FraudReport.objects.filter(fraud=instance)
        representation['total_reports'] = len(reports)
        
        
        return representation
from rest_framework import serializers
from django.db import transaction
from django.db.models import Max
from contract.models import VariableType
from contract.serializers.value_objects_serializer import VariableTypeSerializer
from coredata.utils.name_utils import generate_token
from pricing.serializers.value_objects_serializer import AdjustmentIntervalStretchSerializer, AdjustmentOperationSerializer, VariableCalculationSerializer
from pricing.utils.adjustment_service import updateAdjustmentPreferences

from ..models import Adjustment, AdjustmentOperation, LineItemType, PriceInterval, VariableCalculation, AdjustmentCondition

from .price_interval_serializer import PriceIntervalSerializer

class AdjustmentConditionSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = AdjustmentCondition
        fields = '__all__'

class AdjustmentSerializer(serializers.ModelSerializer):
    adjustment_interval_stretches = AdjustmentIntervalStretchSerializer(many=True, read_only=True, required=False, allow_null=True)
    conditions = AdjustmentConditionSerializer(many=True, read_only=True, required=False, allow_null=True)
    line_item_type_name = serializers.CharField(source='line_item_type.name', read_only=True)
    variable_type = VariableTypeSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Adjustment
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["operation"] = AdjustmentOperationSerializer(instance.operation).data
        representation["variable_calculation"] = VariableCalculationSerializer(instance.variable_calculation).data
        return representation
    
    
class AdjustmentSaveSerializer(serializers.ModelSerializer):
    operation_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    variable_calculation_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    line_item_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Adjustment
        fields = '__all__'
        
    @transaction.atomic
    def create(self, validated_data):
        
        operation = validated_data.pop('operation_token', None)
        variable_calculation = validated_data.pop('variable_calculation_token', None)
        line_item_type_id = validated_data.pop('line_item_type_id', None)
        
        token = generate_token(Adjustment)
        validated_data['token'] = token
        
        if line_item_type_id:
            line_item_type = LineItemType.objects.get(id=line_item_type_id)
            validated_data['line_item_type'] = line_item_type
        
        if operation:
            validated_data['operation'] = AdjustmentOperation.objects.get(token=operation)
        
        if variable_calculation and variable_calculation != '-':
            validated_data['variable_calculation'] = VariableCalculation.objects.get(token=variable_calculation)
            
        # When creating a new object, I want to set its preference to the highest value + 1
        position = Adjustment.objects.filter(line_item_type=line_item_type).aggregate(Max('position'))['position__max']
        if position:
            validated_data['position'] = position + 1
        else:
            validated_data['position'] = 1
        
        
        return super(AdjustmentSaveSerializer, self).create(validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        print('in update')
        print(validated_data)
        operation = validated_data.pop('operation_token', None)
        variable_calculation = validated_data.pop('variable_calculation_token', None)
        line_item_type_id = validated_data.pop('line_item_type_id', None)
        position = validated_data.pop('position', None)
        # quantity = validated_data.pop('quantity', None)
        
        # Actualitzar camps de ContractRequest
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if line_item_type_id:
            line_item_type = LineItemType.objects.get(id=line_item_type_id)
            instance.line_item_type = line_item_type
        
        if operation:
            instance.operation = AdjustmentOperation.objects.get(token=operation)
        
        if variable_calculation and variable_calculation != '-':
            instance.variable_calculation = VariableCalculation.objects.get(token=variable_calculation)
        elif variable_calculation and variable_calculation == '-':
            instance.variable_calculation = None
        print("doing adjustment")
        if position:
            instance.position = position
        instance.save()
        #adjustment = updateAdjustmentPreferences(instance.id, position)
        print(instance.__dict__)
        
        
        return instance
from rest_framework import serializers
from ..models import ( BonificationType )
from .value_objects_serializer import VariableTypeSerializer
from .value_objects_serializer import BonificationTypeDocumentationTypeSerializer

class BonificationTypeSerializer(serializers.ModelSerializer):
    
    variable_types = VariableTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    bonification_type_documentation_types = BonificationTypeDocumentationTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    #write only
    variable_types_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    class Meta:
        model = BonificationType
        fields = '__all__'

    def update(self, instance, validated_data):
        variable_types_ids = validated_data.pop('variable_types_ids', None)
        
        instance = super().update(instance, validated_data)
        
        if variable_types_ids is not None:
            instance.variable_types.set(variable_types_ids)
        
        return instance
    
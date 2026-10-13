from rest_framework import serializers
from django_filters import rest_framework as filters

from coredata.utils.name_utils import generate_token

from ..models import ( Variable )
from .value_objects_serializer import VariableTypeSerializer

class VariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variable
        fields = '__all__'
    
    
class VariableSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variable
        fields = '__all__'
    
    def create(self, validated_data):
        type = validated_data['type']
        if type.data_type == 'bool':
            validated_data['value'] = "True"
        validated_data['token'] = generate_token(Variable)
        instance = super().create(validated_data)
        return instance
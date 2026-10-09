from rest_framework import serializers
from ..models import ( ContractRepresentative )
from coredata.serializers import PersonSerializer
from .value_objects_serializer import ContractRepresentativeTypeSerializer


class ContractRepresentativeSerializer(serializers.ModelSerializer):
    
    person = PersonSerializer(read_only=True, required=False, allow_null=True)
    #contract = ContractSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = ContractRepresentative
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['type'] = ContractRepresentativeTypeSerializer(instance.type).data
        
        return representation

class ContractRepresentativeSaveSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ContractRepresentative
        fields = ['person', 'type']
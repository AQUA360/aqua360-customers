from rest_framework import serializers
from ..models import ( ContractRequestRepresentative )
from coredata.serializers import PersonSerializer
from .value_objects_serializer import ContractRepresentativeTypeSerializer


class ContractRequestRepresentativeSerializer(serializers.ModelSerializer):
    
    person = PersonSerializer(read_only=True, required=False, allow_null=True)
    type = ContractRepresentativeTypeSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = ContractRequestRepresentative
        fields = '__all__'
    
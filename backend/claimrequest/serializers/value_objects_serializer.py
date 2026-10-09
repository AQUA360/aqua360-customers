from rest_framework import serializers

from documentmanager.serializers import DocumentSerializer
from ..models import ClaimDocumentType, VulnerabilityRequestStatus, VulnerabilityRequestDocumentation

class ClaimDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimDocumentType
        fields = '__all__' 
    
class VulnerabilityRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = VulnerabilityRequestStatus
        fields = '__all__'

class VulnerabilityRequestDocumentationSerializer(serializers.ModelSerializer):
    
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = VulnerabilityRequestDocumentation
        fields = '__all__'
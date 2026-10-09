from rest_framework import serializers

from documentmanager.serializers import DocumentSerializer
from fraud.models import *

class FraudStatusSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = FraudStatus
        fields = '__all__'
        
class FraudDocumentationSerializer(serializers.ModelSerializer):
    
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = FraudDocumentation
        fields = '__all__'

class FraudImageSerializer(serializers.ModelSerializer):
    
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = FraudImage
        fields = '__all__'

class FraudTypeSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = FraudType
        fields = '__all__'
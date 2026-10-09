import datetime
from rest_framework import serializers

from contract.serializers.contract_serializer import ContractMinimalSerializer
from fraud.models import *
from fraud.serializers.fraud_serializer import FraudSerializer
from fraud.serializers.value_objects_serializer import *
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer

class FraudReportSerializer(serializers.ModelSerializer):
    
    fraud = FraudSerializer(read_only=True, required=False, allow_null=True)
    documentation_files = FraudDocumentationSerializer(many=True, read_only=True, required=False, allow_null=True)
    image_files = FraudImageSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = FraudReport
        fields = '__all__'

class FraudReportSaveSerializer(serializers.ModelSerializer):
    
    class Meta: 
        model = FraudReport
        fields = '__all__'
    
    def create(self, validated_data):
        print("creating fraud report")
        print(validated_data)
        now = datetime.date.today().strftime('%Y%m%d')
        fraud = validated_data.get('fraud')
        fraud_reports = FraudReport.objects.filter(fraud=fraud).count()
        
        validated_data['token'] = f"{fraud.token}{str(fraud_reports).zfill(3)}"
        validated_data['user'] = self.context['request'].user
        
        return super().create(validated_data)
    
class FraudReportListSerializer(serializers.ModelSerializer):
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = FraudReport
        fields = ['id', 'token', 'report_date', 'user_username']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        documentation = FraudDocumentation.objects.filter(fraud_report=instance)
        images = FraudImage.objects.filter(fraud_report=instance)
        
        representation['total_documents'] = len(documentation)
        representation['total_images'] = len(images)
        
        return representation
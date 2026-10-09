import datetime
from rest_framework import serializers
from django_filters import rest_framework as filters

from auth.serializers import UserMinimalSerializer
from documentmanager.serializers import DocumentSerializer
from ..models import *

class IncidentStatusSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = IncidentStatus
        fields = '__all__'


class IncidentTypeSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = IncidentType
        fields = '__all__'


class IncidentDocumentationSerializer(serializers.ModelSerializer):
    
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = IncidentDocumentation
        fields = '__all__'


class IncidentReportSerializer(serializers.ModelSerializer):
    
    user = UserMinimalSerializer(required=False, allow_null=True)
    documentation_files = IncidentDocumentationSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = IncidentReport
        fields = '__all__'
    
    def create(self, validated_data):
        print("creating incident report")
        print(validated_data)
        now = datetime.date.today().strftime('%Y%m%d')
        incident = validated_data.get('incident')
        incident_reports = IncidentReport.objects.filter(incident=incident).count()
        
        validated_data['token'] = f"{incident.token}{str(incident_reports).zfill(3)}"
        validated_data['user'] = self.context['request'].user
        
        return super().create(validated_data)

class IncidentReportListSerializer(serializers.ModelSerializer):
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = IncidentReport
        fields = ['id', 'token', 'incident_data', 'user_username'] 
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        documentation = IncidentDocumentation.objects.filter(incident_report=instance)
        
        representation['total_documents'] = len(documentation)
        
        return representation
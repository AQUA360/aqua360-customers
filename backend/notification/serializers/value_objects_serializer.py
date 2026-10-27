import datetime
from rest_framework import serializers
from django_filters import rest_framework as filters

from auth.serializers import UserMinimalSerializer
from documentmanager.serializers import DocumentSerializer
from ..models import *

class IncidentStatusSerializer(serializers.ModelSerializer):
    
    # Tokens dels estats als quals es pot passar (buit: a qualsevol), per al canvi d'estat
    allowed_next_tokens = serializers.SerializerMethodField()
    
    class Meta:
        model = IncidentStatus
        fields = '__all__'

    def get_allowed_next_tokens(self, obj):
        return [status.token for status in obj.allowed_next.all()]


class IncidentChannelSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = IncidentChannel
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
        read_only_fields = ['is_active', 'deleted_at', 'deleted_by', 'deletion_reason']
    
    def create(self, validated_data):
        now = datetime.date.today().strftime('%Y%m%d')
        incident = validated_data.get('incident')
        incident_reports = IncidentReport.objects.filter(incident=incident).count()
        
        validated_data['token'] = f"{incident.token}{str(incident_reports).zfill(3)}"
        validated_data['user'] = self.context['request'].user
        
        report = super().create(validated_data)
        # El primer informe compta com a primera resposta de la incidència
        from notification.utils.incident_utils import record_first_response
        record_first_response(incident)
        return report

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
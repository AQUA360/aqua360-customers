from django.utils import timezone
from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from coredata.models import ConfigProject
from .models import *

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyPointConsumption
        fields = '__all__'
class BillingReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingReport
        fields = '__all__'
class ReportTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportType
        fields = '__all__'

class GeneralReportSerializer(serializers.ModelSerializer):
    type = ReportTypeSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = GeneralReport
        fields = '__all__'

class AccountingValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingValue
        fields = '__all__'

class AccountingCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingCode
        fields = '__all__'

class AccountingCodeGroupedSerializer(serializers.ModelSerializer):
    values = serializers.SerializerMethodField()
    class Meta:
        model = AccountingCode
        fields = '__all__'

    def get_values(self, obj):
        return AccountingValueSerializer(obj.values.all().order_by('token'), many=True).data

class BillingConsumptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingConsumption
        fields = '__all__'


class ReadingBatchExportColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingBatchExportColumn
        fields = "__all__"


class ReadingBatchExportColumnSyncItemSerializer(serializers.ModelSerializer):
    """Payload row for POST …/reading-batch-export-column/sync/ (full table replace)."""

    class Meta:
        model = ReadingBatchExportColumn
        fields = ("name", "value", "position")

class ReadingBatchImportColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingBatchImportColumn
        fields = "__all__"

class ReadingBatchImportTemplateSerializer(serializers.ModelSerializer):
    columns = ReadingBatchImportColumnSerializer(many=True, read_only=True)
    class Meta:
        model = ReadingBatchImportTemplate
        fields = "__all__"
class ReadingBatchImportColumnSyncItemSerializer(serializers.ModelSerializer):
    """Payload row for POST …/reading-batch-import-column/sync/ (per-template replace)."""

    class Meta:
        model = ReadingBatchImportColumn
        fields = ("original_name", "mapped_name")

class AvailableReportSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    download_button_name = serializers.SerializerMethodField()
    section_name = serializers.SerializerMethodField()
    section_token = serializers.CharField(source='section.token', read_only=True, allow_null=True)
    
    class Meta:
        model = AvailableReport
        fields = [
            'id', 'name', 'description', 'is_active', 'function_name', 
            'section', 'section_name', 'section_token', 
            'download_button_name', 'has_custom_config', 'required_fields', 'position'
        ]

    def get_name(self, obj):
        from django.utils.translation import gettext as _, override
        from django.conf import settings
        with override(settings.LANGUAGE_CODE):
            return _(obj.name) if obj.name else ""

    def get_description(self, obj):
        from django.utils.translation import gettext as _, override
        from django.conf import settings
        with override(settings.LANGUAGE_CODE):
            return _(obj.description) if obj.description else ""

    def get_download_button_name(self, obj):
        from django.utils.translation import gettext as _, override
        from django.conf import settings
        with override(settings.LANGUAGE_CODE):
            return _(obj.download_button_name) if obj.download_button_name else ""

    def get_section_name(self, obj):
        from django.utils.translation import gettext as _, override
        from django.conf import settings
        if obj.section and obj.section.name:
            with override(settings.LANGUAGE_CODE):
                return _(obj.section.name)
        return ""

class DailyDocumentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyDocumentStatus
        fields = '__all__'

class DailyDocumentTemplateListSerializer(serializers.ModelSerializer):
    
    available_report_name = serializers.CharField(source='available_report.name', read_only=True)
    
    class Meta:
        model = DailyDocumentTemplate
        fields = '__all__'
        
class DailyDocumentTemplateSerializer(serializers.ModelSerializer):
    
    available_report = AvailableReportSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = DailyDocumentTemplate
        fields = '__all__'
        
class DailyDocumentTemplateSaveSerializer(serializers.ModelSerializer):
    
    available_report_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = DailyDocumentTemplate
        fields = '__all__'
    
    def create(self, validated_data):
        user = self.context['request'].user
            
        available_report_id = validated_data.pop('available_report_id', None)
        available_report = None
        now = timezone.now()
        if available_report_id:
            available_report = AvailableReport.objects.get(id=available_report_id)
            validated_data['available_report'] = available_report
        token = f"{available_report.function_name}_{now.strftime('%Y%m%d')}"
        if user and user.username:
            token += f"_{user.username}"
            
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        available_report_id = validated_data.pop('available_report_id', None)
        if available_report_id:
            available_report = AvailableReport.objects.get(id=available_report_id)
            instance.available_report = available_report
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class DailyDocumentSerializer(serializers.ModelSerializer):
    
    status = DailyDocumentStatusSerializer(read_only=True, required=False, allow_null=True)
    template = DailyDocumentTemplateSerializer(read_only=True, required=False, allow_null=True)
    
    completed_by = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    cancelled_by = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    document = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyDocument
        fields = '__all__'
        
    def get_document(self, obj):
        from documentmanager.serializers import DocumentSerializer
        if obj.document:
            return DocumentSerializer(obj.document).data
        return None

    def update(self, instance, validated_data):
        user = self.context['request'].user
        if 'is_completed' in validated_data and validated_data['is_completed']:
            completed_status_token = ConfigProject.objects.get(token='daily_document_status_completed_token').value
            validated_data['status'] = DailyDocumentStatus.objects.get(token=completed_status_token)
            validated_data['completed_by'] = user
        elif 'cancelled_observation' in validated_data:
            cancelled_status_token = ConfigProject.objects.get(token='daily_document_status_cancelled_token').value
            validated_data['status'] = DailyDocumentStatus.objects.get(token=cancelled_status_token)
            validated_data['cancelled_by'] = user
            validated_data['cancelled_at'] = timezone.now()
        
        return super().update(instance, validated_data)

class DailyDocumentListSerializer(serializers.ModelSerializer):
    
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.username', read_only=True)
    cancelled_by_name = serializers.CharField(source='cancelled_by.username', read_only=True)
    document_name = serializers.CharField(source='document.document_name', read_only=True)
    
    class Meta:
        model = DailyDocument
        fields = '__all__'
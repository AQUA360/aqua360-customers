from django.urls import reverse
from rest_framework import serializers
from .models import Document, DocumentSign, ExportJob

class DocumentSerializer(serializers.ModelSerializer):
    
    versions = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = '__all__'
        
    def get_versions(self, obj):
        versions = obj.versions.all()
        data = []
        for version in versions:
            data.append({
                'id': version.id,
                'version': version.version,
                'date': version.date,
                'entity': version.entity,
                'field': version.field,
                'entity_id': version.entity_id,
                'entity_token': version.entity_token,
                'file': version.file if version.file else None,
                'folder': version.folder,
                'document_name': version.document_name,
                'location': version.location,
                'location_url': version.location_url,
                'service': version.service,
                'is_active': version.is_active,
            })
        return data


class DocumentSignSerializer(serializers.ModelSerializer):

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    contract_token = serializers.CharField(source='contract.token', read_only=True, default=None)
    contract_request_token = serializers.CharField(source='contract_request.token', read_only=True, default=None)
    contract_file_url = serializers.SerializerMethodField()
    contract_file_signed_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentSign
        fields = '__all__'
        read_only_fields = (
            'status',
            'error_report',
            'token',
            'signed_at',
            'contract_file_signed',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        contract = attrs.get('contract', getattr(self.instance, 'contract', None))
        contract_request = attrs.get(
            'contract_request', getattr(self.instance, 'contract_request', None)
        )
        if not contract and not contract_request:
            raise serializers.ValidationError(
                "Cal indicar contract o contract_request."
            )
        return attrs

    def _absolute(self, path):
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    def get_contract_file_url(self, obj):
        if not obj.contract_file_id:
            return None
        # El nom `view_document` també el registra `got`; el camí es construeix a mà.
        path = f"/documentmanager/view-document/{obj.contract_file_id}/"
        return self._absolute(path)

    def get_contract_file_signed_url(self, obj):
        # Només el PDF ja firmat, i només quan l'estat és Signed. Mai l'original.
        if obj.status != DocumentSign.STATUS_SIGNED or not obj.contract_file_signed_id:
            return None
        return self._absolute(reverse('document_sign_download', kwargs={'pk': obj.id}))


class ExportJobSerializer(serializers.ModelSerializer):
    document_id = serializers.IntegerField(read_only=True, allow_null=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = [
            "id", "kind", "name", "params", "status", "error_message",
            "document_id", "file_url", "file_name",
            "created_at", "started_at", "completed_at", "duration_seconds",
        ]
        read_only_fields = fields

    def get_duration_seconds(self, obj):
        if obj.started_at and obj.completed_at:
            return round((obj.completed_at - obj.started_at).total_seconds(), 1)
        return None

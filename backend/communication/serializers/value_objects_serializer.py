from rest_framework import serializers
from django.conf import settings

from coredata.utils.name_utils import generate_token
from documentmanager.models import Document
from documentmanager.serializers import DocumentSerializer
from documentmanager.utils.main_utils import delete_document, upload_document
from ..models import *

class MessageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageType
        fields = '__all__'

class CommunicationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationStatus
        fields = '__all__'
        
class CommunicationUseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationUseType
        fields = '__all__'
        
class CommunicationProcessStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationProcessStatus
        fields = '__all__'
        
class MessageTypeTemplateSerializer(serializers.ModelSerializer):
    message_template_id = serializers.SerializerMethodField()
    template_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    type = MessageTypeSerializer(read_only=True, required=False, allow_null=True)
    document = DocumentSerializer(read_only=True, required=False, allow_null=True)
    
    type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    document_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    document_file = serializers.FileField(write_only=True, required=False, allow_null=True)
    delete_file = serializers.BooleanField(write_only=True, required=False, default=False)
    
    class Meta:
        model = MessageTypeTemplate
        fields = '__all__'
    
    def get_message_template_id(self, obj):
        return obj.message_templates.first().id if obj.message_templates.exists() else None

    def _resolve_type_id(self, validated_data):
        type_id = validated_data.pop('type_id', None)
        if type_id is None:
            raw_type = self.initial_data.get('type')
            if raw_type not in (None, ''):
                try:
                    type_id = int(raw_type)
                except (TypeError, ValueError):
                    type_id = None
        return type_id

    def _resolve_document_id(self, validated_data):
        document_id = validated_data.pop('document_id', None)
        if document_id is None:
            raw_document = self.initial_data.get('document')
            if raw_document not in (None, ''):
                # If "document" is numeric in payload, treat it as existing document id.
                try:
                    document_id = int(raw_document)
                except (TypeError, ValueError):
                    document_id = None
        return document_id

    def _get_uploaded_document_file(self, validated_data):
        uploaded_file = validated_data.pop('document_file', None)
        if uploaded_file:
            return uploaded_file

        request = self.context.get('request')
        if not request:
            return None
        return request.FILES.get('document')

    def _upload_document(self, instance, uploaded_file):
        service = settings.DOCUMENT_MANAGER_SERVICES.get("communication")
        return upload_document(
            uploaded_file,
            'COMUNICACIO',
            'COMM_ATTACHMENT',
            instance.id,
            instance.token or str(instance.id),
            '',
            service,
            uploaded_file.name if hasattr(uploaded_file, 'name') else 'document'
        )
    
    def create(self, validated_data):
        template_id = validated_data.pop('template_id', None)
        validated_data.pop('delete_file', False)
        type_id = self._resolve_type_id(validated_data)
        document_id = self._resolve_document_id(validated_data)
        uploaded_file = self._get_uploaded_document_file(validated_data)
        validated_data['token'] = generate_token(MessageTypeTemplate)
        
        if type_id:
            type = MessageType.objects.get(id=type_id)
            validated_data['type'] = type

        if document_id is not None:
            validated_data['document'] = Document.objects.get(id=document_id) if document_id else None
        
        instance = super().create(validated_data)

        if uploaded_file:
            instance.document = self._upload_document(instance, uploaded_file)
            instance.save(update_fields=['document'])
        
        if template_id:
            template = MessageTemplate.objects.get(id=template_id)
            template.templates.add(instance)
            template.save()
            
        return instance

    def update(self, instance, validated_data):
        delete_file = validated_data.pop('delete_file', False)
        type_id = self._resolve_type_id(validated_data)
        document_id = self._resolve_document_id(validated_data)
        uploaded_file = self._get_uploaded_document_file(validated_data)

        if type_id:
            validated_data['type'] = MessageType.objects.get(id=type_id)

        if delete_file and instance.document:
            try:
                delete_document(instance.document)
            except Exception:
                pass
            validated_data['document'] = None

        if document_id is not None:
            validated_data['document'] = Document.objects.get(id=document_id) if document_id else None

        if uploaded_file:
            validated_data['document'] = self._upload_document(instance, uploaded_file)

        return super().update(instance, validated_data)
    
class MessageOriginSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageOrigin
        fields = '__all__'

class CommunicationFileSerializer(serializers.ModelSerializer):
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = CommunicationFile
        fields = '__all__'
    
    def to_representation(self, instance):
        from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
        representation = super().to_representation(instance)
        representation['invoice'] = InvoiceMinimalSerializer(instance.invoice).data if instance.invoice else None
        return representation
import io
from rest_framework import serializers
from django.conf import settings
from billing.serializers.message_serializer import MessageSerializer
from coredata.models import ConfigProject
from documentmanager.serializers import DocumentSerializer
from documentmanager.utils.main_utils import upload_document
from pricing.models import ProductOrigin
from pricing.serializers.value_objects_serializer import ProductOriginSerializer
import importlib.resources as pkg_resources
import billing.templates
from django.core.files.base import ContentFile

from ..models import InvoiceTemplate


class InvoiceTemplateMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceTemplate
        fields = '__all__'
        
class InvoiceTemplateSerializer(serializers.ModelSerializer):
    origin = ProductOriginSerializer(read_only=True, required=False, allow_null=True)
    messages = MessageSerializer(many=True, read_only=True, required=False, allow_null=True)
    file_template = DocumentSerializer(read_only=True, required=False, allow_null=True)
    
    origin_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    file_template_html = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = InvoiceTemplate
        fields = '__all__'
    
    def create(self, validated_data):
        origin_contract_token = ConfigProject.objects.get(token='origin_contract_token').value
        
        
        origin_id = validated_data.pop('origin_id', None)
        origin_instance = ProductOrigin.objects.get(id=origin_id) if origin_id else None
        
        validated_data['origin'] = origin_instance
        invoice_template = InvoiceTemplate.objects.create(**validated_data)
        
        """ with pkg_resources.files(billing.templates).joinpath("invoice_template.html").open('rb') as f:
            invoice_template.file_template.save(
                f"invoice_template_{(invoice_template.origin.name).lower()}.html",
                f
            ) """
        file_name = "invoice_template.html" if origin_instance.token != origin_contract_token else "invoice_request_template.html"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("template")
        with pkg_resources.files(billing.templates).joinpath(
            file_name
        ).open("rb") as f:
            file_content = f.read()
            file_name = (
                f"{file_name}"
            )
            content_file = ContentFile(file_content, name=file_name)

            invoice_template.file_template = upload_document(
                content_file,
                "TEMPLATES",
                "BILLING",
                invoice_template.id,
                (invoice_template.origin.name).upper(),
                "",
                service,
                file_name,
                invoice_template.created_at,
            )
        invoice_template.save()
        
        return invoice_template
    
    def update(self, instance, validated_data):
        print("updating invoice template")

        messages = list(instance.messages.all())  

        origin_id = validated_data.pop('origin_id', None)
        origin_contract_token = ConfigProject.objects.get(token='origin_contract_token').value
        file_template_html = validated_data.pop('file_template_html', None)

        if file_template_html:
            file_name = "invoice_template.html" if instance.origin.token != origin_contract_token else "invoice_request_template.html"
            file_bytes = file_template_html.read()
            content_file = ContentFile(file_bytes, name=file_name)

            service = settings.DOCUMENT_MANAGER_SERVICES.get("template")

            instance.file_template = upload_document(
                content_file,
                "templates",
                "billing",
                instance.id,
                (instance.origin.name).lower() if instance.origin else "",
                "",
                service,
                file_name,
                instance.created_at,
            )

        if origin_id:
            origin_instance = ProductOrigin.objects.get(id=origin_id)
            instance.origin = origin_instance

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save() 
        instance.messages.set(messages)  
        instance.save()

        return instance

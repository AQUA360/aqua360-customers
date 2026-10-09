from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from communication.serializers.communication_process_serializer import CommunicationProcessSerializer
from communication.tasks import generate_communication_invoice_documents_task
from communication.utils.communication_service import create_email_template, get_communication_file
from coredata.models import ConfigProject
from django.conf import settings
from coredata.utils.name_utils import generate_token
from logger.models import LogCommunicationChange
from service.serializers.value_objects_serializer import CompanyConfigEmailSerializer, CompanyConfigSerializer
from ..models import Communication, CommunicationFile, CommunicationObservation, CommunicationStatus, CommunicationUseType, Message, MessageType, MessageTypeTemplate
from .value_objects_serializer import CommunicationFileSerializer, CommunicationStatusSerializer, CommunicationUseTypeSerializer, MessageTypeSerializer
from coredata.serializers import  PersonMinimalSerializer
from service.serializers.company_serializer import CompanySerializer
from .message_serializer import MessageSerializer
from documentmanager.utils.main_utils import upload_document
from django.core.files.base import ContentFile

class CommunicationObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = CommunicationObservation
        fields = '__all__'

class CommunicationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(read_only=True, required=False, allow_null=True, many=True)
    process = CommunicationProcessSerializer(read_only=True, required=False, allow_null=True)
    types = MessageTypeSerializer(many=True, read_only=True, required=False, allow_null=True)
    person = PersonMinimalSerializer(read_only=True, required=False, allow_null=True)
    company_config = CompanyConfigSerializer(read_only=True, required=False, allow_null=True)
    company_config_email = CompanyConfigEmailSerializer(read_only=True, required=False, allow_null=True)
    config_company = serializers.SerializerMethodField()
    status = CommunicationStatusSerializer(read_only=True, required=False, allow_null=True)
    use_type = CommunicationUseTypeSerializer(read_only=True, required=False, allow_null=True)
    user = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    #files = CommunicationFileSerializer(many=True, read_only=True, required=False, allow_null=True)
    files = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    readings = serializers.SerializerMethodField()
    contracts = serializers.SerializerMethodField()
    
    class Meta:
        model = Communication
        fields = '__all__'
    
    def get_invoices(self, obj):
        from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
        return InvoiceMinimalSerializer(obj.invoices.all(), many=True, read_only=True, required=False, allow_null=True).data
    
    def get_readings(self, obj):
        from billing.serializers.reading_serializer import ReadingMinimalSerializer
        return ReadingMinimalSerializer(obj.readings.all(), many=True, read_only=True, required=False, allow_null=True).data
    
    def get_contracts(self, obj):
        from contract.serializers.contract_serializer import ContractMinimalSerializer
        return ContractMinimalSerializer(obj.contracts.all(), many=True, read_only=True, required=False, allow_null=True).data
    
    def get_config_company(self, obj):
        config = obj.company_config
        companies = config.company_configs.all()
        company = companies.first() if len(companies) > 0 else None
        return CompanySerializer(company, read_only=True, required=False, allow_null=True).data
    
    def get_files(self, obj):
        files = obj.files.filter(is_active=True)
        return CommunicationFileSerializer(files, many=True, read_only=True, required=False, allow_null=True).data
        
class CommunicationListSerializer(serializers.ModelSerializer):
    person_name = serializers.SerializerMethodField()
    person_token = serializers.CharField(source='person.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    use_type_name = serializers.CharField(source='use_type.name', read_only=True)
    process_token = serializers.CharField(source='process.token', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    process_message_ids = serializers.SerializerMethodField()
    message_ids = serializers.SerializerMethodField()
    message_subject = serializers.SerializerMethodField()
    class Meta:
        model = Communication
        fields = [
            'id', 'sent_at', 'token', 'created_at',
            'user', 'user_username', 'person_name', 'status_name', 
            'status_color', 'process_token', 'type_names', 'person_token',
            'use_type_name', 'process_message_ids', 'message_ids',
            'used_email', 'due_date', 'message_subject'
            ]
    
    def get_message_subject(self, obj):
        return obj.messages.first().subject if obj.messages.first() else None
    
    def get_process_message_ids(self, obj):
        return [msg.id for msg in obj.process.messages.all()] if obj.process else []
    
    def get_message_ids(self, obj):
        return [msg.id for msg in obj.messages.all()]
    
    def get_person_name(self, obj):
        if obj.person:
            if obj.person.surname:
                return f"{obj.person.name} {obj.person.surname}"
            return obj.person.name
        return None
    
class CommunicationSaveSerializer(serializers.ModelSerializer):
    messages_data = serializers.ListField(write_only=True, required=False, allow_null=True)
    message_type_names = serializers.ListField(write_only=True, required=False, allow_null=True)
    message_types = serializers.ListField(write_only=True, required=False, allow_null=True)
    contract_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    use_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    selected_invoices = serializers.ListField(write_only=True, required=False, allow_null=True)
    selected_readings = serializers.ListField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Communication
        fields = '__all__'
    
    def create(self, validated_data):
        messages_data = validated_data.pop('messages_data', None)
        
        message_type_names = validated_data.pop('message_type_names', None)
        message_types = validated_data.pop('message_types', None)
        person = validated_data.get('person', None)
        contract_id = validated_data.pop('contract_id', None)
        use_type_id = validated_data.pop('use_type_id', None)
        
        selected_invoices = validated_data.pop('selected_invoices', None)
        selected_readings = validated_data.pop('selected_readings', None)
        
        if use_type_id:
            use_type = CommunicationUseType.objects.get(id=use_type_id)
        else:
            use_type = CommunicationUseType.objects.get(is_default=True)
        validated_data['use_type'] = use_type
        
        messages = []
        
        contract = None
        if contract_id:
            from contract.models import Contract
            contract = Contract.objects.get(id=contract_id)
            validated_data['contracts'] = [contract]
        
        if selected_invoices:
            from billing.models import Invoice
            invoices = Invoice.objects.filter(id__in=selected_invoices)
            validated_data['invoices'] = invoices
            
        if selected_readings:
            from billing.models import Reading
            readings = Reading.objects.filter(id__in=selected_readings)
            validated_data['readings'] = readings
        
        status_default = CommunicationStatus.objects.get(is_default=True)
        request = self.context.get('request')
        user = request.user if request else None
        
        validated_data['token'] = generate_token(Communication)
        validated_data['status'] = status_default
        validated_data['user'] = user
        
        if message_types:
            
            if 'default' in message_types or 'digital' in message_types:
                sms_token = ConfigProject.objects.get(token='message_type_sms_token').value
                email_token = ConfigProject.objects.get(token='message_type_email_token').value
                whatsapp_token = ConfigProject.objects.get(token='message_type_whatsapp_token').value
                letter_token = ConfigProject.objects.get(token='message_type_letter_token').value
                if 'default' in message_types:
                    if contract.communication_type == 'DIGITAL':
                        if contract.person_contact_email:
                            msg_type = MessageType.objects.get(token=email_token)
                            if not 'used_email' in validated_data:
                                validated_data['used_email'] = contract.person_contact_email.email if contract.person_contact_email else None
                        else:
                            msg_type = MessageType.objects.get(token=sms_token)
                            if not 'used_phones' in validated_data:
                                validated_data['used_phones'] = contract.person_contact_sms.values_list('phone', flat=True)
                    elif contract.communication_type == 'PAPER' or contract.communication_type == 'PHYSICAL':
                        from coredata.serializers import PersonAddressSerializer
                        msg_type = MessageType.objects.get(token=letter_token)
                        if not 'used_address' in validated_data:
                            validated_data['used_address'] = PersonAddressSerializer(contract.address_contact).data.get('simple_address_complete')
                    elif contract.communication_type == 'NONE':
                        raise serializers.ValidationError(
                            "El contracte té 'Sense comunicació' com a tipus de comunicació; no es pot generar cap enviament."
                        )
                    if contract.communication_type == 'BOTH':
                        # Ambdues: correu i carta alhora; si falta un dels dos destins, només l'altre.
                        from coredata.serializers import PersonAddressSerializer
                        both_types = []
                        if not 'used_email' in validated_data and contract.person_contact_email:
                            validated_data['used_email'] = contract.person_contact_email.email
                        if validated_data.get('used_email'):
                            both_types.append(MessageType.objects.get(token=email_token))
                        if not 'used_address' in validated_data and contract.address_contact:
                            validated_data['used_address'] = PersonAddressSerializer(contract.address_contact).data.get('simple_address_complete')
                        if validated_data.get('used_address') or not both_types:
                            both_types.append(MessageType.objects.get(token=letter_token))
                        validated_data['types'] = both_types
                        validated_data['type_tokens'] = ','.join(t.token for t in both_types)
                        validated_data['type_names'] = ','.join(t.name for t in both_types)
                    else:
                        validated_data['types'] = [msg_type]
                        validated_data['type_tokens'] = msg_type.token
                        validated_data['type_names'] = msg_type.name
                elif 'digital' in message_types:
                    email = validated_data.get('used_email', None)
                    if not email or email == '':
                        msg_type = MessageType.objects.get(token=sms_token)
                    else:
                        msg_type = MessageType.objects.get(token=email_token)
                    validated_data['types'] = [msg_type]
                    validated_data['type_tokens'] = msg_type.token
                    validated_data['type_names'] = msg_type.name
                else:
                    msg_type = MessageType.objects.get(token=letter_token)
                    validated_data['types'] = [msg_type]
                    validated_data['type_tokens'] = msg_type.token
                    validated_data['type_names'] = msg_type.name
            else:
                msg_types = MessageType.objects.filter(id__in=message_types)
                validated_data['types'] = msg_types
                validated_data['type_tokens'] = ','.join([msg_type.token for msg_type in msg_types])
                validated_data['type_names'] = ','.join([msg_type.name for msg_type in msg_types])
    
        for message_data in messages_data:
            msg_type = MessageType.objects.get(id=message_data.get('type').get('id'))
            if msg_type in validated_data['types']:
                message = Message.objects.create(
                    token=generate_token(Message),
                    subject=message_data.get('msg_data').get('subject'),
                    body=message_data.get('msg_data').get('body'),
                    type=msg_type,
                )
                messages.append(message)
            
        instance = super().create(validated_data)
        instance.messages.set(messages)
        instance.save()
        
        if 'letter' in instance.type_tokens.split(','):
            comm = CommunicationFile.objects.create(
                token=generate_token(CommunicationFile),
                communication=instance,
                file=None,
                is_letter=True,
            )
            n_file = get_communication_file(comm.id)
            if n_file:
                comm.file = n_file
                comm.save()
        if 'email' in instance.type_tokens.split(','):
            create_email_template(instance)
        
        if instance.invoices.count() > 0:
            generate_communication_invoice_documents_task.delay(
                [instance.id]
            )
        
        return instance
    
    def update(self, instance, validated_data):
        
        previous_types = instance.types.all()
        previous_used_email = instance.used_email
        previous_used_phones = instance.used_phones
        previous_used_address = instance.used_address
        request = self.context.get('request')
        user = request.user if request else None
        
        had_letter = True if instance.used_address and 'letter' in instance.type_tokens.split(',') else False
        had_electronic_inv = True if instance.accounting_office and 'electronic_inv' in instance.type_tokens.split(',') and instance.invoices.count() > 0 else False
        communication = super().update(instance, validated_data)
        communication.type_tokens = ','.join(communication.types.values_list('token', flat=True))
        communication.type_names = ','.join(communication.types.values_list('name', flat=True))
        messages = []
        for msg_type in communication.types.all():
            template = instance.process.template if instance.process and instance.process.template else None
            template_type = template.templates.filter(type=msg_type).first() if template else None
            messages.append(Message.objects.create(
                token=generate_token(Message),
                subject=template_type.subject if template_type else "",
                body=template_type.body if template_type else "",
                type=msg_type,
            ))
        communication.messages.set(messages)
        
        if 'letter' in communication.type_tokens.split(',') and not had_letter:
            comm = CommunicationFile.objects.create(
                token=generate_token(CommunicationFile),
                communication=communication,
                file=None,
                is_letter=True,
            )
            n_file = get_communication_file(comm.id)
            if n_file:
                comm.file = n_file
        if 'email' in communication.type_tokens.split(','):
            create_email_template(communication)
        if 'electronic_inv' in communication.type_tokens.split(',') and not had_electronic_inv:
            invoice_com_files = []
            from billing.views.epayment_document_generate_view import generate_xml
            for invoice in communication.invoices.all():
                try:
                    xml_data = generate_xml(None, invoice)  
                except Exception as e:
                    raise Exception(f"Error generating XML for invoice {invoice.serie_final}: {e}")
                xml_file_name = f"{invoice.serie_final.replace('/', '_')}_{invoice.id}.xml"
                
                try:
                    from documentmanager.models import Document
                    existing_document = Document.objects.filter(
                        entity='REBUTS',
                        field='EFACTURA',
                        entity_id=invoice.id,
                        document_name=xml_file_name
                    ).first()
                except Exception as e:
                    print(f"Error getting existing document for invoice {invoice.serie_final}: {e}")
                    existing_document = None
                if existing_document:
                    document_file = existing_document
                else:
                    xml_file = ContentFile(xml_data.encode("utf-8"), name=xml_file_name)
                    document_file = upload_document(xml_file, 'REBUTS', 'EFACTURA', invoice.id, invoice.customer_token_final, '', settings.DOCUMENT_MANAGER_SERVICES.get("billing"), xml_file_name)
                    invoice_com_files.append(CommunicationFile.objects.create(
                        token=generate_token(CommunicationFile),
                        communication=communication,
                        file=document_file,
                    ))
        
        communication.save()
        
        if (
            previous_types != communication.types.all() or
            previous_used_email != communication.used_email or
            previous_used_phones != communication.used_phones or
            previous_used_address != communication.used_address
        ):
            new_log = LogCommunicationChange.objects.create(
                object=communication,
                previous_used_email=previous_used_email,
                current_used_email=communication.used_email,
                previous_used_phone=previous_used_phones,
                current_used_phone=communication.used_phones,
                previous_used_address=previous_used_address,
                current_used_address=communication.used_address,
                user=user
            )
            new_log.previous_types.set(previous_types)
            new_log.current_types.set(communication.types.all())
            new_log.save()
        
        return communication

class CommunicationMinimalSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    process_token = serializers.CharField(source='process.token', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    message_subject = serializers.CharField(source='message.subject', read_only=True)
    message_body = serializers.CharField(source='message.body', read_only=True)
    
    class Meta:
        model = Communication
        fields = [
            'id', 'token', 'created_at', 
            'sent_at', 'message_subject', 'message_body',
            'type', 'status_name', 'status_color',
            'process_token', 'user_username'
            ]
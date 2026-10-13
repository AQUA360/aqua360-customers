from rest_framework import serializers
from django.db import transaction

from auth.serializers import UserMinimalSerializer
from communication import process_policy
from communication.serializers.message_serializer import MessageSerializer
from communication.serializers.message_template_serializer import MessageTemplateSerializer
from communication.serializers.value_objects_serializer import CommunicationProcessStatusSerializer, CommunicationUseTypeSerializer
from communication.tasks import generate_claim_document_pdf_task, generate_communication_files, process_communication_creation_task
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from logger.models import LogCommunicationProcessStatusChange
from service.models import Company, CompanyConfig, CompanyConfigEmail
from ..models import Communication, CommunicationProcessObservation, CommunicationProcessStatus, CommunicationStatus, CommunicationProcess, CommunicationUseType, MessageTemplate, MessageType, Message, MessageTypeTemplate

class CommunicationProcessObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = CommunicationProcessObservation
        fields = '__all__'

class CommunicationProcessSerializer(serializers.ModelSerializer):
    status = CommunicationProcessStatusSerializer(read_only=True, required=False, allow_null=True)
    use_type = CommunicationUseTypeSerializer(read_only=True, required=False, allow_null=True)
    template = MessageTemplateSerializer(read_only=True, required=False, allow_null=True)
    messages = MessageSerializer(read_only=True, required=False, allow_null=True, many=True)
    user = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    
    readings = serializers.SerializerMethodField()
    communications = serializers.SerializerMethodField()
    com_files = serializers.SerializerMethodField()
    
    has_electronic_invoices = serializers.SerializerMethodField()
    has_letters = serializers.SerializerMethodField()
    has_email = serializers.SerializerMethodField()
    has_invoices = serializers.SerializerMethodField()


    class Meta:
        model = CommunicationProcess
        fields = '__all__'

    def get_readings(self, obj):
        from billing.serializers.reading_serializer import ReadingMinimalSerializer
        return ReadingMinimalSerializer(obj.readings.all(), many=True, read_only=True, required=False, allow_null=True).data

    def get_has_electronic_invoices(self, obj):
        return obj.communications.filter(types__token='electronic_inv').exists()

    def get_has_letters(self, obj):
        return obj.communications.filter(types__token='letter').exists()

    def get_has_email(self, obj):
        email_token = ConfigProject.objects.get(token='message_type_email_token').value
        return any(email_token in (c.type_tokens or '').split(',') for c in obj.communications.all())
    
    def get_communications(self, obj):
        return obj.communications.values_list('id', flat=True)
    
    def get_has_invoices(self, obj):
        return obj.communications.filter(
            files__file__entity='FACTURES',
            files__file__field='FACTURA',
        ).exists()
    
    def get_com_files(self, obj):
        files = []
        postal_token = ConfigProject.objects.get(token='message_type_letter_token').value
        email_token = ConfigProject.objects.get(token='message_type_email_token').value
        for communication in obj.communications.all():
            type_tokens = (communication.type_tokens or '').split(',')
            comm_is_postal = postal_token in type_tokens
            comm_is_email = email_token in type_tokens
            for comm_file in communication.files.filter(is_active=True):
                if comm_file.file:
                    # Un document exclos d'un canal (p. ex. el del pas de reclamacio amb
                    # `attach_claim_documents` desmarcat) no surt al paquet d'aquell canal.
                    is_postal = comm_is_postal and comm_file.attach_to_letter
                    is_email = comm_is_email and comm_file.attach_to_email
                    if (comm_is_postal or comm_is_email) and not (is_postal or is_email):
                        continue
                    files.append({
                        'id': comm_file.file.id,
                        'is_postal': is_postal,
                        'is_email': is_email,
                        'has_invoice': comm_file.file.entity == 'FACTURES' and comm_file.file.field == 'FACTURA'
                        })
        return files

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['sms_coms'] = instance.communications.filter(types__token='sms').count()
        data['whatsapp_coms'] = instance.communications.filter(types__token='whatsapp').count()
        data['email_coms'] = instance.communications.filter(types__token='email').count()
        data['letter_coms'] = instance.communications.filter(types__token='letter').count()
        
        from billing.models import Billing
        billing = Billing.objects.filter(communication_process=instance).first()
        if billing:
            data['billing'] = {
                'id': billing.id,
                'token': billing.token
            }
        
        from claimrequest.models import ClaimRequest
        claim_request = ClaimRequest.objects.filter(current_step__communication_process=instance).first()
        if claim_request:
            data['claim_request'] = {
                'id': claim_request.id,
                'token': claim_request.token
            }
        
        return data
    
class CommunicationProcessListSerializer(serializers.ModelSerializer):
    total_communications = serializers.SerializerMethodField()
    total_sent_communications = serializers.SerializerMethodField()
    
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_token = serializers.CharField(source='status.token', read_only=True)
    use_type_name = serializers.CharField(source='use_type.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    has_electronic_invoices = serializers.SerializerMethodField()
    total_rejected_communications = serializers.SerializerMethodField()
    readings_exploitation = serializers.SerializerMethodField()
    supply_cuts = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    class Meta:
        model = CommunicationProcess
        fields = [
            'created_at', 'token', 'due_date',
            'supply_cuts',
            'id', 'description', 'user_username',
            'status', 'status_name', 'status_color',
            'template', 'template_name',
            'user', 'total_communications', 
            'type_names', 'total_sent_communications',
            'status_token', 'task_id', 'has_electronic_invoices',
            'use_type_name', 'total_rejected_communications',
            'readings_exploitation'
            ]
    def get_total_rejected_communications(self, obj):
        return obj.communications.filter(status__token=ConfigProject.objects.get(token='communication_status_rejected_token').value).count()
    def get_has_electronic_invoices(self, obj):
        return obj.communications.filter(types__token='electronic_inv').exists()
    def get_total_communications(self, obj):
        return obj.communications.count()
    def get_total_sent_communications(self, obj):
        return obj.communications.filter(status__token=ConfigProject.objects.get(token='communication_status_sent_token').value).count()
    def get_readings_exploitation(self, obj):
        if obj.readings.exists():
            return obj.readings.first().supply_point.connection.exploitation.name
        return None
class CommunicationProcessSaveSerializer(serializers.ModelSerializer):
    persons = serializers.ListField(write_only=True, required=False, allow_null=True)
    fixed_data = serializers.CharField(write_only=True, required=False, allow_null=True)
    fixed_data_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    message_template_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    messages_data = serializers.ListField(write_only=True, required=False, allow_null=True)
    attach_letter = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    company_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    company_config_email_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    message_types_ids = serializers.ListField(write_only=True, required=False, allow_null=True)
    message_type_names = serializers.ListField(write_only=True, required=False, allow_null=True)
    comm_ids = serializers.ListField(write_only=True, required=False, allow_null=True)
    use_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    attach_invoices = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    attach_readings = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    attach_reading_invoices = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    # Només aplica als processos d'impagats (`fixed_data == 'claimrequest'`): decideix si el
    # document del pas (carta de suspensió / recordatori) s'envia amb la comunicació, per
    # correu o per carta. Es genera i queda arxivat a la comunicació en tots dos casos.
    # Per defecte `True`, per no canviar el comportament dels clients que no enviïn el camp.
    attach_claim_documents = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    og_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = CommunicationProcess
        fields = '__all__'
        
    @transaction.atomic
    def create(self, validated_data):
        persons = validated_data.pop('persons', None)
        
        attach_letter = validated_data.pop('attach_letter', False)
        message_types_ids = validated_data.pop('message_types_ids', None)
        message_type_names = validated_data.pop('message_type_names', None)
        company_id = validated_data.pop('company_id', None)
        company_config_email_id = validated_data.pop('company_config_email_id', None)
        fixed_data = validated_data.pop('fixed_data', None)
        fixed_data_id = validated_data.pop('fixed_data_id', None)
        message_template_id = validated_data.pop('message_template_id', None)
        messages_data = validated_data.pop('messages_data', [])
        request = self.context.get('request')
        user = request.user if request else None
        use_type_id = validated_data.pop('use_type_id', None)
        comm_ids = validated_data.pop('comm_ids', None)
        
        attach_invoices = validated_data.pop('attach_invoices', False)
        attach_readings = validated_data.pop('attach_readings', False)
        attach_reading_invoices = validated_data.pop('attach_reading_invoices', False)
        # `None` (camp enviat buit) es tracta com a True: només un `false` explícit desactiva l'adjunt.
        attach_claim_documents = validated_data.pop('attach_claim_documents', None)
        attach_claim_documents = True if attach_claim_documents is None else attach_claim_documents

        og_id = validated_data.pop('og_id', None)
        run_token = validated_data.pop('run_token', None)

        # The cut can arrive three ways: the `supply_cuts` payload used by the step 1
        # supply cut filter, `fixed_data`/`fixed_data_id` used by the supply cut
        # management option, and the `supply_cut_id` deep link (which also lands on
        # fixed_data). Union them so every entry path records the same link.
        supply_cut_ids = [getattr(cut, 'id', cut) for cut in (validated_data.pop('supply_cuts', None) or [])]
        if fixed_data == 'supplycut' and fixed_data_id:
            try:
                supply_cut_ids.append(int(fixed_data_id))
            except (TypeError, ValueError):
                pass
        try:
            supply_cut_ids = sorted({int(cut_id) for cut_id in supply_cut_ids})
        except (TypeError, ValueError):
            supply_cut_ids = []

        # Row lock first, then classify, inside the transaction opened by the
        # decorator: a concurrent save for the same cut blocks here until this one
        # commits, so it sees the process we are about to create. `og_id` excludes
        # the process being updated and `run_token` excludes this run's own
        # earlier batches.
        supply_cut_ids = process_policy.lock_cuts(supply_cut_ids)
        if supply_cut_ids:
            tier, linked_processes = process_policy.inspect(
                supply_cut_ids,
                exclude_process_id=og_id,
                exclude_run_token=run_token,
            )
            if tier == process_policy.TIER_BLOCK:
                raise serializers.ValidationError({
                    'message': 'A communication process is already running for this supply cut.',
                    'tier': tier,
                    'processes': [
                        {
                            'id': process.id,
                            'token': process.token,
                            'status_name': process.status.name if process.status_id else None,
                            'status_color': process.status.color if process.status_id else None,
                        }
                        for process in linked_processes
                    ],
                })
        if run_token:
            validated_data['run_token'] = run_token
        
        print("message_template_id", message_template_id)
        
        token = generate_token(CommunicationProcess) if not og_id else None
        # status = CommunicationProcessStatus.objects.get(is_default=True)
        status = CommunicationProcessStatus.objects.get(
            token=ConfigProject.objects.get(token="communication_process_status_processing_token").value
        )
        
        messages = []
        for message_data in messages_data:
            message = Message.objects.create(
                token=generate_token(Message),
                subject=message_data.get('msg_data').get('subject'),
                body=message_data.get('msg_data').get('body'),
                type=MessageType.objects.get(id=message_data.get('type').get('id')),
            )
            messages.append(message)
        
        if use_type_id:
            use_type = CommunicationUseType.objects.get(id=use_type_id)
        else:
            use_type = CommunicationUseType.objects.get(is_default=True)
        validated_data['use_type'] = use_type
        
        #pr_msg_type = MessageTypeTemplate.objects.get(id=prefered_type_id)
        try:
            msg_types = MessageTypeTemplate.objects.filter(id__in=message_types_ids)
        except Exception:
            msg_types = []
        msg_names = ''
        msg_tokens = ''
        single_name = ''
        
        if message_type_names and len(message_type_names) > 0:
            msg_names = ','.join(message_type_names)
        if len(msg_types) == 0 and message_types_ids:
            msg_tokens = ','.join(message_types_ids)
            single_name = message_type_names[0]
        else:
            msg_tokens = ','.join([msg_type.type.token for msg_type in msg_types])
        template_instance = None
        if message_template_id:
            template_instance = MessageTemplate.objects.filter(id=message_template_id).first()
            if template_instance is None:
                template_instance = MessageTemplate.objects.filter(token=message_template_id).first()

        company_config = None
        if company_id:
            #company = Company.objects.get(id=company_id)
            company_config = CompanyConfig.objects.get(id=company_id)
        
        company_config_email = None
        if company_config_email_id:
            company_config_email = CompanyConfigEmail.objects.get(id=company_config_email_id)
            
        if token:
            validated_data['token'] = token
        validated_data['status'] = status
        validated_data['used_types'] = msg_types
        validated_data['template'] = template_instance
        validated_data['type_names'] = msg_names
        validated_data['type_tokens'] = msg_tokens
        validated_data['user'] = user
        
        instance = None
        if og_id:
            try:
                instance = CommunicationProcess.objects.get(id=og_id)
            except Exception:
                pass
        if instance:
            instance = super().update(instance, validated_data)
        else:
            instance = super().create(validated_data)
        
        instance.messages.set(messages)
        instance.save()
        if supply_cut_ids:
            instance.supply_cuts.set(supply_cut_ids)
        
        if comm_ids:
            communications = Communication.objects.filter(id__in=comm_ids)
            instance.communications.set(communications)
            instance.status = CommunicationProcessStatus.objects.get(
                token=ConfigProject.objects.get(token="communication_process_status_current_token").value
            )
            instance.save()
            return instance
        
        
        if fixed_data:
            if fixed_data == 'claimrequest':
                from claimrequest.models import ClaimRequest
                claim_instance = ClaimRequest.objects.get(id=fixed_data_id)
                if not claim_instance.current_step.is_completed and claim_instance.current_step.document_type != None:
                    claim_instance.current_step.communication_process = instance
                    claim_instance.current_step.due_date = instance.due_date
                    claim_instance.current_step.action_date_at = instance.created_at
                    claim_instance.current_step.save()
            elif fixed_data == 'billing':
                from billing.models import Billing
                billing_instance = Billing.objects.get(id=fixed_data_id)
                billing_instance.communication_process = instance
                billing_instance.save()
        
        LogCommunicationProcessStatusChange.objects.create(
            object=instance,
            previous_status=None,
            current_status=status,
            user=user,
        )
        
        # Trigger async task to handle communication creation and file generation.
        # Deferred to on_commit because the task reads this process and its supply
        # cuts; dispatched inline it could start before the transaction commits.
        transaction.on_commit(lambda: process_communication_creation_task.delay(
            instance.id,
            user.id if user else None,
            persons,
            company_config.id if company_config else None,
            single_name,
            msg_tokens,
            fixed_data,
            attach_letter,
            fixed_data_id,
            message_template_id,
            attach_invoices,
            company_config_email.id if company_config_email else None,
            attach_claim_documents=attach_claim_documents,
            attach_readings=attach_readings,
            attach_reading_invoices=attach_reading_invoices
        ))
        
        return instance

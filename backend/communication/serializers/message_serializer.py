from rest_framework import serializers

from communication.tasks import generate_files_task, update_communication_messages_task
from communication.utils.communication_service import create_email_template, get_communication_file
from coredata.utils.name_utils import generate_token
from documentmanager.utils.main_utils import delete_document
from ..models import Communication, CommunicationFile, CommunicationProcess, Message, MessageType
from .value_objects_serializer import MessageTypeSerializer

class MessageSerializer(serializers.ModelSerializer):
    type = MessageTypeSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Message
        fields = '__all__'
        
class MessageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'subject', 'body', 'message_date', 'message_time']
        
class MessageSaveSerializer(serializers.ModelSerializer):
    type = MessageTypeSerializer(read_only=True, required=False, allow_null=True)
    
    communication_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    process_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    updating_messages_task_id = serializers.CharField(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Message
        fields = '__all__'
    
    def create(self, validated_data):
        communication_id = validated_data.pop('communication_id', None)
        instance = super().create(validated_data)
        if communication_id:
            communication = Communication.objects.get(id=communication_id)
            communication.message = instance
            communication.save()
            
        return instance

    def update(self, instance, validated_data):
        communication_id = validated_data.pop('communication_id', None)
        process_id = validated_data.pop('process_id', None)
        type_id = validated_data.pop('type_id', None)
        
        process = None
        type_instance = MessageType.objects.get(id=type_id)
        
        total_coms = instance.communications.all()
        print(total_coms)
        if total_coms.count() != 1:
            """  Per què era això?
            instance = Message.objects.create(
                token=generate_token(Message),
                subject=validated_data.get('subject', instance.subject),
                body=validated_data.get('body', instance.body),
                type=type_instance,
            ) """
            if process_id:
                instance = super().update(instance, validated_data)
                
                print("should be updating process")
                process = CommunicationProcess.objects.get(id=process_id)
                #process.message = instance
                updated_msg = process.messages.get(type=type_instance)
                process.messages.remove(updated_msg)
                process.messages.add(instance)
                process.save()
                print("process saved")
            if communication_id:
                print("should be updating 1")
                instance = Message.objects.create(
                    token=generate_token(Message),
                    subject=validated_data.get('subject', instance.subject),
                    body=validated_data.get('body', instance.body),
                    type=type_instance,
                )
                communication = Communication.objects.get(id=communication_id)
                #communication.message = instance
                updated_msg = communication.messages.get(type=type_instance)
                communication.messages.remove(updated_msg)
                communication.messages.add(instance)
                print("communication.type_tokens")
                print(communication.type_tokens)
                if 'email' in communication.type_tokens.split(','):
                    create_email_template(communication)
                if 'letter' in communication.type_tokens.split(','):
                    prev_letter = communication.files.get(is_letter=True, file__isnull=False)
                    print("prev_letter")
                    print(prev_letter)
                    if prev_letter:
                        if prev_letter.file:
                            try:
                                delete_document(prev_letter.file)
                                prev_letter.file.delete()
                            except:
                                pass
                        prev_letter.delete()
                    comm = CommunicationFile.objects.create(
                        token=generate_token(CommunicationFile),
                        communication=communication,
                        file=None,
                        is_letter=True,
                    )
                    n_file = get_communication_file(comm.id)
                    if n_file:
                        comm.file = n_file
                        comm.save()
                    communication.save()
            else:
                print("should be updating all")
                #total_coms.update(message=instance)
                task_id = update_communication_messages_task.delay(instance.id, process_id, type_id).id
                instance.updating_messages_task_id = task_id
                if process:
                    process.updating_messages_task_id = task_id
                    process.save()
        else:
            instance = super().update(instance, validated_data)
            if 'email' in total_coms[0].type_tokens.split(','):
                print("should be creating email template")
                create_email_template(total_coms[0])
            if 'letter' in total_coms[0].type_tokens.split(','):
                print("should be creating letter file")
                generate_files_task([total_coms[0].id])
        return instance
        
        
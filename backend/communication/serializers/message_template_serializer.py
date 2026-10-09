from rest_framework import serializers

from communication.serializers.value_objects_serializer import MessageOriginSerializer, MessageTypeTemplateSerializer
from coredata.utils.name_utils import generate_token
from ..models import MessageTemplate

class MessageTemplateSerializer(serializers.ModelSerializer):
    origin = MessageOriginSerializer(read_only=True, required=False, allow_null=True)
    templates = MessageTypeTemplateSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = MessageTemplate
        fields = '__all__'

class MessageTemplateListSerializer(serializers.ModelSerializer):
    total_templates = serializers.SerializerMethodField()
    origin_name = serializers.CharField(source='origin.name', read_only=True)
    
    class Meta:
        model = MessageTemplate
        fields = ['created_at', 'id', 'name', 'token', 'origin', 'total_templates', 'origin_name']
        
    def get_total_templates(self, obj):
        return obj.templates.count()
        
class MessageTemplateSaveSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = MessageTemplate
        fields = '__all__'
    
    def create(self, validated_data):
        
        validated_data['token'] = generate_token(MessageTemplate)
        return super().create(validated_data)
        

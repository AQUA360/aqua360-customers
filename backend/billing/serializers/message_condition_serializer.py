from rest_framework import serializers

from ..models import MessageCondition
        
class MessageConditionSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = MessageCondition
        fields = '__all__'
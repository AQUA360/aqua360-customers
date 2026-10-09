from rest_framework import serializers

from billing.serializers.message_condition_serializer import MessageConditionSerializer

from ..models import Message, MessageCondition


class MessageMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'
        
class MessageSerializer(serializers.ModelSerializer):
    conditions = MessageConditionSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    condition_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    class Meta:
        model = Message
        fields = '__all__'
    
    def create(self, validated_data):
        condition_ids = validated_data.pop('condition_ids')
        message = Message.objects.create(**validated_data)
        for condition_id in condition_ids:
            condition_instance = MessageCondition.objects.get(id=condition_id)
            message.conditions.add(condition_instance)
        message.save()
        
        return message
    
    def update(self, instance, validated_data):
        condition_ids = validated_data.pop('condition_ids')
        
        previous_conditions = instance.conditions.all()
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        #if any previous condition is not in the new list, remove it
        for condition in previous_conditions:
            if condition.id not in condition_ids:
                condition.delete()
                
        instance.conditions.clear()
        for condition_id in condition_ids:
            condition_instance = MessageCondition.objects.get(id=condition_id)
            instance.conditions.add(condition_instance)
        instance.save()
        
        return instance
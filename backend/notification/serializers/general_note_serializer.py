import uuid
from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from ..models import *

class GeneralNoteSerializer(serializers.ModelSerializer):
    
    user = UserMinimalSerializer(required=False, allow_null=True)
    read_by = UserMinimalSerializer(many=True, required=False, allow_null=True)
    
    class Meta:
        model = GeneralNote
        fields = '__all__'
    
    def create(self, validated_data):
        
        request = self.context.get('request')
        user = request.user if request else None
        
        token = uuid.uuid4()
        validated_data['token'] = token
        validated_data['user'] = user
        
        instance = GeneralNote.objects.create(**validated_data)
        instance.read_by.add(user)
        instance.save()
        
        return instance

    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        instance.read_by.add(user)
        instance.save()
        
        return super().update(instance, validated_data)
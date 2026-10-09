from rest_framework import serializers
from django_filters import rest_framework as filters

from auth.serializers import UserMinimalSerializer
from ..models import *

class NotificationSerializer(serializers.ModelSerializer):
    
    handle_all = serializers.BooleanField(required=False, allow_null=True, write_only=True)
    
    read_by = UserMinimalSerializer(many=True, required=False, allow_null=True)
    archived_by = UserMinimalSerializer(many=True, required=False, allow_null=True)
    
    class Meta:
        model = Notification
        fields = '__all__'
    
    def update(self, instance, validated_data):
        print("in update")
        handle_all = validated_data.pop('handle_all', None)
        is_seen = validated_data.pop('is_seen', None)
        is_active = validated_data.get('is_active', None)
        
        request = self.context.get('request')
        user = request.user if request else None
        
        instance = super().update(instance, validated_data)
        
        if handle_all:
            notifications = Notification.objects.filter(is_active=True)
            if is_seen is not None:
                for notification in notifications:
                    if notification.read_by.filter(id=user.id).exists():
                        notification.read_by.remove(user)
                    else:
                        notification.read_by.add(user)
            if is_active is not None:
                for notification in notifications:
                    if notification.archived_by.filter(id=user.id).exists():
                        notification.archived_by.remove(user)
                    else:
                        notification.archived_by.add(user)
        else:
            if is_seen is not None:
                if instance.read_by.filter(id=user.id).exists():
                    instance.read_by.remove(user)
                else:
                    instance.read_by.add(user)
            if is_active is not None:
                if instance.archived_by.filter(id=user.id).exists():
                    instance.archived_by.remove(user)
                else:
                    instance.archived_by.add(user)
                
        return instance
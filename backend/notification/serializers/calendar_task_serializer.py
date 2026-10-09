import uuid
from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from ..models import *

class CalendarTaskSerializer(serializers.ModelSerializer):

    user = UserMinimalSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source='user', queryset=User.objects.all(), write_only=True, required=False, allow_null=True)
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    all_users = serializers.BooleanField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = CalendarTask
        fields = '__all__'

    def _apply_assignment(self, validated_data):
        """Sets validated_data['user'] from 'all_users'/'user_id' when either was
        sent. Leaves 'user' untouched when neither is present, so payloads that
        only update e.g. task_done/color don't silently reassign the task."""
        has_all_users = 'all_users' in validated_data
        all_users = validated_data.pop('all_users', None)
        has_user = 'user' in validated_data

        if not has_all_users and not has_user:
            return

        if all_users:
            validated_data['user'] = None
        elif not has_user:
            request = self.context.get('request')
            validated_data['user'] = request.user if request else None
        # else: validated_data['user'] already holds the chosen user_id

    def create(self, validated_data):
        self._apply_assignment(validated_data)
        if 'user' not in validated_data:
            request = self.context.get('request')
            validated_data['user'] = request.user if request else None
        validated_data['token'] = uuid.uuid4()

        return CalendarTask.objects.create(**validated_data)

    def update(self, instance, validated_data):
        self._apply_assignment(validated_data)

        return super().update(instance, validated_data)
from rest_framework import serializers
from ..models import ClaimRequestStepTemplate

class ClaimRequestStepTemplateListSerializer(serializers.ModelSerializer):
    next_step_name = serializers.CharField(source='next_step.name', read_only=True, allow_null=True)
    order_token = serializers.CharField(source='order_type.token', read_only=True, allow_null=True)
    order_type_name = serializers.CharField(source='order_type.name', read_only=True, allow_null=True)
    document_type_name = serializers.CharField(source='document_type.name', read_only=True, allow_null=True)
    total_previous_steps = serializers.SerializerMethodField()
    
    class Meta:
        model = ClaimRequestStepTemplate
        fields = [
            'id',
            'token',
            'name',
            'created_at',
            'updated_at',
            'duration',
            'duration_type',
            'next_step_name',
            'order_token',
            'order_type_name',
            'document_type_name',
            'total_previous_steps',
            'description',
            'position'
        ]
    
    def get_total_previous_steps(self, obj):
        count = 0
        current_step = obj
        
        while current_step.next_step:
            count += 1
            current_step = current_step.next_step
            
        return count 
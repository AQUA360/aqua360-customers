from rest_framework import serializers
from ..models import ClaimRequest
from .claim_request_step_serializer import ClaimRequestStepSerializer
from django.db.models import Sum

class ClaimRequestListSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name')
    status_color = serializers.CharField(source='status.color')
    total_payments = serializers.SerializerMethodField()
    total_contracts = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    current_step = ClaimRequestStepSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = ClaimRequest
        fields = [
            'id',
            'token',
            'created_at',
            'updated_at',
            'status',
            'status_name',
            'status_color',
            'template',
            'current_step',
            'total_payments',
            'total_contracts',
            'amount',
            'due_date',
            'description',
            'name'
        ]
    
    def get_amount(self, obj):
        # Utilitzem el camp amount que ja està calculat al queryset
        try:
            return obj.amount or 0
        except:
            return 0
    
    def get_total_payments(self, obj):
        # Utilitzem el camp total_payments que ja està calculat al queryset
        try:
            return obj.total_payments or 0
        except:
            return 0
    
    def get_total_contracts(self, obj):
        # Utilitzem el camp total_contracts que ja està calculat al queryset
        try:
            return obj.total_contracts or 0 
        except:
            return 0
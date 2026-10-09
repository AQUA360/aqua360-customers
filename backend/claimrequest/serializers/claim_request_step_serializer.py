from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from communication.serializers.communication_process_serializer import CommunicationProcessListSerializer
from coredata.models import ConfigProject
from documentmanager.serializers import DocumentSerializer
from pricing.serializers.price_rate_serializer import PriceRateSerializer
from ..models import ClaimRequestStep, ClaimRequestStepDocument
from .claim_request_step_template_serializer import ClaimRequestStepTemplateSerializer
from .value_objects_serializer import ClaimDocumentTypeSerializer


class ClaimRequestStepDocumentSerializer(serializers.ModelSerializer):
    file = DocumentSerializer(read_only=True, allow_null=True)
    user = UserMinimalSerializer(read_only=True, allow_null=True)
    
    class Meta:
        model = ClaimRequestStepDocument
        fields = '__all__'

class ClaimRequestStepSerializer(serializers.ModelSerializer):
    step_template = ClaimRequestStepTemplateSerializer(read_only=True)
    next_step_id = serializers.IntegerField(source='next_step.id', read_only=True, allow_null=True)
    next_step_token = serializers.CharField(source='next_step.token', read_only=True, allow_null=True)
    next_step_name = serializers.CharField(source='next_step.name', read_only=True, allow_null=True)
    order_type = serializers.CharField(source='order_type.name', read_only=True, allow_null=True)
    document_type = ClaimDocumentTypeSerializer(read_only=True, allow_null=True)
    end_step_date = serializers.DateField(allow_null=True, required=False)
    previous_step_due_date = serializers.DateField(allow_null=True, required=False)
    communication_process = CommunicationProcessListSerializer(read_only=True, allow_null=True)
    documents = ClaimRequestStepDocumentSerializer(many=True, read_only=True, allow_null=True)
    price_rates = PriceRateSerializer(many=True, read_only=True, allow_null=True)
    total_claim_request_payments = serializers.SerializerMethodField(read_only=True, allow_null=True)
    
    class Meta:
        model = ClaimRequestStep
        fields = '__all__' 
    
    def get_previous_step_due_date(self, obj):
        previous_step = ClaimRequestStep.objects.filter(next_step=obj).first()
        if previous_step:
            return previous_step.due_date
        return None

    def get_total_claim_request_payments(self, obj):
        status_token_config = ConfigProject.objects.filter(
            token__in=[
                'payment_status_cancelled_token', #-6
                'payment_status_dropped_token', #-7
                'payment_status_payoff_token' #-4
            ]
        )
        payments = obj.claim_request_payments.filter(
            payment__is_active=True,
        ).exclude(payment__status__token__in=status_token_config.values_list('value', flat=True)).distinct()
        return payments.count()
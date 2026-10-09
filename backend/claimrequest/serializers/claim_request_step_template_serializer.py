from rest_framework import serializers

from pricing.serializers.price_rate_serializer import PriceRateSerializer
from ..models import ClaimRequestStepTemplate
from .value_objects_serializer import ClaimDocumentTypeSerializer
from .claim_request_step_template_list_serializer import ClaimRequestStepTemplateListSerializer

class ClaimRequestStepTemplateSerializer(serializers.ModelSerializer):
    next_step_id = serializers.IntegerField(source='next_step.id', read_only=True, allow_null=True)
    next_step_token = serializers.CharField(source='next_step.token', read_only=True, allow_null=True)
    next_step_name = serializers.CharField(source='next_step.name', read_only=True, allow_null=True)
    order_type = serializers.CharField(source='order_type.name', read_only=True, allow_null=True)
    
    previous_steps = serializers.SerializerMethodField()
    related_steps = serializers.SerializerMethodField()
    
    document_type = ClaimDocumentTypeSerializer(read_only=True, allow_null=True)
    price_rates = PriceRateSerializer(many=True, read_only=True, allow_null=True)
    
    class Meta:
        model = ClaimRequestStepTemplate
        fields = '__all__' 
    
    def get_previous_steps(self, obj):
        previous_steps = []
        current_step = obj
        previous_step = ClaimRequestStepTemplate.objects.filter(next_step=obj).first()
        while previous_step:
            previous_steps.append(previous_step)
            previous_step = ClaimRequestStepTemplate.objects.filter(next_step=previous_step).first()
        
        return ClaimRequestStepTemplateListSerializer(previous_steps, many=True).data
    
    def get_related_steps(self, obj):
        related_steps = []
        while obj.next_step:
            related_steps.append(obj.next_step)
            obj = obj.next_step
        return ClaimRequestStepTemplateListSerializer(related_steps, many=True).data
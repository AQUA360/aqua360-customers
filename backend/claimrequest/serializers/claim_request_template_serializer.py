from rest_framework import serializers
from ..models import ClaimRequestTemplate
from .claim_request_step_template_serializer import ClaimRequestStepTemplateSerializer

class ClaimRequestTemplateSerializer(serializers.ModelSerializer):
    steps = serializers.SerializerMethodField()

    def get_steps(self, obj):
        steps = obj.steps.all().order_by('position')
        return ClaimRequestStepTemplateSerializer(steps, many=True).data
    
    class Meta:
        model = ClaimRequestTemplate
        fields = '__all__' 
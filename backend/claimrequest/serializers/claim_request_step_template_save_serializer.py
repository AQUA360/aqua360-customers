from rest_framework import serializers
from ..models import ClaimRequestStepTemplate

class ClaimRequestStepTemplateSaveSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ClaimRequestStepTemplate
        fields = '__all__'
    
    def create(self, validated_data):
        print("Creating claim step template with data:", validated_data)
        return super().create(validated_data) 
    
    def update(self, instance, validated_data):
        print("Updating claim step template with data:", validated_data)
        return super().update(instance, validated_data)
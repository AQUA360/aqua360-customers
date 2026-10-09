from rest_framework import serializers

from contract.serializers.value_objects_serializer import BonificationTypeDocumentationTypeSerializer
from ..models import (  BonificationDocumentation)

class BonificationDocumentationSerializer(serializers.ModelSerializer):
    type = BonificationTypeDocumentationTypeSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = BonificationDocumentation
        fields = '__all__'
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['name'] = instance.type.name if instance.type else None
        return representation


class BonificationDocumentationSaveSerializer(serializers.ModelSerializer):        
    class Meta:
        model = BonificationDocumentation
        fields = '__all__'

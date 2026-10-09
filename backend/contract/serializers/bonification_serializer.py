from rest_framework import serializers
from contract.serializers.bonification_documentation_serializer import BonificationDocumentationSerializer
from coredata.serializers import PersonSerializer
from coredata.utils.name_utils import generate_token
from .variable_serializer import VariableSerializer
from ..models import (  Bonification)
from .bonification_type_serializer import BonificationTypeSerializer


class BonificationSerializer(serializers.ModelSerializer):
    
    person = PersonSerializer(read_only=True, required=False, allow_null=True)
    bonification_type = BonificationTypeSerializer(read_only=True, required=False, allow_null=True)    
    documentation_files = BonificationDocumentationSerializer(many=True, required=False, allow_null=True)
    variables = VariableSerializer(many=True, required=False, allow_null=True)
    is_aca_bonification = serializers.SerializerMethodField()
    sent_to_aca = serializers.SerializerMethodField()

    class Meta:
        model = Bonification
        fields = '__all__'

    def get_is_aca_bonification(self, obj):
        return hasattr(obj, 'aca_request')

    def get_sent_to_aca(self, obj):
        aca_request = getattr(obj, 'aca_request', None)
        return bool(aca_request and aca_request.sent_at)


class BonificationSaveSerializer(serializers.ModelSerializer):        
    class Meta:
        model = Bonification
        fields = '__all__'
    
    def create(self, validated_data):
        validated_data['token'] = generate_token(Bonification)
        return super().create(validated_data)

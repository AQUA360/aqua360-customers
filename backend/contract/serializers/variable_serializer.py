from rest_framework import serializers
from django_filters import rest_framework as filters

from coredata.utils.name_utils import generate_token

from ..models import ( Variable )
from .value_objects_serializer import VariableTypeSerializer

class VariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variable
        fields = '__all__'
    
    
class VariableSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variable
        fields = '__all__'

    def validate(self, attrs):
        """La variable de membres de l'ampliació de trams de l'ACA ha d'arribar al mínim
        de persones (`aca_tram_min_persons`). No es valida en desactivar-la, perquè una
        variable antiga amb un valor per sota del mínim es pugui donar de baixa."""
        from ..utils.aca_tram_service import aca_tram_members_error

        instance = self.instance
        is_active = attrs.get('is_active', instance.is_active if instance else True)
        if not is_active:
            return attrs
        variable_type = attrs.get('type', instance.type if instance else None)
        value = attrs.get('value', instance.value if instance else None)
        error = aca_tram_members_error(variable_type, value)
        if error:
            raise serializers.ValidationError({'value': error})
        return attrs

    def create(self, validated_data):
        type = validated_data['type']
        if type.data_type == 'bool':
            validated_data['value'] = "True"
        validated_data['token'] = generate_token(Variable)
        instance = super().create(validated_data)
        return instance
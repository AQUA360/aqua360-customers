from rest_framework import serializers
from ..models import ( ClauseTemplate )

class ClauseTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClauseTemplate
        fields = '__all__'
from rest_framework import serializers

from coredata.utils.name_utils import generate_token

from ..models import Publication

class PublicationSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Publication
        fields = '__all__'
    
    def create(self, validated_data):
        validated_data["token"] = generate_token(Publication)
        return super().create(validated_data)

class PublicationMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = ['id', 'token', 'name', 'boe_number', 'boe_date']
from rest_framework import serializers
from claimrequest.models import ClaimDocumentType

class ClaimDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimDocumentType
        fields = '__all__' 
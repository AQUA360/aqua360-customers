from rest_framework import serializers

from billing.serializers.payment_serializer import PaymentMinimalSerializer

from ..models import DocumentSEPA, DocumentSEPALine

class DocumentSEPALineSerializer(serializers.ModelSerializer):

    payments = PaymentMinimalSerializer(many=True, read_only=True)
    
    class Meta:
        model = DocumentSEPALine
        fields = '__all__'

class DocumentSEPASerializer(serializers.ModelSerializer):
    
    lines = DocumentSEPALineSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = DocumentSEPA
        fields = '__all__'
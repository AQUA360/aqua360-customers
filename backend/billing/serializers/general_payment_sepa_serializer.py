from rest_framework import serializers
from billing.models import GeneralPaymentSepaDocument

class GeneralPaymentSepaDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralPaymentSepaDocument
        fields = '__all__'


class GeneralPaymentSepaDocumentSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralPaymentSepaDocument
        fields = '__all__'
        
    def create(self,validated_data):
        instance = super().create(validated_data)
        return instance
from django.conf import settings
from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from contract.serializers.value_objects_serializer import PaymentTypeSerializer
from coredata.serializers import PersonAddressSerializer, PersonBankSerializer, PersonContactSerializer, PersonSerializer
from ..models import ContractDataChange

class ContractDataChangeSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ContractDataChange
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['new_payment_type'] = PaymentTypeSerializer(instance.new_payment_type).data if instance.new_payment_type else None
        representation['previous_payment_type'] = PaymentTypeSerializer(instance.previous_payment_type).data if instance.previous_payment_type else None
        
        representation['new_payment'] = PersonBankSerializer(instance.new_payment).data if instance.new_payment else None
        representation['previous_payment'] = PersonBankSerializer(instance.previous_payment).data if instance.previous_payment else None
        
        representation['new_person_contact_email'] = PersonContactSerializer(instance.new_person_contact_email).data if instance.new_person_contact_email else None
        representation['previous_person_contact_email'] = PersonContactSerializer(instance.previous_person_contact_email).data if instance.previous_person_contact_email else None
        
        representation['new_address_contact'] = PersonAddressSerializer(instance.new_address_contact).data if instance.new_address_contact else None
        representation['previous_address_contact'] = PersonAddressSerializer(instance.previous_address_contact).data if instance.previous_address_contact else None
        
        representation['new_address_billing'] = PersonAddressSerializer(instance.new_address_billing).data if instance.new_address_billing else None
        representation['previous_address_billing'] = PersonAddressSerializer(instance.previous_address_billing).data if instance.previous_address_billing else None
        
        representation['user'] = UserMinimalSerializer(instance.user).data if instance.user else None
        
        return representation
    
    def create(self, validated_data):

        contract = validated_data.get('contract')
        validated_data['user'] = self.context['request'].user
        tenant_change = ContractDataChange.objects.create(**validated_data)

        new_language = validated_data.get('new_language')
        if contract and new_language and contract.language != new_language:
            contract.language = new_language
            contract.save(update_fields=['language'])

        return tenant_change
    
    
    
    
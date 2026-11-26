from django.conf import settings
from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from contract.serializers.value_objects_serializer import PaymentTypeSerializer
from coredata.serializers import PersonAddressSerializer, PersonBankSerializer, PersonContactSerializer, PersonSerializer
from ..models import ContractDataChange

class ContractDataChangeSerializer(serializers.ModelSerializer):

    # Camps d'històric (valor anterior i nou) que apunten a dades de la persona. Si el registre
    # ja no existeix (p. ex. un contacte esborrat mentre s'editava), es desa buit: el registre
    # del canvi no ha de bloquejar el desat del contracte.
    HISTORY_FK_FIELDS = (
        'new_payment', 'previous_payment',
        'new_payment_type', 'previous_payment_type',
        'new_person_contact_email', 'previous_person_contact_email',
        'new_address_contact', 'previous_address_contact',
        'new_address_billing', 'previous_address_billing',
    )

    class Meta:
        model = ContractDataChange
        fields = '__all__'

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        for field_name in self.HISTORY_FK_FIELDS:
            value = data.get(field_name) if hasattr(data, 'get') else None
            if value in (None, ''):
                continue
            related_model = ContractDataChange._meta.get_field(field_name).related_model
            try:
                exists = related_model.objects.filter(pk=value).exists()
            except (TypeError, ValueError):
                exists = False
            if not exists:
                data[field_name] = None
        return super().to_internal_value(data)

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
    
    
    
    
from django.conf import settings
from rest_framework import serializers
from billing.models import GeneralPayment
from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from coredata.models import PersonAddress, PersonBank, PersonContact
from coredata.serializers import PersonMinimalSerializer, PersonSerializer, PersonBankSerializer
from .value_objects_serializer import ContractSurrogationDocumentTypeSerializer, ContractSurrogationTypeSerializer
from ..models import Contract, ContractSurrogation, ContractSurrogationDocument, PaymentType

class ContractSurrogationDocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContractSurrogationDocument
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        representation['contract_surrogation_document_type'] = ContractSurrogationDocumentTypeSerializer(instance.contract_surrogation_document_type).data if instance.contract_surrogation_document_type else None

        return representation

class ContractSurrogationSerializer(serializers.ModelSerializer):
    
    documents = ContractSurrogationDocumentSerializer(many=True, read_only=True)
    new_payment = GeneralPaymentSerializer(read_only=True, required=False, allow_null=True)
    payment_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = ContractSurrogation
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['new_holder'] = PersonMinimalSerializer(instance.new_holder).data if instance.new_holder else None
        representation['previous_holder'] = PersonMinimalSerializer(instance.previous_holder).data if instance.previous_holder else None
        representation['previous_payment'] = GeneralPaymentSerializer(instance.previous_payment).data if instance.previous_payment else None
        representation['type'] = ContractSurrogationTypeSerializer(instance.type).data
        
        return representation
    
    def create(self, validated_data):
        new_payment_person_bank = self.initial_data.get('new_payment').get('person_bank') if self.initial_data.get('new_payment') else None
        new_payment_type = self.initial_data.get('new_payment').get('type') if self.initial_data.get('new_payment') else None
        new_payment_data = None
        new_payment = None
        payment_id = validated_data.pop('payment_id', None)
        if new_payment_person_bank:
            new_payment_person_bank, _ = PersonBank.objects.get_or_create(id=new_payment_person_bank)

        if new_payment_type:
            new_payment_type, _ = PaymentType.objects.get_or_create(id=new_payment_type)

        if new_payment_type:
            new_payment_data = {
                'IBAN': new_payment_person_bank,
                'type': new_payment_type
            }

        if new_payment_data or payment_id:
            if payment_id and payment_id != '' and payment_id != None and int(payment_id) > 0:
                print("getting payment")
                new_payment = GeneralPayment.objects.get(id=payment_id)
            else:
                print("creating payment")
                new_payment = GeneralPayment.objects.create(**new_payment_data, token = new_payment_person_bank)
            validated_data['new_payment'] = new_payment
        
        contract = validated_data.get('contract')
        contract_surrogation = ContractSurrogation.objects.create(**validated_data)

        if contract:
            contract.holder = contract_surrogation.new_holder
            if contract.piggy_bank:
                contract.piggy_bank.person = contract_surrogation.new_holder
                contract.piggy_bank.save()
            contract.payment = contract_surrogation.new_payment if new_payment else None

            # L'adreça (propietat/punt de subministrament) es manté igual, però es
            # re-crea sota el nou titular sense arrossegar dades personals de l'antic
            # (com "attention_to", que sol portar el nom de contacte de l'antic titular).
            if contract.address_billing and contract.address_contact and (contract.address_billing == contract.address_contact or contract.address_billing.address_id == contract.address_contact.address_id):
                new_address, _ = PersonAddress.objects.get_or_create(
                    token = "SR/"+contract.token,
                    address = contract.address_billing.address,
                    person = contract_surrogation.new_holder,
                    defaults = {'attention_to': None}
                )
                contract.address_billing = new_address
                contract.address_contact = new_address
            else:
                if contract.address_billing:
                    new_address_billing, _ = PersonAddress.objects.get_or_create(
                        token = "SR/"+contract.token,
                        address = contract.address_billing.address,
                        person = contract_surrogation.new_holder,
                        defaults = {'attention_to': None}
                    )
                    contract.address_billing = new_address_billing
                if contract.address_contact:
                    new_address_contact, _ = PersonAddress.objects.get_or_create(
                        token = "SR/"+contract.token,
                        address = contract.address_contact.address,
                        person = contract_surrogation.new_holder,
                        defaults = {'attention_to': None}
                    )
                    contract.address_contact = new_address_contact

            # El contacte (email/telèfon) és una dada personal de l'antic titular:
            # no es copia mai cap al nou titular, es deixa buit perquè n'aporti un propi.
            contract.person_contact_email = None
            contract.contacts.clear()
            contract.person_contact_sms.clear()
            contract.save()
        
        return contract_surrogation
   
    
    
    
    
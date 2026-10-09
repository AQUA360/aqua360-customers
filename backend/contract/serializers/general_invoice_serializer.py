from rest_framework import serializers

from billing.models import GeneralPayment
from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from coredata.models import ConfigProject, PersonAddress
from coredata.serializers import PersonAddressSerializer, PersonMinimalSerializer,PersonMinimalContractSerializer
from contract.serializers.contract_serializer import ContractGeneralInvoiceSerializer
from ..models import Contract, GeneralInvoice

class GeneralInvoiceSerializer(serializers.ModelSerializer):
    contracts = ContractGeneralInvoiceSerializer(many=True, read_only=True, required=False, allow_null=True)
    payment = GeneralPaymentSerializer(read_only=True, required=False, allow_null=True)
    address_billing = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    address_contact = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    
    contract_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    payment_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_billing_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    address_contact_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = GeneralInvoice
        fields = '__all__'
    
    def create(self, validated_data):
        contract_ids = validated_data.pop('contract_ids', None)
        payment_id = validated_data.pop('payment_id', None)
        address_billing_id = validated_data.pop('address_billing_id', None)
        address_contact_id = validated_data.pop('address_contact_id', None)
        
        obj = GeneralInvoice.objects.create(**validated_data)

        if payment_id:
            payment = GeneralPayment.objects.get(id=payment_id)
            obj.payment = payment
        if address_billing_id:
            address_billing = PersonAddress.objects.get(id=address_billing_id)
            obj.address_billing = address_billing
        if address_contact_id:
            address_contact = PersonAddress.objects.get(id=address_contact_id)
            obj.address_contact = address_contact
        if contract_ids:
            try:
                contracts = Contract.objects.filter(id__in=contract_ids)
                contracts.update(general_invoice=obj)
            except Exception as e:
                raise Exception(f"Error getting contracts: {e}")
        
        obj.save()
        return obj
    
    def update(self, instance, validated_data):
        contract_ids = validated_data.pop('contract_ids', None)
        payment_id = validated_data.pop('payment_id', None)
        address_billing_id = validated_data.pop('address_billing_id', None)
        address_contact_id = validated_data.pop('address_contact_id', None)
        if payment_id:
            payment = GeneralPayment.objects.get(id=payment_id)
            instance.payment = payment
        if address_billing_id:
            address_billing = PersonAddress.objects.get(id=address_billing_id)
            instance.address_billing = address_billing
        if address_contact_id:
            address_contact = PersonAddress.objects.get(id=address_contact_id)
            instance.address_contact = address_contact
        if contract_ids:
            try:
                contracts = Contract.objects.filter(id__in=contract_ids)
                contract_with_gen_invoice = Contract.objects.filter(general_invoice=instance).exclude(id__in=contract_ids)
                
                contracts.update(general_invoice=instance)
                contract_with_gen_invoice.update(general_invoice=None)
            except Exception as e:
                raise Exception(f"Error getting contracts: {e}")
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
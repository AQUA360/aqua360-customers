"""Serializer lleuger per GET/PUT del formulari de modificació de dades del contracte."""
from rest_framework import serializers

from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from contract.models import Contract, ContractRepresentative
from contract.serializers.value_objects_serializer import ContractRepresentativeTypeSerializer
from coredata.models import Person
from coredata.serializers import (
    PersonAddressMinimalSerializer,
    PersonBankMinimalSerializer,
    PersonContactSerializer,
    PersonAddressSerializer,
)


class PersonDataChangeSerializer(serializers.ModelSerializer):
    """Persona amb adreces sense consultes extra de distinct (usa prefetch)."""
    addresses = serializers.SerializerMethodField()
    contacts = PersonContactSerializer(many=True, read_only=True)
    banks = PersonBankMinimalSerializer(many=True, read_only=True)

    class Meta:
        model = Person
        fields = [
            'id',
            'token',
            'name',
            'surname',
            'is_juridic',
            'vulnerability_level',
            'addresses',
            'contacts',
            'banks',
        ]

    def get_addresses(self, instance):
        seen_address_ids = set()
        serialized = []
        for person_address in instance.addresses.all():
            address_id = person_address.address_id
            if address_id in seen_address_ids:
                continue
            seen_address_ids.add(address_id)
            serialized.append(PersonAddressMinimalSerializer(person_address).data)
        return serialized


class ContractRepresentativeDataChangeSerializer(serializers.ModelSerializer):
    person = PersonDataChangeSerializer(read_only=True)
    type = ContractRepresentativeTypeSerializer(read_only=True)

    class Meta:
        model = ContractRepresentative
        fields = ['id', 'person', 'type']


class ContractDataChangeEditSerializer(serializers.ModelSerializer):
    holder = PersonDataChangeSerializer(read_only=True)
    owner = PersonDataChangeSerializer(read_only=True, allow_null=True)
    tenant = PersonDataChangeSerializer(read_only=True, allow_null=True)
    representatives = ContractRepresentativeDataChangeSerializer(
        many=True,
        read_only=True,
    )
    address_billing = PersonAddressSerializer(read_only=True, allow_null=True)
    address_contact = PersonAddressSerializer(read_only=True, allow_null=True)
    payment = GeneralPaymentSerializer(read_only=True, allow_null=True)
    person_contact_email = PersonContactSerializer(read_only=True, allow_null=True)
    person_contact_sms = PersonContactSerializer(many=True, read_only=True)
    contacts = PersonContactSerializer(many=True, read_only=True)
    supply_point_default = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            'id',
            'token',
            'total_persons',
            'simplified_invoice',
            'remittance_date',
            'communication_type',
            'holder',
            'owner',
            'tenant',
            'representatives',
            'address_billing',
            'address_contact',
            'payment',
            'person_contact_email',
            'person_contact_sms',
            'contacts',
            'supply_point_default',
            'registration_date',
            'language',
        ]

    def get_supply_point_default(self, obj):
        if not obj.supply_point_default_id:
            return None
        return {'id': obj.supply_point_default_id}

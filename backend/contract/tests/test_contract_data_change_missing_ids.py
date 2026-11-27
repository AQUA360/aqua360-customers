from django.test import TestCase

from contract.serializers.contract_data_change_serializer import ContractDataChangeSerializer


class ContractDataChangeMissingIdsTest(TestCase):
    """El registre d'històric d'un canvi de dades no ha de fallar si un valor anterior o nou
    apunta a un registre que ja no existeix (p. ex. un contacte esborrat mentre s'editava)."""

    MISSING_ID = 999999999

    def test_missing_history_ids_are_saved_empty(self):
        data = {field: self.MISSING_ID for field in ContractDataChangeSerializer.HISTORY_FK_FIELDS}
        serializer = ContractDataChangeSerializer(data=data)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        for field in ContractDataChangeSerializer.HISTORY_FK_FIELDS:
            self.assertIsNone(serializer.validated_data.get(field), field)

    def test_invalid_history_id_value_is_saved_empty(self):
        serializer = ContractDataChangeSerializer(data={'previous_person_contact_email': 'abc'})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get('previous_person_contact_email'))

    def test_empty_history_ids_are_accepted(self):
        serializer = ContractDataChangeSerializer(data={'previous_person_contact_email': None, 'new_address_billing': ''})

        self.assertTrue(serializer.is_valid(), serializer.errors)

import importlib

from django.apps import apps
from django.test import TestCase

from contract.models import ContractRequestType
from contract.serializers.contract_request_serializer import ContractRequestSaveSerializer
from pricing.models import PriceRate


class ChangeOfNameRegistrationPriceRatesTest(TestCase):
    """Les altes i els canvis de nom agafen tarifes de contractació diferents del tipus."""

    def setUp(self):
        self.registration_rate = PriceRate.objects.create(token="ALTA")
        self.change_of_name_rate = PriceRate.objects.create(token="CANVI-NOM")
        self.shared_rate = PriceRate.objects.create(token="COMUNA")

        self.type = ContractRequestType.objects.create(token="domestic", name="Domèstic")
        self.type.registration_price_rates.set([self.registration_rate, self.shared_rate])
        self.type.change_of_name_registration_price_rates.set([self.change_of_name_rate, self.shared_rate])

        self.other_type = ContractRequestType.objects.create(token="agricola", name="Agrícola")
        self.other_rate = PriceRate.objects.create(token="ALTA-AGRICOLA")
        self.other_change_of_name_rate = PriceRate.objects.create(token="CANVI-NOM-AGRICOLA")
        self.other_type.registration_price_rates.set([self.other_rate])
        self.other_type.change_of_name_registration_price_rates.set([self.other_change_of_name_rate])

    def _create(self, **data):
        serializer = ContractRequestSaveSerializer(data={"token": "REQ-TEST", "type": self.type.id, **data})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_new_request_gets_registration_price_rates(self):
        request = self._create()
        self.assertEqual(set(request.registration_price_rates.all()), {self.registration_rate, self.shared_rate})

    def test_change_of_name_gets_change_of_name_price_rates(self):
        request = self._create(is_change_of_name=True)
        self.assertEqual(set(request.registration_price_rates.all()), {self.change_of_name_rate, self.shared_rate})

    def test_changing_type_keeps_the_change_of_name_list(self):
        request = self._create(is_change_of_name=True)
        request.type = self.other_type
        request.save()
        self.assertEqual(set(request.registration_price_rates.all()), {self.other_change_of_name_rate})

    def test_changing_type_of_new_request_uses_registration_list(self):
        request = self._create()
        request.type = self.other_type
        request.save()
        self.assertEqual(set(request.registration_price_rates.all()), {self.other_rate})

    def test_migration_copies_registration_price_rates(self):
        self.type.change_of_name_registration_price_rates.clear()
        migration = importlib.import_module(
            "contract.migrations.0246_contract_request_type_change_of_name_registration_price_rates"
        )

        migration.copy_registration_price_rates(apps, None)

        self.assertEqual(
            set(self.type.change_of_name_registration_price_rates.all()),
            {self.registration_rate, self.shared_rate},
        )

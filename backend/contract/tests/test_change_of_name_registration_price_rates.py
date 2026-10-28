import importlib

from django.apps import apps
from django.test import TestCase

from contract.models import ContractRequestType
from contract.serializers.contract_request_serializer import ContractRequestSaveSerializer
from contract.serializers.contract_request_type_serializer import ContractRequestTypeSerializer
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

    def test_marking_as_change_of_name_with_same_type_switches_list(self):
        request = self._create()
        request.is_change_of_name = True
        request.save()
        self.assertEqual(set(request.registration_price_rates.all()), {self.change_of_name_rate, self.shared_rate})

    def test_type_creation_accepts_price_rate_ids(self):
        serializer = ContractRequestTypeSerializer(data={
            "token": "nou",
            "name": "Nou",
            "registration_price_rates_ids": [self.registration_rate.id],
            "change_of_name_registration_price_rates_ids": [self.change_of_name_rate.id],
        })
        serializer.is_valid(raise_exception=True)
        request_type = serializer.save()

        self.assertEqual(list(request_type.registration_price_rates.all()), [self.registration_rate])
        self.assertEqual(list(request_type.change_of_name_registration_price_rates.all()), [self.change_of_name_rate])

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


class ContractRequestKindFilterTest(TestCase):
    """El llistat de sol·licituds es pot filtrar per canvi de nom o nova alta."""

    def test_filters_by_is_change_of_name(self):
        from contract.filters.contract_request_filter import ContractRequestFilter
        from contract.models import ContractRequest

        new_request = ContractRequest.objects.create(token="REQ-ALTA")
        change_of_name = ContractRequest.objects.create(token="REQ-CANVI", is_change_of_name=True)
        queryset = ContractRequest.objects.all()

        self.assertEqual(list(ContractRequestFilter({"is_change_of_name": "true"}, queryset=queryset).qs), [change_of_name])
        self.assertEqual(list(ContractRequestFilter({"is_change_of_name": "false"}, queryset=queryset).qs), [new_request])
        self.assertEqual(ContractRequestFilter({}, queryset=queryset).qs.count(), 2)

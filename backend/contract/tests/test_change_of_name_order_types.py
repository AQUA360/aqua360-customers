import importlib

from django.apps import apps
from django.test import TestCase

from contract.models import Contract, ContractRequest, ContractRequestType, ContractTerminationRequest, ContractTerminationType
from contract.serializers.contract_request_serializer import ContractRequestSaveSerializer
from contract.serializers.value_objects_serializer import ContractTerminationRequestTypeSerializer
from order.models import OrderType


class ChangeOfNameOrderTypesTest(TestCase):
    """Les altes i els canvis de nom agafen tipus d'ordre diferents del tipus de sol·licitud."""

    def setUp(self):
        self.new_order_type = OrderType.objects.create(token="ALTA", name="Alta")
        self.change_of_name_order_type = OrderType.objects.create(token="CANVI-NOM", name="Canvi de nom")
        self.shared_order_type = OrderType.objects.create(token="COMUNA", name="Comuna")

        self.type = ContractRequestType.objects.create(token="domestic", name="Domèstic")
        self.type.order_types.set([self.new_order_type, self.shared_order_type])
        self.type.change_of_name_order_types.set([self.change_of_name_order_type, self.shared_order_type])

    def _create(self, **data):
        serializer = ContractRequestSaveSerializer(data={"token": "REQ-TEST", "type": self.type.id, **data})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_new_request_gets_order_types(self):
        request = self._create()
        self.assertEqual(set(request.order_types.all()), {self.new_order_type, self.shared_order_type})

    def test_change_of_name_gets_change_of_name_order_types(self):
        request = self._create(is_change_of_name=True)
        self.assertEqual(set(request.order_types.all()), {self.change_of_name_order_type, self.shared_order_type})

    def test_changing_the_flag_keeps_chosen_order_types(self):
        # El canvi de nom es decideix en crear la sol·licitud: després no es substitueixen les ordres triades
        request = self._create()
        request.is_change_of_name = True
        request.save()
        self.assertEqual(set(request.order_types.all()), {self.new_order_type, self.shared_order_type})

    def test_migration_copies_order_types(self):
        self.type.change_of_name_order_types.clear()
        migration = importlib.import_module("contract.migrations.0248_change_of_name_order_types_and_termination_type")

        migration.copy_order_types(apps, None)

        self.assertEqual(set(self.type.change_of_name_order_types.all()), {self.new_order_type, self.shared_order_type})


class ChangeOfNameTerminationTypeTest(TestCase):
    """Marcatge de les sol·licituds antigues vinculades a una baixa per canvi de nom."""

    def setUp(self):
        from coredata.models import ConfigProject

        # Els senyals de Contract la consulten en desar
        ConfigProject.objects.update_or_create(token='contract_terminated_status', defaults={'value': 'baixa'})
        self.change_of_name_type = ContractTerminationType.objects.create(token="canvi-titular", name="Canvi de titular")
        self.other_type = ContractTerminationType.objects.create(token="peticio", name="Petició del client")

    def _finished_request(self, token, termination_type):
        request = ContractRequest.objects.create(token=token)
        request.contract_termination_requests.add(ContractTerminationRequest.objects.create(type=termination_type))
        Contract.objects.create(token=token, contract_request=request)
        return request

    def _link(self, request, termination):
        serializer = ContractRequestSaveSerializer(
            request, data={"contract_termination_requests": [termination.id]}, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_linking_change_of_name_termination_keeps_new_request(self):
        # Una nova alta continua sent nova alta encara que doni de baixa el contracte anterior
        from pricing.models import PriceRate

        chosen_rate = PriceRate.objects.create(token="TRIADA")
        request = ContractRequest.objects.create(token="REQ-1")
        request.registration_price_rates.set([chosen_rate])
        self.change_of_name_type.is_change_of_name = True
        self.change_of_name_type.save()

        request = self._link(request, ContractTerminationRequest.objects.create(type=self.change_of_name_type))

        request.refresh_from_db()
        self.assertFalse(request.is_change_of_name)
        self.assertEqual(list(request.registration_price_rates.all()), [chosen_rate])

    def test_marking_termination_type_marks_linked_requests(self):
        linked = self._finished_request("REQ-1", self.change_of_name_type)
        other = self._finished_request("REQ-2", self.other_type)
        pending = ContractRequest.objects.create(token="REQ-3")
        pending.contract_termination_requests.add(ContractTerminationRequest.objects.create(type=self.change_of_name_type))

        serializer = ContractTerminationRequestTypeSerializer(
            self.change_of_name_type, data={"is_change_of_name": True}, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        linked.refresh_from_db()
        other.refresh_from_db()
        pending.refresh_from_db()
        self.assertTrue(linked.is_change_of_name)
        self.assertFalse(other.is_change_of_name)
        self.assertFalse(pending.is_change_of_name)

    def test_opscript_marks_configured_holder_change_type(self):
        from coredata.models import ConfigProject

        ConfigProject.objects.update_or_create(token='termination_type_holder_change', defaults={'value': 'canvi-titular'})
        linked = self._finished_request("REQ-1", self.change_of_name_type)
        other = self._finished_request("REQ-2", self.other_type)
        pending = ContractRequest.objects.create(token="REQ-3")
        pending.contract_termination_requests.add(ContractTerminationRequest.objects.create(type=self.change_of_name_type))

        importlib.import_module("contract.opscripts.0005_mark_change_of_name_requests").run()

        self.change_of_name_type.refresh_from_db()
        linked.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(self.change_of_name_type.is_change_of_name)
        pending.refresh_from_db()
        self.assertTrue(linked.is_change_of_name)
        self.assertFalse(other.is_change_of_name)
        self.assertFalse(pending.is_change_of_name)

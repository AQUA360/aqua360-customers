import importlib

from django.apps import apps
from django.test import TestCase

from contract.models import ContractRequest, ContractRequestType, ContractTerminationRequest, ContractTerminationType
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

    def test_marking_as_change_of_name_switches_order_types(self):
        request = self._create()
        request.is_change_of_name = True
        request.save()
        self.assertEqual(set(request.order_types.all()), {self.change_of_name_order_type, self.shared_order_type})

    def test_migration_copies_order_types(self):
        self.type.change_of_name_order_types.clear()
        migration = importlib.import_module("contract.migrations.0248_change_of_name_order_types_and_termination_type")

        migration.copy_order_types(apps, None)

        self.assertEqual(set(self.type.change_of_name_order_types.all()), {self.new_order_type, self.shared_order_type})


class ChangeOfNameTerminationTypeTest(TestCase):
    """Les sol·licituds vinculades a una baixa per canvi de nom es marquen com a canvi de nom."""

    def setUp(self):
        self.change_of_name_type = ContractTerminationType.objects.create(token="canvi-titular", name="Canvi de titular")
        self.other_type = ContractTerminationType.objects.create(token="peticio", name="Petició del client")

    def _link(self, request, termination):
        serializer = ContractRequestSaveSerializer(
            request, data={"contract_termination_requests": [termination.id]}, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_linking_change_of_name_termination_marks_request(self):
        self.change_of_name_type.is_change_of_name = True
        self.change_of_name_type.save()
        termination = ContractTerminationRequest.objects.create(type=self.change_of_name_type)

        request = self._link(ContractRequest.objects.create(token="REQ-1"), termination)

        self.assertTrue(request.is_change_of_name)

    def test_linking_other_termination_keeps_new_request(self):
        termination = ContractTerminationRequest.objects.create(type=self.other_type)

        request = self._link(ContractRequest.objects.create(token="REQ-1"), termination)

        self.assertFalse(request.is_change_of_name)

    def test_marking_termination_type_marks_linked_requests(self):
        linked = ContractRequest.objects.create(token="REQ-1")
        linked.contract_termination_requests.add(ContractTerminationRequest.objects.create(type=self.change_of_name_type))
        other = ContractRequest.objects.create(token="REQ-2")
        other.contract_termination_requests.add(ContractTerminationRequest.objects.create(type=self.other_type))

        serializer = ContractTerminationRequestTypeSerializer(
            self.change_of_name_type, data={"is_change_of_name": True}, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        linked.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(linked.is_change_of_name)
        self.assertFalse(other.is_change_of_name)

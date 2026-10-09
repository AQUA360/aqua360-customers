from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from contract.models import Contract, ContractRequest, ContractStatus, Variable, VariableType
from coredata.models import ConfigProject
from service.models import SupplyPoint
from contract.utils.contract_service import copy_change_of_name_variables


class ChangeOfNameVariablesTest(TestCase):

    def setUp(self):
        today = timezone.now().date()
        ConfigProject.objects.update_or_create(token='contract_active_token', defaults={'value': 'actiu'})
        ConfigProject.objects.update_or_create(token='contract_terminated_status', defaults={'value': 'baixa'})
        active_status = ContractStatus.objects.create(token='actiu', name='Actiu')
        inactive_status = ContractStatus.objects.create(token='baixa', name='Baixa')

        self.supply_point = SupplyPoint.objects.create(token="CN-SP")
        self.old_contract = Contract.objects.create(token="CN-OLD", status=active_status)
        self.old_contract.supply_points.add(self.supply_point)
        inactive_contract = Contract.objects.create(token="CN-OLDER", status=inactive_status)
        inactive_contract.supply_points.add(self.supply_point)

        self.contract_request = ContractRequest.objects.create(
            token="CN-REQ", is_change_of_name=True, supply_point_default=self.supply_point,
        )

        self.type_members = VariableType.objects.create(token="MEMBRES", name="Membres")
        self.type_aca = VariableType.objects.create(token="ACA_MEMBRES", name="ACA")
        self.type_social = VariableType.objects.create(token="tarifa_social", name="Social")
        self.type_expired = VariableType.objects.create(token="EXPIRED", name="Expired")
        self.type_inactive = VariableType.objects.create(token="INACTIVE", name="Inactive")
        self.type_other_contract = VariableType.objects.create(token="OTHER", name="Other")
        self.type_undated = VariableType.objects.create(token="classe-equip-inst", name="Classe equip. instal.")

        def add(contract, variable_type, **kwargs):
            return Variable.objects.create(
                contract=contract, type=variable_type, name=variable_type.name,
                value="4", start_at=today - timedelta(days=30), **kwargs,
            )

        add(self.old_contract, self.type_members, token="VR-1")
        add(self.old_contract, self.type_aca, token="VR-2")
        add(self.old_contract, self.type_social, token="VR-3")
        add(self.old_contract, self.type_expired, token="VR-4", end_at=today - timedelta(days=1))
        add(self.old_contract, self.type_inactive, token="VR-5", is_active=False)
        add(inactive_contract, self.type_other_contract, token="VR-6")
        Variable.objects.create(contract=self.old_contract, type=self.type_undated, value="1", token="VR-7")

    def test_copies_active_contract_variables_to_request_except_aca_and_social(self):
        copy_change_of_name_variables(self.contract_request)

        copied = {v.type_id: v for v in self.contract_request.variables.all()}
        self.assertEqual(set(copied), {self.type_members.id, self.type_undated.id})
        self.assertEqual(copied[self.type_members.id].value, "4")
        self.assertIsNone(copied[self.type_members.id].contract)
        self.assertIsNone(copied[self.type_members.id].bonification)
        # El contracte antic conserva les seves variables.
        self.assertEqual(self.old_contract.variables.count(), 6)

    def test_skips_types_already_on_the_request(self):
        Variable.objects.create(contract_request=self.contract_request, type=self.type_members, value="2", token="VR-REQ")

        copy_change_of_name_variables(self.contract_request)

        members = self.contract_request.variables.filter(type=self.type_members)
        self.assertEqual(members.count(), 1)
        self.assertEqual(members.first().value, "2")

from django.test import TestCase

from contract.models import ACABonificationRequest, Bonification, BonificationType, Contract, ContractStatus, Variable, VariableType
from coredata.models import ConfigProject


class BonificationVariableDeleteTest(TestCase):
    """En eliminar una bonificació s'eliminen les seves variables. En eliminar una
    variable, la bonificació es manté: és l'usuari qui decideix si l'elimina."""

    def setUp(self):
        ConfigProject.objects.update_or_create(token='contract_terminated_status', defaults={'value': 'baixa'})
        status = ContractStatus.objects.create(token='actiu', name='Actiu')
        self.contract = Contract.objects.create(token="BV-CT", status=status)

        bonification_type = BonificationType.objects.create(token="BV-BT", name="Bonificació")
        self.type_a = VariableType.objects.create(token="BV-A", name="A")
        self.type_b = VariableType.objects.create(token="BV-B", name="B")

        self.bonification = Bonification.objects.create(
            token="BV-BO", contract=self.contract, bonification_type=bonification_type,
        )
        self.variable_a = Variable.objects.create(
            token="BV-VA", contract=self.contract, bonification=self.bonification, type=self.type_a, value="1",
        )
        self.variable_b = Variable.objects.create(
            token="BV-VB", contract=self.contract, bonification=self.bonification, type=self.type_b, value="2",
        )
        self.standalone = Variable.objects.create(
            token="BV-VS", contract=self.contract, type=self.type_a, value="3",
        )

    def test_deleting_bonification_deletes_its_variables(self):
        self.bonification.delete()

        self.assertFalse(Bonification.objects.filter(pk=self.bonification.pk).exists())
        self.assertEqual(list(Variable.objects.filter(contract=self.contract)), [self.standalone])

    def test_deleting_bonification_queryset_deletes_its_variables(self):
        Bonification.objects.filter(contract=self.contract).delete()

        self.assertEqual(list(Variable.objects.filter(contract=self.contract)), [self.standalone])

    def test_deleting_bonification_variable_keeps_bonification(self):
        self.variable_a.delete()
        self.variable_b.delete()

        self.assertTrue(Bonification.objects.filter(pk=self.bonification.pk).exists())
        self.assertEqual(self.bonification.variables.count(), 0)

    def test_deleting_bonification_deletes_aca_request(self):
        ACABonificationRequest.objects.create(bonification=self.bonification)

        self.bonification.delete()

        self.assertFalse(ACABonificationRequest.objects.exists())

    def test_deleting_standalone_variable_keeps_bonification(self):
        self.standalone.delete()

        self.assertTrue(Bonification.objects.filter(pk=self.bonification.pk).exists())
        self.assertEqual(self.bonification.variables.count(), 2)

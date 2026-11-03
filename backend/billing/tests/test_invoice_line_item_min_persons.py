from django.test import TestCase

from billing.utils.invoice_line_item_service import create_from_lineitemtype
from contract.models import Contract
from coredata.models import ConfigProject
from pricing.models import BillingRange, LineItemType, VariableCalculation
from service.models import ConnectionDiameter


class TestInvoiceLineItemMinPersons(TestCase):
    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': 'terminated'},
        )
        ConfigProject.objects.update_or_create(
            token='contract_min_persons', defaults={'value': '5'},
        )
        cls.contract = Contract.objects.create(total_persons=2)
        ConnectionDiameter.objects.create(name='63', is_default=True)
        cls.line_item_type = LineItemType.objects.create(
            name='Persones', proportional_price=2,
            billing_range=BillingRange.objects.create(),
            quantity=VariableCalculation.objects.create(token='total_persons'),
        )

    def test_quantity_uses_minimum_only_for_missing_or_non_positive_persons(self):
        for total_persons, expected_units in ((None, 5), (0, 5), (-1, 5), (2, 2), (7, 7)):
            with self.subTest(total_persons=total_persons):
                self.contract.total_persons = total_persons
                contract = self.contract if total_persons is not None else None
                lines = create_from_lineitemtype(contract, self.line_item_type, None, 0, 0)
                self.assertEqual(len(lines), 1)
                self.assertEqual(lines[0]['units'], expected_units)
                self.assertEqual(lines[0]['price'], expected_units * 2)

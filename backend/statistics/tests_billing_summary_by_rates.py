from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

import openpyxl
from django.test import TestCase

from billing.models import Billing, Invoice, InvoiceLineItem, InvoiceStatus, Payment
from contract.models import Contract
from coredata.models import ConfigProject, Person
from pricing.models import LineItemType, Product
from statistics.utils import report_billing_service


class BillingSummaryByRatesTests(TestCase):
    """Resum d'abonats per tarifa: factures i titulars diferents per tipus de línia, comptats a la BD."""

    def setUp(self):
        ConfigProject.objects.create(token='invoice_status_pending_token', value='1')
        ConfigProject.objects.create(token='contract_terminated_status', value='BAIXA')
        ConfigProject.objects.create(token='invoice_status_cancelled_token', value='-6')
        ConfigProject.objects.create(token='invoice_status_paid_token', value='-1')
        self.confirmed = InvoiceStatus.objects.create(token='0', name='Confirmada')
        self.billing = Billing.objects.create(name='Facturació')
        self.product = Product.objects.create(token='AIGUA', name='Aigua')
        self.rate_a = LineItemType.objects.create(name='TARIFA A')
        self.rate_b = LineItemType.objects.create(name='TARIFA B')
        self.rate_c = LineItemType.objects.create(name='TARIFA C')

    def invoice(self, contract, line_types, billing=None):
        invoice = Invoice.objects.create(billing=billing or self.billing, contract=contract, status=self.confirmed)
        Payment.objects.create(invoice=invoice, amount=Decimal('1'))
        for line_type in line_types:
            InvoiceLineItem.objects.create(invoice=invoice, product=self.product, line_item_type=line_type, price=1)
        return invoice

    def report_rows(self):
        request = SimpleNamespace(data={'id': self.billing.id, 'billing_ids': [self.billing.id]})
        with mock.patch.object(report_billing_service, 'save_report', return_value=None):
            response, _document_id, _ = report_billing_service.generate_billing_summary_by_rates(request)
        sheet = openpyxl.load_workbook(BytesIO(response.content))['Aigua']
        return {row[0]: row[1:] for row in sheet.iter_rows(min_row=2, values_only=True)}

    def test_compta_factures_i_titulars_diferents(self):
        first_holder_contract = Contract.objects.create(holder=Person.objects.create())
        second_holder_contract = Contract.objects.create(holder=Person.objects.create())
        without_holder_contract = Contract.objects.create()
        self.invoice(first_holder_contract, [self.rate_a, self.rate_a, self.rate_b])
        self.invoice(first_holder_contract, [self.rate_a])
        self.invoice(second_holder_contract, [self.rate_b])
        self.invoice(without_holder_contract, [self.rate_a])
        # Tarifa del producte que només surt en una altra facturació
        self.invoice(second_holder_contract, [self.rate_c], billing=Billing.objects.create(name='Altra'))

        rows = self.report_rows()

        self.assertEqual(rows['TARIFA A'], (3, 1))
        self.assertEqual(rows['TARIFA B'], (2, 2))
        self.assertEqual(rows['TARIFA C'], (0, 0))

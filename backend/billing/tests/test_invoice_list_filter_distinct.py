from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import Billing, Invoice, InvoiceLineItem, InvoiceStatus, InvoiceType
from billing.utils.invoice_list_queryset import invoice_list_queryset
from coredata.models import ConfigProject


class InvoiceListFilterDistinctTests(TestCase):
    """La llista de factures no demana DISTINCT quan els filtres no ho necessiten.

    Amb DISTINCT, la base havia de comparar totes les factures (amb totes les columnes de les
    taules enllaçades) abans de tornar-ne 50: en una explotació de 34.000 factures, obrir la
    pantalla trigava 2,5 s a la consulta i sense, 0,75 s. Els filtres per camps propis o per
    claus foranes no poden repetir cap factura; només els de línies i contractes generals sí.
    """

    def setUp(self):
        ConfigProject.objects.get_or_create(token='invoice_type_invoice_token', defaults={'value': 'INVOICE'})
        ConfigProject.objects.get_or_create(token='invoice_type_budget_token', defaults={'value': 'BUDGET'})
        # Els senyals de la factura els llegeixen en desar-la amb un estat
        for token in ('invoice_status_paid_token', 'invoice_status_cancelled_token', 'invoice_status_expired_token'):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': token})
        invoice_type = InvoiceType.objects.create(token='INVOICE', name='Factura')
        budget_type = InvoiceType.objects.create(token='BUDGET', name='Pressupost')
        self.status = InvoiceStatus.objects.create(token='PENDING', name='Pendent', position=1)
        self.billing = Billing.objects.create(token='FAC-D')
        self.first = Invoice.objects.create(
            billing=self.billing, token='F1', type=invoice_type, status=self.status, customer_final='Garcia')
        Invoice.objects.create(
            billing=self.billing, token='F2', type=invoice_type, status=self.status, customer_final='Puig')
        Invoice.objects.create(billing=self.billing, token='P1', type=budget_type, status=self.status)

    def filtered(self, params):
        queryset = invoice_list_queryset().filter(billing=self.billing)
        with CaptureQueriesContext(connection) as ctx:
            tokens = list(InvoiceFilter(params, queryset=queryset).qs.values_list('token', flat=True))
        return sorted(tokens), ' '.join(q['sql'] for q in ctx.captured_queries)

    def test_opening_the_screen_does_not_use_distinct(self):
        tokens, sql = self.filtered({'is_invoice': 'true'})

        self.assertEqual(tokens, ['F1', 'F2'])
        self.assertNotIn('DISTINCT', sql)

    def test_search_and_status_do_not_use_distinct(self):
        tokens, sql = self.filtered({'is_invoice': 'true', 'search': 'garcia', 'status': str(self.status.id)})

        self.assertEqual(tokens, ['F1'])
        self.assertNotIn('DISTINCT', sql)

    def test_line_item_search_still_returns_each_invoice_once(self):
        InvoiceLineItem.objects.create(invoice=self.first, name='Quota de servei')
        InvoiceLineItem.objects.create(invoice=self.first, name='Quota de manteniment')

        tokens, _ = self.filtered({'is_invoice': 'true', 'line_item': 'quota'})

        self.assertEqual(tokens, ['F1'])

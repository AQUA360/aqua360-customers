import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from billing.models import Invoice, InvoiceStatus, InvoiceType, Reading
from billing.utils import charts_service
from contract.models import Contract
from coredata.models import ConfigProject
from service.models import SupplyPoint


class ChartHistoryTests(TestCase):
    """Barres del gràfic de consum del PDF: amb l'historial precarregat per trossos surten igual
    que consultant-lo factura a factura, i amb poques consultes."""

    def setUp(self):
        for token, value in (
            ('invoice_type_invoice_token', 'F'),
            ('invoice_status_cancelled_token', '-6'),
            ('invoice_status_payoff_token', '-2'),
            ('invoice_status_paid_token', '-1'),
            ('contract_terminated_status', 'BAIXA'),
            ('payment_status_paid_token', 'PAGAT'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        self.type = InvoiceType.objects.create(token='F', name='Factura')
        self.confirmed = InvoiceStatus.objects.create(token='0', name='Confirmada')
        self.cancelled = InvoiceStatus.objects.create(token='-6', name='Anul·lada')

    def contract(self):
        supply_point = SupplyPoint.objects.create()
        return Contract.objects.create(supply_point_default=supply_point)

    def reading(self, contract, day, consumption, **kwargs):
        return Reading.objects.create(
            contract=contract, supply_point=contract.supply_point_default, reading_date=day,
            real_consumption=consumption, **kwargs,
        )

    def invoice(self, contract, day, consumption, status=None, readings=None):
        invoice = Invoice.objects.create(
            contract=contract, type=self.type, status=status or self.confirmed, consumption=consumption,
        )
        invoice.readings.set(readings if readings is not None else [self.reading(contract, day, consumption)])
        return invoice

    def bars(self, invoices, preload):
        invoices = list(Invoice.objects.filter(id__in=[invoice.id for invoice in invoices]).select_related('contract'))
        if not preload:
            return {invoice.id: charts_service.get_chart_bars(invoice) for invoice in invoices}
        with charts_service.chart_history_scope(invoices):
            return {invoice.id: charts_service.get_chart_bars(invoice) for invoice in invoices}

    def test_mateixes_barres_amb_i_sense_precarrega(self):
        first = self.contract()
        # Lectures antigues sense factura: omplen les barres que falten
        self.reading(first, datetime.date(2025, 1, 15), 4)
        self.reading(first, datetime.date(2025, 4, 15), 6)
        self.invoice(first, datetime.date(2025, 7, 15), 10)
        self.invoice(first, datetime.date(2025, 10, 15), 99, status=self.cancelled)  # no compta
        last = self.invoice(first, datetime.date(2026, 1, 15), 12)

        second = self.contract()
        for month in (1, 3, 5, 7, 9, 11):
            self.invoice(second, datetime.date(2025, month, 1), month)
        current = self.invoice(second, datetime.date(2026, 1, 1), 20)
        # Factura sense consum desat: es calcula amb les lectures
        third = self.contract()
        without_consumption = self.invoice(third, datetime.date(2026, 2, 1), None, readings=[
            self.reading(third, datetime.date(2026, 2, 1), 3),
        ])

        invoices = [last, current, without_consumption]
        expected = self.bars(invoices, preload=False)
        self.assertEqual(self.bars(invoices, preload=True), expected)
        dates, values = expected[last.id]
        self.assertEqual(values, [12.0, 10.0, 6.0, 4.0])
        self.assertEqual(dates[0], datetime.date(2026, 1, 15))
        # Com a màxim 5 barres, de la més recent a la més antiga
        self.assertEqual(expected[current.id][1], [20.0, 11.0, 9.0, 7.0, 5.0])
        self.assertEqual(expected[without_consumption.id][1], [3.0])

    def test_poques_consultes_per_tros(self):
        invoices = []
        for _ in range(10):
            contract = self.contract()
            for month in (2, 4, 6):
                invoices.append(self.invoice(contract, datetime.date(2025, month, 1), month))
        invoices = list(Invoice.objects.filter(id__in=[invoice.id for invoice in invoices]).select_related('contract'))
        with CaptureQueriesContext(connection) as context:
            with charts_service.chart_history_scope(invoices):
                for invoice in invoices:
                    charts_service.get_chart_bars(invoice)
        self.assertLess(len(context.captured_queries), 15)

    def test_barra_d_una_factura_per_a_la_taula_de_consums(self):
        contract = self.contract()
        invoice = self.invoice(contract, datetime.date(2026, 3, 1), 7)
        without_readings = self.invoice(contract, None, 5, readings=[])
        history = charts_service.ChartHistory([invoice, without_readings], bars_only=True)
        for item in (invoice, without_readings):
            self.assertEqual(charts_service.invoice_chart_bar(item, history), charts_service.invoice_chart_bar(item))
        self.assertEqual(charts_service.invoice_chart_bar(invoice), (datetime.date(2026, 3, 1), 7.0))
        self.assertEqual(charts_service.invoice_chart_bar(without_readings), (None, None))

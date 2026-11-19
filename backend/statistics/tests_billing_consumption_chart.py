import datetime

from django.test import TestCase

from billing.models import Invoice, InvoiceStatus, Reading
from contract.models import Contract
from coredata.models import ConfigProject
from service.models import SupplyPoint
from statistics.models import BillingConsumption
from statistics.tasks import fill_billing_consumption_chart, update_billing_consumption


class BillingConsumptionChartTests(TestCase):
    """La taula de consums guarda la barra del gràfic de cada factura (data i consum facturat)."""

    def setUp(self):
        for token, value in (
            ('invoice_status_cancelled_token', '-6'),
            ('invoice_status_paid_token', '-1'),
            ('payment_status_paid_token', 'PAGAT'),
            ('contract_terminated_status', 'BAIXA'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        self.status = InvoiceStatus.objects.create(token='0', name='Confirmada')
        self.contract = Contract.objects.create(supply_point_default=SupplyPoint.objects.create())

    def invoice(self, consumption, reading_dates):
        invoice = Invoice.objects.create(
            contract=self.contract, status=self.status, consumption=consumption,
            billing_period_year=2026, billing_period_month=3,
        )
        invoice.readings.set([
            Reading.objects.create(contract=self.contract, reading_date=day, real_consumption=consumption)
            for day in reading_dates
        ])
        return invoice

    def test_es_desa_en_calcular_el_consum(self):
        invoice = self.invoice(7, [datetime.date(2026, 2, 20), datetime.date(2026, 3, 1)])
        update_billing_consumption(invoice.id)
        row = BillingConsumption.objects.get(invoice=invoice)
        self.assertEqual((row.chart_date, row.chart_consumption), (datetime.date(2026, 3, 1), 7.0))

    def test_el_backfill_omple_les_que_falten(self):
        with_readings = self.invoice(4, [datetime.date(2026, 1, 10)])
        without_readings = self.invoice(5, [])
        for invoice in (with_readings, without_readings):
            BillingConsumption.objects.create(invoice=invoice, contract=self.contract)

        self.assertEqual(fill_billing_consumption_chart(batch_size=1), 1)

        rows = {row.invoice_id: row for row in BillingConsumption.objects.all()}
        self.assertEqual(
            (rows[with_readings.id].chart_date, rows[with_readings.id].chart_consumption),
            (datetime.date(2026, 1, 10), 4.0),
        )
        self.assertIsNone(rows[without_readings.id].chart_date)

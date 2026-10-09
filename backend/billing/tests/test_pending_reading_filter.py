from datetime import date

from django.test import TestCase

from billing.models import Invoice, InvoiceStatus, InvoiceType, Reading
from billing.utils.reading_filters import PENDING_READING_FILTER
from contract.models import Contract
from coredata.models import ConfigProject


class TestPendingReadingFilter(TestCase):
    """Una lectura amb prefactura I factura definitiva no és pendent de facturar.

    El filtre antic era `Q(invoices__isnull=True) | Q(invoices__type_final='P')`.
    Com que `invoices` és multivaluat, l'OR s'avaluava sobre el JOIN i la lectura
    passava el filtre per la branca de la prefactura tot i tenir la factura
    definitiva. Això va fer que un lot de telelectura recollís lectures ja
    facturades — sobretot
    liquidacions de baixa, que és el flux que deixa la PF/... vinculada.
    """

    def setUp(self):
        # Configs que consulten els post_save de Contract i d'Invoice
        for token, value in (
            ('contract_terminated_status', 'TERMINATED'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_pending_token', 'PENDING'),
            ('payment_status_paid_token', 'PAID'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        InvoiceStatus.objects.get_or_create(token='PENDING', defaults={'name': 'Pendent'})

        self.contract = Contract.objects.create(token='C-PENDING')
        self.type_budget = InvoiceType.objects.create(token='BUDGET', name='Prefactura')
        self.type_invoice = InvoiceType.objects.create(token='INVOICE', name='Factura')

    def make_reading(self, day):
        return Reading.objects.create(
            contract=self.contract, reading_date=date(2026, 5, day), reading_value=100)

    def make_invoice(self, reading, type_final, serie_final):
        invoice = Invoice.objects.create(
            contract=self.contract,
            type=self.type_budget if type_final == 'P' else self.type_invoice,
            type_final=type_final,
            serie_final=serie_final,
        )
        invoice.readings.set([reading])
        return invoice

    def pending_ids(self):
        return set(
            Reading.objects.filter(PENDING_READING_FILTER)
            .distinct()
            .values_list('id', flat=True)
        )

    def test_lectura_sense_factures_es_pendent(self):
        reading = self.make_reading(1)
        self.assertIn(reading.id, self.pending_ids())

    def test_lectura_nomes_amb_prefactura_es_pendent(self):
        reading = self.make_reading(2)
        self.make_invoice(reading, 'P', 'PF/1')
        self.assertIn(reading.id, self.pending_ids())

    def test_lectura_amb_prefactura_i_factura_no_es_pendent(self):
        reading = self.make_reading(3)
        self.make_invoice(reading, 'P', 'PF/2')
        self.make_invoice(reading, 'F', 'FC/202605/000001')
        self.assertNotIn(reading.id, self.pending_ids())

    def test_lectura_amb_factura_i_rectificativa_no_es_pendent(self):
        """FC + FF + FR sobre la mateixa lectura."""
        reading = self.make_reading(4)
        self.make_invoice(reading, 'P', 'PF/3')
        self.make_invoice(reading, 'F', 'FC/202607/000002')
        self.make_invoice(reading, 'F', 'FF/202607/000002')
        self.make_invoice(reading, 'F', 'FR/202607/000003')
        self.assertNotIn(reading.id, self.pending_ids())

    def test_el_filtre_no_duplica_files(self):
        reading = self.make_reading(5)
        self.make_invoice(reading, 'P', 'PF/4')
        self.make_invoice(reading, 'P', 'PF/5')
        self.assertEqual(
            Reading.objects.filter(id=reading.id).filter(PENDING_READING_FILTER).count(), 1)

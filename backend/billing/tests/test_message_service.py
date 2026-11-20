from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from billing.models import Invoice, InvoiceTemplate, Message
from billing.utils.message_service import invoice_add_messages
from contract.models import Contract
from coredata.models import ConfigProject


class InvoiceMessagesTests(TestCase):
    """Missatges del PDF de la factura: es consulta només el lligam de la factura, no totes
    les factures del missatge (en una explotació gran en són desenes de milers)."""

    def setUp(self):
        self.template = InvoiceTemplate.objects.create()
        self.message = Message.objects.create(template=self.template, title='Avís', content='Text')
        self.other_template_message = Message.objects.create(template=InvoiceTemplate.objects.create(), title='Altre')
        for token, value in (('contract_terminated_status', 'BAIXA'), ('invoice_status_cancelled_token', '-6')):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        self.contract = Contract.objects.create()

    def new_invoice(self):
        return Invoice.objects.create(contract=self.contract)

    def test_el_missatge_sense_condicions_surt_a_la_factura(self):
        invoice = self.new_invoice()
        updated_at = self.message.updated_at

        data = invoice_add_messages(invoice)

        self.assertEqual(list(data), [self.message.id])
        self.assertEqual(data[self.message.id]['title'], 'Avís')
        self.assertTrue(self.message.invoices.filter(id=invoice.id).exists())
        # Lligar la factura no desa el missatge
        self.message.refresh_from_db()
        self.assertEqual(self.message.updated_at, updated_at)

    def test_no_surt_un_missatge_d_un_altre_lligam(self):
        invoice = self.new_invoice()
        Message.objects.filter(id=self.message.id).update(start_at='2000-01-01', end_at='2000-01-02')
        self.message.invoices.add(self.new_invoice())

        self.assertEqual(invoice_add_messages(invoice), {})

    def test_no_es_carreguen_les_factures_del_missatge(self):
        self.message.invoices.add(*[self.new_invoice() for _ in range(5)])
        through_table = Message.invoices.through._meta.db_table
        with CaptureQueriesContext(connection) as context:
            invoice_add_messages(self.new_invoice())
        # Totes les lectures del lligam van filtrades per la factura
        through_selects = [
            query['sql'] for query in context.captured_queries
            if query['sql'].startswith('SELECT') and through_table in query['sql']
        ]
        self.assertTrue(through_selects)
        for sql in through_selects:
            self.assertRegex(sql, rf'"{through_table}"\."invoice_id" (=|IN)')

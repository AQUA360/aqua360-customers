from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import (
    Billing, Invoice, InvoiceStatus, InvoiceType, Payment, PaymentMovement, PaymentStatus,
)
from coredata.models import ConfigProject
from service.models import Exploitation


INVOICE_STATUSES = {
    'invoice_status_paid_token': 'Pagada',
    'invoice_status_pending_token': 'Pre-factura',
    'invoice_status_expired_token': 'Vençuda',
    'invoice_status_dropped_token': 'Anul·lada',
    'invoice_status_cancelled_token': 'Abonada',
    'invoice_status_commitment_token': 'En compromís',
    'invoice_status_payoff_token': 'Abonament',
}
PAYMENT_STATUSES = {
    'payment_status_paid_token': 'Pagat',
    'payment_status_pending_token': 'Pendent',
    'payment_status_returned_token': 'Retornat',
    'payment_status_cancelled_token': 'Abonat',
    'payment_status_payoff_token': 'Abonament',
    'payment_status_dropped_token': 'Anul·lat',
    'payment_status_piggy_token': 'En saldo',
}


class InvoiceManageMassivelyPaidTests(TestCase):
    """Pagar en massa: el servidor paga només les factures confirmades que compleixen els
    filtres de la llista i les seves condicions, i diu per què queden fora les altres."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(token='invoice_type_invoice_token', defaults={'value': 'F'})
        # El senyal de factura pagada el llegeix en crear-ne una de pagada
        ConfigProject.objects.get_or_create(token='bail_status_returned_token', defaults={'value': 'RETURNED'})
        cls.invoice_type = InvoiceType.objects.create(token='F', name='Factura')
        cls.invoice_status = {}
        for token, name in INVOICE_STATUSES.items():
            ConfigProject.objects.get_or_create(token=token, defaults={'value': token})
            cls.invoice_status[token] = InvoiceStatus.objects.create(token=token, name=name)
        cls.payment_status = {}
        for token, name in PAYMENT_STATUSES.items():
            ConfigProject.objects.get_or_create(token=token, defaults={'value': token})
            cls.payment_status[token] = PaymentStatus.objects.create(token=token, name=name)
        cls.exploitation = Exploitation.objects.create(name='Explotació A')
        cls.other_exploitation = Exploitation.objects.create(name='Explotació B')
        cls.billing = Billing.objects.create(token='FAC-MASS')
        cls.user = get_user_model().objects.create_user(username='bulk-pay', password='x')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('invoice-manage-massively-paid')

    def invoice(self, token, status='invoice_status_expired_token', payment_type='BANK_TRANSFER',
                exploitation=None, **kwargs):
        return Invoice.objects.create(
            billing=self.billing, token=token, serie_final=token, type=self.invoice_type,
            status=self.invoice_status[status], payment_type_token_final=payment_type,
            exploitation=exploitation or self.exploitation,
            total_final=Decimal('100.00'), left_to_pay=kwargs.pop('left_to_pay', Decimal('100.00')),
            **kwargs,
        )

    def payment(self, invoice, status):
        return Payment.objects.create(
            invoice=invoice, status=self.payment_status[status], payment_type_token='BANK_TRANSFER',
        )

    def summary(self, **data):
        response = self.client.post(self.url, {'exploitation': self.exploitation.id, 'saving': False, **data}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def save(self, invoice_ids, **data):
        return self.client.post(
            self.url,
            {'exploitation': self.exploitation.id, 'saving': True, 'invoice_ids': invoice_ids, **data},
            format='json',
        )

    def test_summary_lists_payable_invoices_and_why_others_are_left_out(self):
        payable = self.invoice('T1', left_to_pay=Decimal('40.00'))
        self.invoice('T2', status='invoice_status_paid_token')
        self.invoice('T3', status='invoice_status_pending_token')
        self.invoice('T4', payment_type='DIRECT_DEBIT')
        self.invoice('T5', is_excluded=True)
        self.invoice('T6', exploitation=self.other_exploitation)

        data = self.summary()

        self.assertEqual(data['count'], 1)
        self.assertEqual(data['invoice_ids'], [payable.id])
        self.assertEqual([row['id'] for row in data['results']], [payable.id])
        self.assertEqual(Decimal(str(data['total_amount'])), Decimal('40.00'))
        self.assertEqual(
            {item['reason']: item['count'] for item in data['skipped']},
            {'already_paid': 1, 'status': 1, 'payment_type': 1},
        )

    def test_total_filter_uses_the_invoice_total_like_the_list(self):
        invoice = self.invoice('T1', left_to_pay=Decimal('30.00'))

        self.assertEqual(self.summary(total_final='100.00')['invoice_ids'], [invoice.id])
        self.assertEqual(self.summary(total_final='30.00')['invoice_ids'], [])

    def test_save_requires_the_confirmed_invoices(self):
        self.invoice('T1')

        response = self.save([])

        self.assertEqual(response.status_code, 400)

    def test_save_pays_only_confirmed_invoices_that_still_match(self):
        confirmed = self.invoice('T1')
        not_confirmed = self.invoice('T2')
        other_exploitation = self.invoice('T3', exploitation=self.other_exploitation)
        sepa = self.invoice('T4', payment_type='DIRECT_DEBIT')

        response = self.save([confirmed.id, other_exploitation.id, sepa.id])

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'updated_count': 1, 'skipped_count': 2, 'error_count': 0})
        paid = self.invoice_status['invoice_status_paid_token']
        confirmed.refresh_from_db()
        self.assertEqual(confirmed.status, paid)
        self.assertEqual(confirmed.left_to_pay, 0)
        for invoice in (not_confirmed, other_exploitation, sepa):
            invoice.refresh_from_db()
            self.assertNotEqual(invoice.status, paid)

    def test_save_skips_invoices_that_changed_after_the_preview(self):
        invoice = self.invoice('T1')
        invoice_ids = self.summary()['invoice_ids']
        Invoice.objects.filter(id=invoice.id).update(status=self.invoice_status['invoice_status_paid_token'])

        response = self.save(invoice_ids)

        self.assertEqual(response.json(), {'updated_count': 0, 'skipped_count': 1, 'error_count': 0})

    def test_save_leaves_cancelled_payments_untouched(self):
        invoice = self.invoice('T1')
        pending = self.payment(invoice, 'payment_status_pending_token')
        returned = self.payment(invoice, 'payment_status_returned_token')
        cancelled = self.payment(invoice, 'payment_status_cancelled_token')
        dropped = self.payment(invoice, 'payment_status_dropped_token')

        self.save([invoice.id])

        paid = self.payment_status['payment_status_paid_token']
        for payment in (pending, returned):
            payment.refresh_from_db()
            self.assertEqual(payment.status, paid)
        cancelled.refresh_from_db()
        dropped.refresh_from_db()
        self.assertEqual(cancelled.status, self.payment_status['payment_status_cancelled_token'])
        self.assertEqual(dropped.status, self.payment_status['payment_status_dropped_token'])
        self.assertEqual(
            set(PaymentMovement.objects.filter(payment__invoice=invoice).values_list('payment_id', flat=True)),
            {pending.id, returned.id},
        )

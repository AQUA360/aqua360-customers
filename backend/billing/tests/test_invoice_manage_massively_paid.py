from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import (
    Billing, Invoice, InvoiceStatus, InvoiceType, Payment, PaymentMovement, PaymentStatus,
)
from billing.views.invoice_manage_massively_view import SKIPPED_PAYMENT_STATUS_TOKENS
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
        # La base de proves pot portar ja la configuració de les migracions de dades
        # (p. ex. payment_status_dropped_token = -7): cada estat es resol pel valor configurat,
        # com fa el codi, i no es dona per fet que el token de l'estat és el nom de la config.
        def configured(token, default):
            return ConfigProject.objects.get_or_create(token=token, defaults={'value': default})[0].value

        # El senyal de factura pagada el llegeix en crear-ne una de pagada
        configured('bail_status_returned_token', 'RETURNED')
        cls.invoice_type, _ = InvoiceType.objects.get_or_create(
            token=configured('invoice_type_invoice_token', 'F'), defaults={'name': 'Factura'})
        cls.invoice_status = {
            token: InvoiceStatus.objects.get_or_create(token=configured(token, token), defaults={'name': name})[0]
            for token, name in INVOICE_STATUSES.items()
        }
        cls.payment_status = {
            token: PaymentStatus.objects.get_or_create(token=configured(token, token), defaults={'name': name})[0]
            for token, name in PAYMENT_STATUSES.items()
        }
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

    def test_save_pays_open_payments_and_leaves_closed_ones_untouched(self):
        """Cada estat de cobrament: els ja pagats, abonats o anul·lats no es toquen ni generen
        moviment; la resta (pendent, retornat...) queda pagada amb el seu moviment."""
        invoice = self.invoice('T1')
        payments = {token: self.payment(invoice, token) for token in PAYMENT_STATUSES}

        response = self.save([invoice.id])

        self.assertEqual(response.json()['updated_count'], 1)
        paid = self.payment_status['payment_status_paid_token']
        moved_ids = set(PaymentMovement.objects.filter(payment__invoice=invoice).values_list('payment_id', flat=True))
        for token, payment in payments.items():
            with self.subTest(status=token):
                payment.refresh_from_db()
                if token in SKIPPED_PAYMENT_STATUS_TOKENS:
                    self.assertEqual(payment.status, self.payment_status[token])
                    self.assertNotIn(payment.id, moved_ids)
                else:
                    self.assertEqual(payment.status, paid)
                    self.assertIn(payment.id, moved_ids)

    def test_preview_pages_follow_the_initial_selection(self):
        invoices = [self.invoice(f'T{n}', issue_date=f'2026-01-0{n}') for n in (1, 2, 3)]
        with patch('billing.views.invoice_manage_massively_view.PREVIEW_PAGE_SIZE', 1):
            data = self.summary()
            self.assertEqual(data['invoice_ids'], [invoice.id for invoice in invoices])
            self.assertEqual([row['id'] for row in data['results']], [invoices[0].id])

            # La primera es paga entremig: la pàgina següent continua sent la segona factura
            Invoice.objects.filter(id=invoices[0].id).update(status=self.invoice_status['invoice_status_paid_token'])
            page = self.summary(preview_ids=data['invoice_ids'][1:2])

        self.assertEqual([row['id'] for row in page['results']], [invoices[1].id])

    def test_preview_page_rejects_more_ids_than_a_page(self):
        with patch('billing.views.invoice_manage_massively_view.PREVIEW_PAGE_SIZE', 1):
            response = self.client.post(
                self.url, {'saving': False, 'preview_ids': [1, 2]}, format='json')

        self.assertEqual(response.status_code, 400)

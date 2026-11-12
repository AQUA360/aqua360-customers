import json
from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import GeneralPayment, Invoice, Payment
from billing.tests.test_return_warnings import ReturnWarningsBase
from billing.utils.payment_return_warnings import annotate_rejection_warnings
from billing.utils.payment_service import generate_payment_movement
from claimrequest.models import ClaimRequestStatus, ClaimRequestStepTemplate, ClaimRequestTemplate
from contract.models import PaymentType, PiggyBank, PiggyBankMovement
from coredata.models import PersonBank


class RectifiedInvoiceReturnBase(ReturnWarningsBase):
    """Factura cobrada per domiciliació (25 €) anul·lada amb el cobrat al saldo i refeta per 20 €."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.balance = PaymentType.objects.create(token='BALANCE', name='Saldo')

    def setUp(self):
        super().setUp()
        bank = PersonBank.objects.create(iban='ES1111111111111111111111', swift='BANKESXX')
        self.contract.payment = GeneralPayment.objects.create(type=self.direct_debit, IBAN=bank)
        self.contract.piggy_bank = PiggyBank.objects.create(token='PB-RET', amount=Decimal('0.00'))
        self.contract.save()

    def piggy_amount(self):
        return PiggyBank.objects.get(id=self.contract.piggy_bank_id).amount

    def credit_piggy(self, amount, payment=None, is_positive=True):
        PiggyBank.objects.filter(id=self.contract.piggy_bank_id).update(
            amount=self.piggy_amount() + (amount if is_positive else -amount))
        PiggyBankMovement.objects.create(
            piggy_bank_id=self.contract.piggy_bank_id, amount=amount, is_positive=is_positive,
            movement_date=date(2026, 9, 20), payment=payment)

    def rectify_with_balance(self, new_total=Decimal('20.00'), extra_balance=Decimal('0.00')):
        """Anul·lació amb el cobrat al saldo i factura refeta pagada amb saldo."""
        if extra_balance:
            self.credit_piggy(extra_balance)
        rectifying = Invoice.objects.create(token='F-RET-R', contract=self.contract, serie_final='FR/RET')
        Invoice.objects.filter(id=self.invoice.id).update(
            status=self.invoice_status['CANCELLED'], return_token=rectifying.token)
        self.payment.status = self.payment_status['-6']
        self.payment.save()
        self.invoice.refresh_from_db()
        self.credit_piggy(Decimal('25.00'), self.payment)

        self.new_invoice = Invoice.objects.create(
            token='F-RET-2', contract=self.contract, serie_final='FC/RET2', refactored_token=self.invoice.token,
            status=self.invoice_status['PAID'], due_date=date(2026, 10, 1), total_final=new_total, left_to_pay=0,
            payment_type=self.balance, payment_type_final='Saldo', payment_type_token_final='BALANCE')
        paid_with_balance = min(new_total, self.piggy_amount())
        self.balance_payment = Payment.objects.create(
            token='PRET0002', amount=paid_with_balance, invoice=self.new_invoice, contract=self.contract,
            status=self.payment_status['1'], payment_type='Saldo', payment_type_token='BALANCE',
            due_date=date(2026, 10, 1))
        generate_payment_movement(self.balance_payment, self.payment_status['0'], date(2026, 9, 20), 'BALANCE', None, self.user)
        self.balance_payment.status = self.payment_status['0']
        self.balance_payment.save()
        self.credit_piggy(paid_with_balance, self.balance_payment, is_positive=False)

    def post_return(self, claim=False):
        client = APIClient()
        client.force_authenticate(self.user)
        rejection = {'id': self.payment.id, 'skip_return': False, 'rjt_dt': '2026-10-09',
                     'motive_id': self.motive.id, 'motive': self.motive.name}
        data = {
            'payments_to_return': json.dumps([rejection]),
            'return_payments': json.dumps([]),
            'claim_payments': json.dumps([self.payment.id] if claim else []),
            'return_date': '2026-10-09',
        }
        return client.post(reverse('payment-manage-rejection-payments'), data, format='multipart')

    def pending_payments(self):
        return self.new_invoice.payments.exclude(payment_type_token='BALANCE')


class TestRectifiedInvoiceReturn(RectifiedInvoiceReturnBase):

    def test_difference_is_removed_and_refactored_invoice_is_debt(self):
        self.rectify_with_balance()
        self.assertEqual(self.piggy_amount(), Decimal('5.00'))

        response = self.post_return()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.piggy_amount(), Decimal('0.00'))
        self.new_invoice.refresh_from_db()
        self.assertEqual(self.new_invoice.status.token, 'EXPIRED')
        self.assertEqual(self.new_invoice.left_to_pay, Decimal('20.00'))
        self.assertEqual(self.new_invoice.payment_type_token_final, 'DIRECT_DEBIT')
        self.balance_payment.refresh_from_db()
        self.assertEqual(self.balance_payment.status.token, '-6')
        pending = self.pending_payments().get()
        self.assertEqual(pending.amount, Decimal('20.00'))
        self.assertEqual(pending.payment_type_token, 'DIRECT_DEBIT')
        self.assertEqual(pending.payment_bank, 'ES1111111111111111111111')
        self.assertNotEqual(pending.status.token, '0')
        # La factura antiga continua anul·lada i el cobrament, abonat però amb el retorn registrat
        self.invoice.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.invoice.status.token, 'CANCELLED')
        self.assertEqual(self.payment.status.token, '-6')
        self.assertTrue(self.payment.movements.filter(current_status__token='-2', reject_motive=self.motive).exists())
        rectified = response.data['rejections'][0]['rectified_return']
        self.assertEqual(rectified['status'], 'applied')
        self.assertEqual(rectified['balance_removed'], Decimal('5.00'))
        self.assertEqual(rectified['refactored_debt'], Decimal('20.00'))

    def test_enough_balance_keeps_refactored_invoice_paid(self):
        self.rectify_with_balance(extra_balance=Decimal('30.00'))
        self.assertEqual(self.piggy_amount(), Decimal('35.00'))

        self.post_return()

        self.assertEqual(self.piggy_amount(), Decimal('10.00'))
        self.new_invoice.refresh_from_db()
        self.assertEqual(self.new_invoice.status.token, 'PAID')
        self.assertFalse(self.pending_payments().exists())

    def test_balance_partly_covers_and_rest_is_debt(self):
        self.rectify_with_balance(extra_balance=Decimal('10.00'))
        self.assertEqual(self.piggy_amount(), Decimal('15.00'))

        self.post_return()

        self.assertEqual(self.piggy_amount(), Decimal('0.00'))
        self.new_invoice.refresh_from_db()
        self.assertEqual(self.new_invoice.left_to_pay, Decimal('10.00'))
        self.assertEqual(self.pending_payments().get().amount, Decimal('10.00'))
        balance_paid = self.new_invoice.payments.filter(payment_type_token='BALANCE', status__token='0')
        self.assertEqual(sum(p.amount for p in balance_paid), Decimal('10.00'))

    def test_balance_never_goes_negative(self):
        self.rectify_with_balance()
        # La diferència ja s'ha gastat en una altra factura
        self.credit_piggy(Decimal('5.00'), is_positive=False)

        result = self.post_return().data['rejections'][0]['rectified_return']

        self.assertEqual(self.piggy_amount(), Decimal('0.00'))
        self.assertEqual(self.pending_payments().get().amount, Decimal('20.00'))
        self.assertEqual(result['uncovered'], Decimal('5.00'))

    def test_processing_the_same_return_twice_does_nothing_more(self):
        self.rectify_with_balance()

        self.post_return()
        self.post_return()

        self.assertEqual(self.piggy_amount(), Decimal('0.00'))
        self.assertEqual(self.pending_payments().count(), 1)

    def test_claim_includes_the_refactored_invoice_debt(self):
        template = ClaimRequestTemplate.objects.create(name='Per defecte', is_default=True)
        ClaimRequestStepTemplate.objects.create(template=template, name='Avís', position=1, duration=10)
        ClaimRequestStatus.objects.create(token='PENDING', name='Pendent', is_default=True)
        self.rectify_with_balance()

        self.post_return(claim=True)

        pending = self.pending_payments().get()
        self.assertTrue(pending.claim_requests.exists())
        self.assertFalse(self.payment.claim_requests.exists())

    def test_preview_shows_balance_and_debt(self):
        self.rectify_with_balance()

        warnings = annotate_rejection_warnings([{'payment_id': self.payment.id}])[0]

        self.assertEqual(warnings['rectified_balance'], {
            'balance_to_remove': 5.0, 'refactored_debt': 20.0, 'uncovered': 0.0})

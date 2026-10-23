import json
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import (
    CommitmentDepositStatus, Invoice, InvoiceStatus, Payment, PaymentCommitmentStatus, PaymentStatus, RejectMotive,
)
from billing.utils import payment_service
from billing.utils.payment_service import (
    disconnect_payment_signals, generate_method_change_rejection_movements, generate_payment_movement, get_unreturned_direct_debit_movement,
    is_paid_by_direct_debit_with_other_method, reconnect_payment_signals,
)
from billing.utils.sepa_service import handle_not_found_payment
from contract.models import Contract, PaymentType
from coredata.models import ConfigProject


class ReturnAfterPaymentMethodChangeBase(TestCase):
    """Factura cobrada per domiciliació a la qual després s'ha canviat el mètode a efectiu."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': '0'})
        payment_status_tokens = {
            'payment_status_paid_token': ('0', 'Pagat'),
            'payment_status_pending_token': ('1', 'Pendent'),
            'payment_status_expired_token': ('-1', 'Vençut'),
            'payment_status_returned_token': ('-2', 'Retornat'),
            'payment_status_sent_token': ('2', 'Processat'),
            'payment_status_endowment_token': ('-3', 'Morositat'),
            'payment_status_irrecoverable_token': ('-5', 'Irrecuperable'),
            'payment_status_commitment_token': ('4', 'En compromís'),
            'payment_status_cancelled_token': ('-6', 'Abonat'),
            'payment_status_piggy_token': ('5', 'Saldo'),
            'payment_status_payoff_token': ('6', 'Liquidat'),
        }
        cls.payment_status = {}
        for config_token, (token, name) in payment_status_tokens.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': token})
            cls.payment_status[token] = PaymentStatus.objects.create(token=token, name=name)

        invoice_status_tokens = {
            'invoice_status_paid_token': ('PAID', 'Pagada'),
            'invoice_status_confirmed_token': ('CONFIRMED', 'Confirmada'),
            'invoice_status_expired_token': ('EXPIRED', 'Vençuda'),
        }
        cls.invoice_status = {}
        for config_token, (token, name) in invoice_status_tokens.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': token})
            cls.invoice_status[token] = InvoiceStatus.objects.create(token=token, name=name)

        # Estats de dipòsits i compromisos: la vista els carrega sempre, encara que no s'usin
        for config_token, value in {
            'commitment_deposit_status_paid_token': 'CD_PAID',
            'commitment_deposit_status_partially_paid_token': 'CD_PARTIAL',
            'payment_commitment_status_paid_token': 'PC_PAID',
            'payment_commitment_status_pending_token': 'PC_PENDING',
            'direct_debit_token': 'DIRECT_DEBIT',
        }.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': value})
        CommitmentDepositStatus.objects.create(token='CD_PARTIAL', name='Parcial')
        PaymentCommitmentStatus.objects.create(token='PC_PAID', name='Pagat')
        PaymentCommitmentStatus.objects.create(token='PC_PENDING', name='Pendent')

        cls.direct_debit = PaymentType.objects.create(token='DIRECT_DEBIT', name='Domiciliació')
        cls.cash = PaymentType.objects.create(token='CASH', name='Efectiu')
        cls.motive = RejectMotive.objects.create(token='AM04', name='Fons insuficients')
        cls.other_motive = RejectMotive.objects.create(token='MD06', name='Retorn a petició del deutor')
        cls.user = get_user_model().objects.create_superuser(username='admin-retorn', password='x')

    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)
        self.contract = Contract.objects.create(token='C-RET')
        self.invoice = Invoice.objects.create(
            token='F-RET', contract=self.contract, serie_final='FC/RET',
            status=self.invoice_status['PAID'], due_date=date(2026, 9, 30),
            payment_type_final='Domiciliació', payment_type_token_final='DIRECT_DEBIT')
        self.payment = Payment.objects.create(
            token='PRET0001', amount=Decimal('25.00'), invoice=self.invoice,
            status=self.payment_status['1'], payment_type='Domiciliació', payment_type_token='DIRECT_DEBIT',
            payment_bank='ES0000000000000000000000', due_date=date(2026, 9, 3))
        # Cobrament per domiciliació del 03/09
        generate_payment_movement(
            self.payment, self.payment_status['0'], date(2026, 9, 3), 'DIRECT_DEBIT',
            self.payment.payment_bank, self.user)
        self.payment.status = self.payment_status['0']
        self.payment.payment_date = date(2026, 9, 3)
        self.payment.save()

    def change_method_to_cash(self):
        """Canvi de mètode com el feia abans el canvi de mètode de pagament: sense cap moviment."""
        Payment.objects.filter(id=self.payment.id).update(payment_type='Efectiu', payment_type_token='CASH')
        self.payment.refresh_from_db()


class TestDetectDirectDebitWithOtherMethod(ReturnAfterPaymentMethodChangeBase):

    def test_direct_debit_payment_is_not_method_changed(self):
        self.assertIsNotNone(get_unreturned_direct_debit_movement(self.payment, '2026-09-09'))
        self.assertFalse(is_paid_by_direct_debit_with_other_method(self.payment, '2026-09-09'))

    def test_changed_method_without_return_is_detected(self):
        self.change_method_to_cash()
        self.assertTrue(is_paid_by_direct_debit_with_other_method(self.payment, '2026-09-09'))

    def test_collection_after_rejection_date_is_ignored(self):
        # Només compten els cobraments fins a la data del retorn
        self.change_method_to_cash()
        self.assertFalse(is_paid_by_direct_debit_with_other_method(self.payment, '2026-09-01'))

    def test_already_returned_direct_debit_is_not_detected(self):
        self.change_method_to_cash()
        generate_payment_movement(
            self.payment, self.payment_status['-2'], date(2026, 9, 9), 'DIRECT_DEBIT',
            self.payment.payment_bank, self.user)
        self.assertFalse(is_paid_by_direct_debit_with_other_method(self.payment, '2026-09-10'))


class TestSepaReturnFileAfterMethodChange(ReturnAfterPaymentMethodChangeBase):

    def parse(self):
        client_data = {'end_to_end_id': self.payment.token, 'RJT': 'AM04', 'IBAN': self.payment.payment_bank}
        return handle_not_found_payment(client_data, {'name': 'EMPRESA'}, '2026-09-09')

    def test_changed_method_is_returned_and_flagged(self):
        self.change_method_to_cash()

        rejection = self.parse()

        self.assertFalse(rejection['skip_return'])
        self.assertTrue(rejection['method_changed'])
        self.assertEqual(rejection['motive_id'], self.motive.id)

    def test_paid_by_other_method_without_direct_debit_is_skipped(self):
        self.payment.movements.all().delete()
        self.change_method_to_cash()
        generate_payment_movement(
            self.payment, self.payment_status['0'], date(2026, 9, 3), 'CASH', None, self.user)

        rejection = self.parse()

        self.assertTrue(rejection['skip_return'])
        self.assertFalse(rejection['method_changed'])


class TestManageRejectionAfterMethodChange(ReturnAfterPaymentMethodChangeBase):

    def post_return(self, motive=None, main_motive=None):
        client = APIClient()
        client.force_authenticate(self.user)
        rejection = {'id': self.payment.id, 'skip_return': False, 'rjt_dt': '2026-09-09'}
        if not main_motive:
            motive = motive or self.motive
            rejection.update({'motive_id': motive.id, 'motive': motive.name})
        data = {
            'payments_to_return': json.dumps([rejection]),
            'return_payments': json.dumps([self.payment.id]),
            'claim_payments': json.dumps([self.payment.id]),
            'return_date': '2026-09-09',
        }
        if main_motive:
            data['main_return_reason'] = main_motive.id
        return client.post(reverse('payment-manage-rejection-payments'), data, format='multipart')

    def test_return_creates_direct_debit_return_and_new_method_payment(self):
        self.change_method_to_cash()

        response = self.post_return()

        self.assertEqual(response.status_code, 200)
        movements = list(self.payment.movements.order_by('timestamp', 'id'))
        self.assertEqual(len(movements), 3)
        _, returned, repaid = movements
        self.assertEqual(returned.payment_type.token, 'DIRECT_DEBIT')
        self.assertFalse(returned.is_positive)
        self.assertEqual(returned.current_status.token, '-2')
        self.assertEqual(returned.reject_motive, self.motive)
        self.assertEqual(returned.movement_date, date(2026, 9, 9))
        self.assertEqual(repaid.payment_type.token, 'CASH')
        self.assertTrue(repaid.is_positive)
        self.assertEqual(repaid.previous_status.token, '-2')
        self.assertEqual(repaid.current_status.token, '0')
        self.assertEqual(repaid.movement_date, date(2026, 9, 9))

        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.payment.status.token, '0')
        self.assertEqual(self.invoice.status.token, 'PAID')
        # Continua pagada: ni factura de reclamació ni gestió d'impagats
        self.assertFalse(Invoice.objects.filter(parent_invoice=self.invoice).exists())
        self.assertFalse(self.payment.claim_requests.exists())

    def test_reloading_the_return_does_not_duplicate_movements(self):
        self.change_method_to_cash()
        self.post_return()

        response = self.post_return()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.payment.movements.count(), 3)

    def test_reloading_the_return_with_other_motive_does_not_return_it_again(self):
        self.change_method_to_cash()
        self.post_return()

        response = self.post_return(motive=self.other_motive)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.payment.movements.count(), 3)
        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.payment.status.token, '0')
        self.assertEqual(self.invoice.status.token, 'PAID')

    def test_inactive_return_does_not_block_the_return(self):
        self.change_method_to_cash()
        self.post_return()
        # S'anul·la el retorn: només queda actiu el cobrament per domiciliació
        self.payment.movements.exclude(payment_type__token='DIRECT_DEBIT', current_status__token='0').update(is_active=False)

        self.post_return()

        self.assertEqual(self.payment.movements.filter(is_active=True).count(), 3)

    def test_failed_new_collection_rolls_back_the_return(self):
        self.change_method_to_cash()
        real_generate = payment_service.generate_payment_movement

        def fail_on_new_collection(payment, payment_status, *args, **kwargs):
            if payment_status == self.payment_status['0']:
                raise Exception('error')
            return real_generate(payment, payment_status, *args, **kwargs)

        with mock.patch.object(payment_service, 'generate_payment_movement', side_effect=fail_on_new_collection):
            with self.assertRaises(Exception):
                generate_method_change_rejection_movements(
                    self.payment, self.payment_status['-2'], date(2026, 9, 9),
                    self.payment.payment_bank, self.user, self.motive)

        self.assertEqual(self.payment.movements.count(), 1)
        self.assertEqual(self.payment.status.token, '0')

    def test_return_with_main_motive_saves_reject_date(self):
        self.change_method_to_cash()

        response = self.post_return(main_motive=self.motive)

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.reject_date, date(2026, 9, 9))
        self.assertEqual(self.payment.movements.get(current_status__token='-2').reject_motive, self.motive)


class TestChangePaymentMethodOfPaidInvoice(ReturnAfterPaymentMethodChangeBase):

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def change_method(self):
        return self.client.put(
            reverse('invoice-change-payment-method-invoice', args=[self.invoice.id]),
            {'payment_type_final': self.cash.id, 'payment_bank_final': None}, format='json')

    def test_paid_invoice_cannot_change_payment_method(self):
        response = self.change_method()

        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.payment.payment_type_token, 'DIRECT_DEBIT')
        self.assertEqual(self.invoice.payment_type_token_final, 'DIRECT_DEBIT')

    def test_unpaid_invoice_changes_only_unpaid_payments(self):
        self.invoice.status = self.invoice_status['CONFIRMED']
        self.invoice.save()
        pending = Payment.objects.create(
            token='P-RET-2', amount=Decimal('10.00'), invoice=self.invoice,
            status=self.payment_status['1'], payment_type_token='DIRECT_DEBIT')

        response = self.change_method()

        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(pending.payment_type_token, 'CASH')
        self.assertEqual(self.payment.payment_type_token, 'DIRECT_DEBIT')

    def test_paid_payment_cannot_change_payment_type(self):
        response = self.client.patch(
            reverse('payment-detail', args=[self.payment.id]),
            {'payment_type_token': 'CASH', 'payment_type': 'Efectiu'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_type_token, 'DIRECT_DEBIT')

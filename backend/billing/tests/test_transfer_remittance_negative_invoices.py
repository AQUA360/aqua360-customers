from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Invoice, Payment, PaymentRemittance, PaymentStatus
from billing.serializers.payment_remittance_serializer import get_remittance_total_amount
from billing.utils.confirm_invoice_service import switch_negative_direct_debit_to_transfer
from billing.utils.payment_service import (
    add_negative_payment_to_balance,
    disconnect_payment_signals,
    reconnect_payment_signals,
)
from billing.views.sepa_payment_document_generate_view import (
    RequestData,
    check_for_anomalies,
    get_sepa_payments_and_batches,
)
from contract.models import Contract, PaymentType, PiggyBank
from coredata.models import ConfigProject

IBAN = 'ES9121000418450200051332'


class TestTransferRemittanceNegativeInvoices(TestCase):
    """A les transferències de retorn, a més de la devolució de saldo, hi entren
    els pagaments negatius de factures (abonaments i factures negatives), que es
    transfereixen al client en valor absolut."""

    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)

        self.balance_return = self.payment('P-SALDO', '30.00')
        self.negative_invoice = self.payment('P-ABONAMENT', '-20.00', invoice=self.invoice('F-NEG'))

    def invoice(self, token):
        return Invoice.objects.create(token=token, serie_final=f'FR/{token}')

    def payment(self, token, amount, invoice=None, payment_type_token='BANK_TRANSFER'):
        return Payment.objects.create(
            token=token, amount=Decimal(amount), invoice=invoice,
            payment_type_token=payment_type_token, payment_bank=IBAN,
            customer_token_final='12345678Z')

    def search(self, **data):
        payments, batches, is_return = get_sepa_payments_and_batches(
            RequestData({'payments_type': 'return', **data}))
        return payments, batches, is_return

    def test_inclou_saldo_i_factures_negatives(self):
        # Un cobrament per transferència d'una factura positiva no és un retorn.
        self.payment('P-COBRAMENT', '15.00', invoice=self.invoice('F-POS'))
        # Les factures negatives que encara són SEPA es queden fora.
        self.payment('P-SEPA', '-5.00', invoice=self.invoice('F-SEPA'), payment_type_token='DIRECT_DEBIT')

        payments, _, is_return = self.search()

        self.assertTrue(is_return)
        self.assertEqual(
            set(payments.values_list('token', flat=True)),
            {'P-SALDO', 'P-ABONAMENT'},
        )

    def test_lots_amb_imports_en_absolut(self):
        # Amb l'import en absolut, 30 + 20 supera el límit i surten dos lots.
        _, batches, _ = self.search(maxTotalRemittance='40')

        self.assertEqual(len(batches), 2)

    def test_imports_negatius_no_son_anomalia_als_retorns(self):
        payments = Payment.objects.filter(id=self.negative_invoice.id)

        anomalies, _ = check_for_anomalies(payments, is_return=True)
        self.assertEqual(anomalies['negative_total'], [])

        anomalies, _ = check_for_anomalies(payments, is_return=False)
        self.assertEqual(len(anomalies['negative_total']), 1)

    def test_total_de_la_remesa_en_absolut(self):
        remittance = PaymentRemittance.objects.create(token='TRF-1', is_return=True)
        remittance.payments.add(self.balance_return, self.negative_invoice)

        self.assertEqual(get_remittance_total_amount(remittance), Decimal('50.00'))

        remittance.is_return = False
        self.assertEqual(get_remittance_total_amount(remittance), Decimal('10.00'))


class TestSwitchNegativeDirectDebitToTransfer(TestCase):
    """Una factura negativa amb SEPA passa a transferència en confirmar-la,
    perquè el seu pagament es pugui retornar per remesa de transferència."""

    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)

        self.direct_debit = PaymentType.objects.create(token='DIRECT_DEBIT', name='Domiciliació')
        self.bank_transfer = PaymentType.objects.create(token='BANK_TRANSFER', name='Transferència')

    def invoice(self, total):
        return Invoice.objects.create(
            token=f'F{total}', total_final=Decimal(total), payment_type=self.direct_debit,
            payment_type_final=self.direct_debit.name, payment_type_token_final='DIRECT_DEBIT',
            payment_bank_final=IBAN)

    def test_factura_negativa_sepa_passa_a_transferencia(self):
        invoice = self.invoice('-12.00')

        switch_negative_direct_debit_to_transfer(invoice, 'DIRECT_DEBIT')

        self.assertEqual(invoice.payment_type, self.bank_transfer)
        self.assertEqual(invoice.payment_type_token_final, 'BANK_TRANSFER')
        self.assertEqual(invoice.payment_type_final, self.bank_transfer.name)
        # L'IBAN del client és el destí de la transferència.
        self.assertEqual(invoice.payment_bank_final, IBAN)

    def test_factura_positiva_es_queda_amb_sepa(self):
        invoice = self.invoice('12.00')

        switch_negative_direct_debit_to_transfer(invoice, 'DIRECT_DEBIT')

        self.assertEqual(invoice.payment_type_token_final, 'DIRECT_DEBIT')


class TestAddNegativePaymentToBalance(TestCase):
    """En comptes de retornar-la per transferència, una factura negativa es pot
    liquidar afegint-ne l'import al saldo del client."""

    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)

        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': '0'})
        self.piggy_bank = PiggyBank.objects.create(token='M-1', amount=Decimal('5.00'))
        self.contract = Contract.objects.create(token='C-SALDO', piggy_bank=self.piggy_bank)
        invoice = Invoice.objects.create(token='F-NEG', contract=self.contract, total_final=Decimal('-12.00'))
        self.payment = Payment.objects.create(token='P-NEG', amount=Decimal('-12.00'), invoice=invoice)

    def test_suma_l_import_absolut_al_moneder_del_contracte(self):
        movement = add_negative_payment_to_balance(self.payment, date(2026, 10, 29))

        self.piggy_bank.refresh_from_db()
        self.assertEqual(self.piggy_bank.amount, Decimal('17.00'))
        self.assertTrue(movement.is_positive)
        self.assertEqual(movement.amount, Decimal('12.00'))
        self.assertEqual(movement.payment, self.payment)

    def test_sense_moneder_dona_error(self):
        self.contract.piggy_bank = None
        self.contract.save()

        with self.assertRaises(ValueError):
            add_negative_payment_to_balance(self.payment, date(2026, 10, 29))


class TestManualPaymentNegativeToBalance(TestCase):
    """El pagament manual amb saldo d'un pagament negatiu es decideix pel signe
    del pagament i no pot abonar-se dues vegades."""

    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)

        for config_token, value in {
            'contract_terminated_status': '0',
            'payment_status_paid_token': 'PAID',
            'payment_status_cancelled_token': 'CANCELLED',
            'payment_status_piggy_token': 'PIGGY',
            'payment_status_payoff_token': 'PAYOFF',
        }.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': value})
        self.pending = PaymentStatus.objects.create(token='PENDING', name='Pendent')
        PaymentStatus.objects.create(token='PAID', name='Pagat')
        PaymentStatus.objects.create(token='CANCELLED', name='Abonat')
        self.balance = PaymentType.objects.create(token='BALANCE', name='Saldo')

        self.piggy_bank = PiggyBank.objects.create(token='M-2', amount=Decimal('5.00'))
        contract = Contract.objects.create(token='C-MANUAL', piggy_bank=self.piggy_bank)
        self.payment = Payment.objects.create(
            token='P-MANUAL', amount=Decimal('-12.00'), contract=contract, status=self.pending)

        user = get_user_model().objects.create_superuser(username='admin-saldo', password='x')
        self.client = APIClient()
        self.client.force_authenticate(user)

    def pay(self, amount, payment_date='2026-10-29'):
        return self.client.post(reverse('payment-manual-payment'), {
            'id': self.payment.id, 'payment_date': payment_date,
            'payment_method': self.balance.id, 'amount': amount,
        }, format='json')

    def test_import_positiu_obsolet_tambe_abona(self):
        # Un import d'un altre pagament (positiu) no ha de restar del moneder.
        response = self.pay('30.00')

        self.assertEqual(response.status_code, 200)
        self.piggy_bank.refresh_from_db()
        self.assertEqual(self.piggy_bank.amount, Decimal('17.00'))

    def test_no_abona_dues_vegades(self):
        self.assertEqual(self.pay('-12.00').status_code, 200)
        self.assertEqual(self.pay('-12.00').status_code, 400)

        self.piggy_bank.refresh_from_db()
        self.assertEqual(self.piggy_bank.amount, Decimal('17.00'))

    def test_sense_data_no_abona(self):
        self.assertEqual(self.pay('-12.00', payment_date='').status_code, 400)

        self.piggy_bank.refresh_from_db()
        self.assertEqual(self.piggy_bank.amount, Decimal('5.00'))

    def test_remesa_pendent_no_abona(self):
        sent = PaymentRemittance.objects.create(token='TRF-SENT', sent_at=date(2026, 10, 28), is_return=True)
        pending = PaymentRemittance.objects.create(token='TRF-PENDING', is_return=True)
        self.payment.remittances.add(sent, pending)

        response = self.pay('-12.00')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Payment belongs to a pending remittance.')
        self.piggy_bank.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.piggy_bank.amount, Decimal('5.00'))
        self.assertFalse(self.piggy_bank.movements.exists())
        self.assertEqual(self.payment.status, self.pending)
        self.assertIsNone(self.payment.payment_date)
        self.assertIsNone(self.payment.paid_at)
        self.assertFalse(self.payment.movements.exists())
        self.assertTrue(pending.payments.filter(id=self.payment.id).exists())

    def test_remesa_enviada_permet_abonar(self):
        sent = PaymentRemittance.objects.create(token='TRF-SENT', sent_at=date(2026, 10, 28), is_return=True)
        self.payment.remittances.add(sent)

        self.assertEqual(self.pay('-12.00').status_code, 200)

        self.piggy_bank.refresh_from_db()
        self.assertEqual(self.piggy_bank.amount, Decimal('17.00'))

from datetime import date
from decimal import Decimal

from django.test import TestCase

from billing.models import (
    CommitmentDeposit, CommitmentDepositStatus, Payment, PaymentCommitment, PaymentCommitmentStatus, PaymentStatus,
)
from contract.models import Contract, PaymentType
from coredata.models import ConfigProject


class CommitmentDepositPaymentCollectionTests(TestCase):
    """Cobrament dels pagaments d'un compromís de pagament: cada pagament es descompta una sola vegada."""

    @classmethod
    def setUpTestData(cls):
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

        for config_token, value in {
            'commitment_deposit_status_paid_token': 'CD_PAID',
            'commitment_deposit_status_partially_paid_token': 'CD_PARTIAL',
            'commitment_deposit_status_cancelled_token': 'CD_CANCELLED',
            'payment_commitment_status_paid_token': 'PC_PAID',
            'payment_commitment_status_partially_paid_token': 'PC_PARTIAL',
            'payment_commitment_status_pending_token': 'PC_PENDING',
            'payment_commitment_status_confirmed_token': 'PC_CONFIRMED',
            'payment_commitment_status_cancelled_token': 'PC_CANCELLED',
            'direct_debit_token': 'DIRECT_DEBIT',
            'bank_payment_token': 'BANK_PAYMENT',
            'contract_terminated_status': '0',
        }.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': value})
        cls.deposit_status = {
            token: CommitmentDepositStatus.objects.create(token=token, name=token)
            for token in ('CD_PENDING', 'CD_PAID', 'CD_PARTIAL', 'CD_CANCELLED')
        }
        cls.pc_status = {
            token: PaymentCommitmentStatus.objects.create(token=token, name=token)
            for token in ('PC_PAID', 'PC_PARTIAL', 'PC_PENDING', 'PC_CONFIRMED', 'PC_CANCELLED')
        }
        PaymentType.objects.create(token='CARD', name='Targeta')

    def setUp(self):
        self.contract = Contract.objects.create(token='C-COMPROMIS')
        self.deposit = CommitmentDeposit.objects.create(
            token='CP0001', contract=self.contract, status=self.deposit_status['CD_PENDING'], total=Decimal('300.00'),
            remaining=Decimal('300.00'), remaining_to_share=Decimal('0.00'))
        for index, due_date in enumerate((date(2026, 11, 27), date(2026, 12, 27), date(2027, 1, 26))):
            PaymentCommitment.objects.create(
                token=f'CP000100{index}', commitment_deposit=self.deposit, is_guide=True,
                amount=Decimal('100.00'), currently_paid=Decimal('0.00'), due_date=due_date,
                status=self.pc_status['PC_CONFIRMED'])
        self.payment = Payment.objects.create(
            token='CP000101', commitment_deposit=self.deposit, contract=self.contract,
            amount=Decimal('100.00'), status=self.payment_status['1'],
            payment_type='Targeta', payment_type_token='CARD', due_date=date(2026, 11, 27))

    def collect(self, payment_date=date(2026, 11, 11)):
        self.payment.status = self.payment_status['0']
        self.payment.payment_date = payment_date
        self.payment.save()

    def collections(self):
        return PaymentCommitment.objects.filter(commitment_deposit=self.deposit, is_guide=False)

    def assert_collected_once(self):
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.remaining, Decimal('200.00'))
        self.assertEqual(self.collections().count(), 1)
        self.assertEqual(
            PaymentCommitment.objects.filter(commitment_deposit=self.deposit, is_guide=True,
                                             status=self.pc_status['PC_PAID']).count(), 1)

    def test_collecting_a_payment_discounts_it_from_the_commitment(self):
        self.collect()

        self.assert_collected_once()

    def test_editing_a_collected_payment_does_not_discount_it_again(self):
        self.collect()

        self.payment.payment_date = date(2026, 11, 27)
        self.payment.save()
        Payment.objects.get(id=self.payment.id).save()

        self.assert_collected_once()
        self.assertEqual(self.collections().get().payment_date, date(2026, 11, 11))

    def test_failed_collection_leaves_the_payment_unpaid_and_can_be_retried(self):
        # Sense el tipus de pagament configurat, el cobrament del compromís falla
        Payment.objects.filter(id=self.payment.id).update(payment_type='Bizum', payment_type_token='BIZUM')
        self.payment.refresh_from_db()

        with self.assertRaises(Exception):
            self.collect()

        self.assertEqual(Payment.objects.get(id=self.payment.id).status, self.payment_status['1'])
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.remaining, Decimal('300.00'))
        self.assertFalse(self.collections().exists())

        PaymentType.objects.create(token='BIZUM', name='Bizum')
        self.payment = Payment.objects.get(id=self.payment.id)
        self.collect()

        self.assert_collected_once()

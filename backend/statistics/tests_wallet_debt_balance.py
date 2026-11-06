import datetime
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from billing.models import Invoice, Payment, PaymentMovement, PaymentStatus
from contract.models import Contract, PiggyBank, PiggyBankMovement
from coredata.models import ConfigProject
from statistics.utils.report_wallet_debt_balance_service import (
    get_contract_balances_at,
    get_contract_debts_at,
    get_debt_status_tokens,
    parse_cutoff_date,
)

D = datetime.date


class ParseCutoffDateTests(SimpleTestCase):
    def test_accepts_date_and_iso_strings(self):
        self.assertEqual(parse_cutoff_date('2026-03-15'), D(2026, 3, 15))
        self.assertEqual(parse_cutoff_date('2026-03-15T23:00:00.000Z'), D(2026, 3, 15))
        self.assertEqual(parse_cutoff_date(D(2026, 3, 15)), D(2026, 3, 15))

    def test_invalid_or_empty_returns_none(self):
        self.assertIsNone(parse_cutoff_date(None))
        self.assertIsNone(parse_cutoff_date(''))
        self.assertIsNone(parse_cutoff_date('not-a-date'))


class WalletDebtBalanceAtDateTests(TestCase):
    """Reconstrucció del deute (via PaymentMovement) i del saldo (via PiggyBankMovement) a una data."""

    @classmethod
    def setUpTestData(cls):
        tokens = {
            'payment_status_pending_token': '1',
            'payment_status_sent_token': '2',
            'payment_status_expired_token': '-1',
            'payment_status_returned_token': '-2',
            'payment_status_endowment_token': '-3',
        }
        for config_token, value in tokens.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': value})
        cls.status = {}
        for token in ['1', '2', '-1', '-2', '-3', '0', '4', '-6']:
            cls.status[token] = PaymentStatus.objects.create(token=f'{token}')
        cls.debt_tokens = get_debt_status_tokens()

        cls.contract, cls.other_contract = Contract.objects.bulk_create([
            Contract(token='C-TEST-1'), Contract(token='C-TEST-2'),
        ])
        cls.invoice = Invoice.objects.bulk_create([Invoice(issue_date=D(2026, 1, 10), contract=cls.contract)])[0]

    def _payment(self, status, amount, contract=None, invoice=None, token=None):
        payment = Payment.objects.bulk_create([Payment(
            token=token or f'P-{Payment.objects.count() + 1}',
            status=self.status[status],
            amount=Decimal(amount),
            contract=contract,
            invoice=invoice,
        )])[0]
        Payment.objects.filter(id=payment.id).update(updated_at=datetime.datetime(2026, 1, 10, tzinfo=datetime.timezone.utc))
        return payment

    def _movement(self, payment, previous, current, date):
        PaymentMovement.objects.create(
            payment=payment,
            previous_status=self.status[previous] if previous else None,
            current_status=self.status[current],
            movement_date=date,
        )

    def test_status_is_rebuilt_from_movements(self):
        # Pendent -> pagat el 1/2 -> retornat el 1/3 -> pagat el 1/4
        payment = self._payment('0', '100.00', invoice=self.invoice)
        self._movement(payment, '1', '0', D(2026, 2, 1))
        self._movement(payment, '0', '-2', D(2026, 3, 1))
        self._movement(payment, '-2', '0', D(2026, 4, 1))

        self.assertEqual(get_contract_debts_at(D(2026, 1, 5), self.debt_tokens), {})  # factura encara no emesa
        self.assertEqual(get_contract_debts_at(D(2026, 1, 20), self.debt_tokens), {self.contract.id: Decimal('100.00')})
        self.assertEqual(get_contract_debts_at(D(2026, 2, 15), self.debt_tokens), {})
        self.assertEqual(get_contract_debts_at(D(2026, 3, 15), self.debt_tokens), {self.contract.id: Decimal('100.00')})
        self.assertEqual(get_contract_debts_at(D(2026, 4, 15), self.debt_tokens), {})

    def test_payment_without_movements_uses_current_status(self):
        self._payment('-1', '30.00', invoice=self.invoice)
        self._payment('4', '50.00', invoice=self.invoice)  # en compromís: no compta
        self.assertEqual(get_contract_debts_at(D(2026, 2, 1), self.debt_tokens), {self.contract.id: Decimal('30.00')})

    def test_untracked_cancellation_uses_rectifying_invoice_date(self):
        Invoice.objects.bulk_create([Invoice(token='RECT-1', issue_date=D(2026, 3, 1))])
        Invoice.objects.filter(id=self.invoice.id).update(return_token='RECT-1')
        payment = self._payment('-6', '80.00', invoice=self.invoice)
        self._movement(payment, '0', '-2', D(2026, 2, 1))

        self.assertEqual(get_contract_debts_at(D(2026, 2, 15), self.debt_tokens), {self.contract.id: Decimal('80.00')})
        self.assertEqual(get_contract_debts_at(D(2026, 3, 1), self.debt_tokens), {})

    def test_contract_falls_back_to_payment_contract(self):
        self._payment('1', '12.50', contract=self.other_contract)
        self.assertEqual(get_contract_debts_at(D(2099, 1, 1), self.debt_tokens), {self.other_contract.id: Decimal('12.50')})

    def test_balance_sums_signed_movements_until_date(self):
        piggy_bank = PiggyBank.objects.create(token='PB-TEST')
        Contract.objects.filter(id=self.contract.id).update(piggy_bank=piggy_bank)
        PiggyBankMovement.objects.bulk_create([
            PiggyBankMovement(piggy_bank=piggy_bank, amount=Decimal('50.00'), is_positive=True, movement_date=D(2026, 1, 1)),
            PiggyBankMovement(piggy_bank=piggy_bank, amount=Decimal('20.00'), is_positive=False, movement_date=D(2026, 2, 1)),
            PiggyBankMovement(piggy_bank=piggy_bank, amount=Decimal('99.00'), is_positive=True, movement_date=D(2026, 3, 1), is_active=False),
        ])
        self.assertEqual(get_contract_balances_at(D(2025, 12, 31)), {})
        self.assertEqual(get_contract_balances_at(D(2026, 1, 15)), {self.contract.id: Decimal('50.00')})
        self.assertEqual(get_contract_balances_at(D(2026, 3, 15)), {self.contract.id: Decimal('30.00')})

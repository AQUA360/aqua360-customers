import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from billing.models import InvoiceStatus, PaymentStatus
from contract.models import Bail, BailStatus, Contract, ContractStatus, PiggyBank, PiggyBankMovement
from contract.utils.bail_service import immediate_return_bail, pending_bail_contract_termination
from coredata.models import ConfigProject
from service.models import Company


class BailReturnWithoutInvoiceTest(TestCase):
    """Amb BAIL_RETURN_INVOICE_DISABLED el retorn de fiança es completa sense factura ni abonament al saldo."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('bail_status_unreturned_token', 'B_UNRETURNED'),
            ('bail_status_pending_token', 'B_PENDING'),
            ('bail_status_returned_token', 'B_RETURNED'),
            ('invoice_status_confirmed_token', 'I_CONFIRMED'),
            ('payment_status_piggy_token', 'P_PIGGY'),
            ('BAIL_RETURN_INVOICE_DISABLED', 'true'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.active, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Actiu'})
        cls.unreturned = BailStatus.objects.create(token='B_UNRETURNED', name='No retornat')
        BailStatus.objects.create(token='B_PENDING', name='Pendent')
        cls.returned = BailStatus.objects.create(token='B_RETURNED', name='Retornat')
        InvoiceStatus.objects.get_or_create(token='I_CONFIRMED', defaults={'name': 'Confirmada'})
        PaymentStatus.objects.get_or_create(token='P_PIGGY', defaults={'name': 'Saldo'})
        cls.user = get_user_model().objects.create_superuser('bail-admin', 'bail-admin@example.com', 'x')
        cls.company = Company.objects.create(name='Company bail')

    def _contract_with_bail(self, token, with_piggy_bank=True):
        piggy_bank = PiggyBank.objects.create(token=f'PB-{token}', amount=Decimal('0.00')) if with_piggy_bank else None
        # Sense forma de pagament: amb la factura deshabilitada no és necessària
        contract = Contract.objects.create(
            company=self.company, token=f'CON-{token}', status=self.active, is_active=True, piggy_bank=piggy_bank,
        )
        bail = Bail.objects.create(token=f'B-{token}', contract=contract, status=self.unreturned, amount=Decimal('50.00'))
        contract.bails.add(bail)
        return contract, bail

    def _assert_returned_without_invoice(self, contract, bail):
        bail.refresh_from_db()
        self.assertEqual(bail.status, self.returned)
        self.assertIsNone(bail.invoice)
        self.assertFalse(PiggyBankMovement.objects.filter(bail=bail).exists())
        if contract.piggy_bank:
            contract.piggy_bank.refresh_from_db()
            self.assertEqual(contract.piggy_bank.amount, Decimal('0.00'))

    @patch('contract.utils.bail_service.invoice_generate_return_bail')
    def test_immediate_return_skips_invoice(self, generate_invoice):
        contract, bail = self._contract_with_bail('1')

        immediate_return_bail(self.user, bail.id)

        generate_invoice.assert_not_called()
        self._assert_returned_without_invoice(contract, bail)

    @patch('contract.utils.bail_service.invoice_generate_return_bail')
    def test_immediate_return_uses_given_return_date(self, generate_invoice):
        contract, bail = self._contract_with_bail('5')

        immediate_return_bail(self.user, bail.id, return_date=datetime.date(2026, 1, 15))

        bail.refresh_from_db()
        self.assertEqual(bail.return_date, datetime.date(2026, 1, 15))

    @patch('contract.utils.bail_service.invoice_generate_return_bail')
    def test_immediate_return_defaults_return_date_to_today(self, generate_invoice):
        contract, bail = self._contract_with_bail('6')

        immediate_return_bail(self.user, bail.id)

        bail.refresh_from_db()
        self.assertEqual(bail.return_date, timezone.localdate())

    @patch('contract.utils.bail_service.invoice_generate_return_bail')
    def test_immediate_return_without_balance(self, generate_invoice):
        contract, bail = self._contract_with_bail('4', with_piggy_bank=False)

        immediate_return_bail(self.user, bail.id)

        generate_invoice.assert_not_called()
        self._assert_returned_without_invoice(contract, bail)

    @patch('contract.utils.bail_service.invoice_generate_return_bail')
    def test_termination_return_skips_invoice(self, generate_invoice):
        contract, bail = self._contract_with_bail('2')

        pending_bail_contract_termination(self.user, contract)

        generate_invoice.assert_not_called()
        self._assert_returned_without_invoice(contract, bail)

    @patch('contract.utils.bail_service.invoice_generate_return_bail')
    def test_termination_without_payment_keeps_bails_when_invoice_enabled(self, generate_invoice):
        ConfigProject.objects.filter(token='BAIL_RETURN_INVOICE_DISABLED').update(value='false')
        contract, bail = self._contract_with_bail('3')

        pending_bail_contract_termination(self.user, contract)

        generate_invoice.assert_not_called()
        bail.refresh_from_db()
        self.assertEqual(bail.status, self.unreturned)

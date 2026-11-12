from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from billing.utils import remittance_block_service as service

CONFIG = {
    'block_remittance_if_unpaid': 'true',
    'direct_debit_token': 'DIRECT_DEBIT',
    'bank_payment_token': 'BANK_PAYMENT',
}


class BlockedRemittancePaymentTypeTests(SimpleTestCase):

    def setUp(self):
        self.config = dict(CONFIG)
        self.bank_payment = SimpleNamespace(token='BANK_PAYMENT', name='Pagament bancari')
        self.direct_debit = SimpleNamespace(token='DIRECT_DEBIT', name='Domiciliació')
        self.contract = SimpleNamespace(id=1)

        patches = [
            patch.object(service, '_config_value', side_effect=lambda token: self.config.get(token)),
            patch.object(service, 'contract_has_unpaid_invoices', return_value=True),
            patch.object(service.PaymentType.objects, 'filter'),
        ]
        mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        self.has_unpaid = mocks[1]
        mocks[2].return_value.first.return_value = self.bank_payment

    def test_direct_debit_with_unpaid_invoices_goes_to_bank_payment(self):
        result = service.blocked_remittance_payment_type(self.contract, self.direct_debit)
        self.assertIs(result, self.bank_payment)

    def test_disabled_by_default(self):
        for value in (None, '', 'false', 'False'):
            self.config['block_remittance_if_unpaid'] = value
            self.assertIsNone(service.blocked_remittance_payment_type(self.contract, self.direct_debit))
        self.has_unpaid.assert_not_called()

    def test_without_unpaid_invoices_keeps_payment(self):
        self.has_unpaid.return_value = False
        self.assertIsNone(service.blocked_remittance_payment_type(self.contract, self.direct_debit))

    def test_other_payment_types_are_untouched(self):
        transfer = SimpleNamespace(token='BANK_TRANSFER', name='Transferència')
        self.assertIsNone(service.blocked_remittance_payment_type(self.contract, transfer))
        self.assertIsNone(service.blocked_remittance_payment_type(self.contract, None))
        self.has_unpaid.assert_not_called()

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import GeneralPayment
from contract.models import Contract, ContractDataChange, ContractStatus, PaymentType
from contract.utils.contract_service import _update_contract_payment
from coredata.models import ConfigProject, Person, PersonBank


class BankChangeHistoryTest(TestCase):
    """Canvi de compte per fitxer bancari: ha de quedar a l'historial del contracte."""

    @classmethod
    def setUpTestData(cls):
        # El signal post_save de Contract la llegeix; un valor que no coincideix amb cap
        # estat de la prova evita el flux de fiances de baixa, que aquí no es prova.
        ConfigProject.objects.update_or_create(
            token='contract_terminated_status', defaults={'value': 'BCH_UNUSED_TERMINATED'}
        )
        cls.status, _ = ContractStatus.objects.get_or_create(token='BCH_ACTIVE', defaults={'name': 'Actiu'})
        cls.direct_debit = PaymentType.objects.create(token='BCH_DIRECT_DEBIT', name='Domiciliació')
        cls.window = PaymentType.objects.create(token='BCH_WINDOW', name='Finestreta')
        cls.user = get_user_model().objects.create_user('bch-user', 'bch@example.com', 'x')
        cls.holder = Person.objects.create(name='Titular', surname='Prova', token='00000000T')
        cls.old_bank = PersonBank.objects.create(
            person=cls.holder, token='BCH_OLD', iban='ES0000000000000000000000')
        cls.new_bank = PersonBank.objects.create(
            person=cls.holder, token='BCH_NEW', iban='ES1111111111111111111111')

    def _contract(self, token, payment=None):
        return Contract.objects.create(
            token=token, status=self.status, is_active=True, holder=self.holder, payment=payment)

    def _update(self, contract, person_bank):
        _update_contract_payment(
            contract, person_bank, self.direct_debit, self.direct_debit.token, self.user)

    def test_change_on_existing_payment_is_recorded(self):
        payment = GeneralPayment.objects.create(token='BCH_GP', type=self.window, IBAN=self.old_bank)
        contract = self._contract('BCH-1', payment)

        self._update(contract, self.new_bank)

        payment.refresh_from_db()
        self.assertEqual(payment.IBAN, self.new_bank)
        self.assertEqual(payment.type, self.direct_debit)
        change = ContractDataChange.objects.get(contract=contract)
        self.assertEqual(change.previous_payment, self.old_bank)
        self.assertEqual(change.new_payment, self.new_bank)
        self.assertEqual(change.previous_payment_type, self.window)
        self.assertEqual(change.new_payment_type, self.direct_debit)
        self.assertIsNone(change.new_general_payment)
        self.assertEqual(change.user, self.user)
        self.assertEqual(change.token, 'CDC_BCH-1_1')
        self.assertIsNotNone(change.approved_at)

    def test_contract_without_payment_records_created_payment(self):
        contract = self._contract('BCH-2')

        self._update(contract, self.new_bank)

        contract.refresh_from_db()
        self.assertIsNotNone(contract.payment)
        self.assertEqual(contract.payment.IBAN, self.new_bank)
        change = ContractDataChange.objects.get(contract=contract)
        self.assertIsNone(change.previous_payment)
        self.assertEqual(change.new_payment, self.new_bank)
        self.assertIsNone(change.previous_payment_type)
        self.assertEqual(change.new_payment_type, self.direct_debit)
        self.assertEqual(change.new_general_payment, contract.payment)

    def test_same_account_and_type_is_not_recorded(self):
        payment = GeneralPayment.objects.create(token='BCH_GP3', type=self.direct_debit, IBAN=self.new_bank)
        contract = self._contract('BCH-3', payment)

        self._update(contract, self.new_bank)

        self.assertFalse(ContractDataChange.objects.filter(contract=contract).exists())

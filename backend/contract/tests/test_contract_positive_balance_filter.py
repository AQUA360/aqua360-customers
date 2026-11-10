from decimal import Decimal

from django.test import TestCase

from contract.filters.contract_filter import ContractFilter
from contract.models import Contract, ContractStatus, PiggyBank
from coredata.models import ConfigProject


class ContractPositiveBalanceFilterTest(TestCase):
    """Filtre has_positive_balance del llistat de contractes (saldo de la guardiola)."""

    @classmethod
    def setUpTestData(cls):
        # El signal post_save de Contract la llegeix; un valor que no coincideix amb cap
        # estat de la prova evita el flux de fiances de baixa, que aquí no es prova.
        ConfigProject.objects.update_or_create(
            token='contract_terminated_status', defaults={'value': 'PB_UNUSED_TERMINATED'}
        )
        cls.active, _ = ContractStatus.objects.get_or_create(token='PB_ACTIVE', defaults={'name': 'Actiu'})
        cls.terminated, _ = ContractStatus.objects.get_or_create(token='PB_TERMINATED', defaults={'name': 'Baixa'})

        cls.with_balance = cls._contract('PB-POS', cls.active, Decimal('25.50'))
        cls.zero_balance = cls._contract('PB-ZERO', cls.active, Decimal('0'))
        cls.without_piggy_bank = cls._contract('PB-NONE', cls.active, None)
        cls.terminated_with_balance = cls._contract('PB-TERM-POS', cls.terminated, Decimal('10'))
        cls.terminated_zero_balance = cls._contract('PB-TERM-ZERO', cls.terminated, Decimal('0'))

    @classmethod
    def _contract(cls, token, status, amount):
        contract = Contract.objects.create(token=token, status=status, is_active=True)
        if amount is not None:
            piggy_bank = PiggyBank.objects.create(token=f'PB-{token}', amount=amount)
            Contract.objects.filter(pk=contract.pk).update(piggy_bank=piggy_bank)
        return contract

    def _ids(self, data):
        return set(ContractFilter(data=data, queryset=Contract.objects.all()).qs.values_list('id', flat=True))

    def test_positive_balance_true(self):
        expected = {self.with_balance.id, self.terminated_with_balance.id}
        self.assertEqual(self._ids({'has_positive_balance': 'true'}), expected)
        self.assertEqual(self._ids({'has_positive_balance': '1'}), expected)

    def test_positive_balance_false_includes_zero_and_missing_piggy_bank(self):
        expected = {self.zero_balance.id, self.without_piggy_bank.id, self.terminated_zero_balance.id}
        self.assertEqual(self._ids({'has_positive_balance': 'false'}), expected)
        self.assertEqual(self._ids({'has_positive_balance': '0'}), expected)

    def test_combined_with_status_filter(self):
        ids = self._ids({'has_positive_balance': 'true', 'status': str(self.terminated.id)})
        self.assertEqual(ids, {self.terminated_with_balance.id})

    def test_empty_or_invalid_value_does_not_filter(self):
        all_ids = self._ids({})
        self.assertEqual(self._ids({'has_positive_balance': ''}), all_ids)
        self.assertEqual(self._ids({'has_positive_balance': 'maybe'}), all_ids)

from django.test import TestCase

from contract.filters.contract_filter import ContractFilter
from contract.models import Contract, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from contract.utils.contract_list_queryset import _termination_status_tokens
from coredata.models import ConfigProject


class ContractPendingTerminationFilterTest(TestCase):
    """Filtre pending_termination del llistat de contractes (sol·licitud de baixa oberta)."""

    @classmethod
    def setUpTestData(cls):
        # El signal post_save de Contract la llegeix; un valor que no coincideix amb cap
        # estat de la prova evita el flux de fiances de baixa, que aquí no es prova.
        ConfigProject.objects.update_or_create(
            token='contract_terminated_status', defaults={'value': 'PT_UNUSED_TERMINATED'}
        )
        ConfigProject.objects.update_or_create(
            token='contract_termination_cancelled_token', defaults={'value': 'PT_CANCELLED'}
        )
        ConfigProject.objects.update_or_create(
            token='contract_termination_completed_token', defaults={'value': 'PT_COMPLETED'}
        )
        cls.active, _ = ContractStatus.objects.get_or_create(token='PT_ACTIVE', defaults={'name': 'Actiu'})
        cls.terminated, _ = ContractStatus.objects.get_or_create(token='PT_TERMINATED', defaults={'name': 'Baixa'})

        pending = ContractTerminationStatus.objects.create(token='PT_PENDING', name='Pendent')
        cancelled = ContractTerminationStatus.objects.create(token='PT_CANCELLED', name='Anul·lada')
        completed = ContractTerminationStatus.objects.create(token='PT_COMPLETED', name='Finalitzada')

        cls.with_pending = Contract.objects.create(token='PT-PENDING', status=cls.active, is_active=True)
        cls.with_cancelled = Contract.objects.create(token='PT-CANCELLED', status=cls.active, is_active=True)
        cls.with_completed = Contract.objects.create(token='PT-COMPLETED', status=cls.terminated, is_active=True)
        cls.without_request = Contract.objects.create(token='PT-NONE', status=cls.active, is_active=True)

        # bulk_create: el signal de la sol·licitud de baixa (ordres de treball) no és el que es prova.
        ContractTerminationRequest.objects.bulk_create([
            ContractTerminationRequest(contract=cls.with_pending, status=pending),
            ContractTerminationRequest(contract=cls.with_cancelled, status=cancelled),
            ContractTerminationRequest(contract=cls.with_completed, status=completed),
        ])

    def setUp(self):
        _termination_status_tokens.cache_clear()
        self.addCleanup(_termination_status_tokens.cache_clear)

    def _ids(self, data):
        return set(ContractFilter(data=data, queryset=Contract.objects.all()).qs.values_list('id', flat=True))

    def test_pending_termination_true(self):
        expected = {self.with_pending.id}
        self.assertEqual(self._ids({'pending_termination': 'true'}), expected)
        self.assertEqual(self._ids({'pending_termination': '1'}), expected)

    def test_pending_termination_false_ignores_cancelled_and_completed(self):
        expected = {self.with_cancelled.id, self.with_completed.id, self.without_request.id}
        self.assertEqual(self._ids({'pending_termination': 'false'}), expected)

    def test_combined_with_status_filter(self):
        ids = self._ids({'pending_termination': 'true', 'status': str(self.terminated.id)})
        self.assertEqual(ids, set())

    def test_empty_or_invalid_value_does_not_filter(self):
        all_ids = self._ids({})
        self.assertEqual(self._ids({'pending_termination': ''}), all_ids)
        self.assertEqual(self._ids({'pending_termination': 'maybe'}), all_ids)

import datetime
import io
from unittest import mock

from django.db.models.signals import post_save, pre_save
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from contract.filters.contract_filter import ContractFilter
from contract.models import Contract, ContractLog
from coredata.models import ConfigProject
from integrations.models import IntegrationRequestLog
from integrations.outbound.ov.client import OVClient
from integrations.outbound.ov import sync as sync_module
from integrations.outbound.ov.exceptions import OVApiError
from integrations.outbound.ov.sync import (
    extract_active_contracts,
    parse_link_date,
    sync_virtual_office_contracts,
)
from integrations.outbound.ov.tasks import sync_virtual_office_contracts_task

D1 = datetime.date(2026, 3, 15)
D2 = datetime.date(2026, 5, 2)


def link(token, link_date=None):
    """Element de la resposta de l'OV (una vinculació d'usuari a contracte)."""
    return {
        'contract_number': token,
        'user_email': 'usuari@example.com',
        'user_registration_date': '2025-01-01T09:00:00Z',
        'contract_link_date': link_date,
    }


class ParseTests(TestCase):
    def test_link_date(self):
        self.assertEqual(parse_link_date('2026-03-15T10:20:00.793511Z'), D1)
        self.assertEqual(parse_link_date('2026-03-15'), D1)
        # UTC de les 23:30 → l'endemà a hora local
        self.assertEqual(parse_link_date('2026-03-14T23:30:00Z'), D1)
        self.assertIsNone(parse_link_date('no és una data'))
        self.assertIsNone(parse_link_date(None))

    def test_extract_keeps_the_oldest_link_of_each_contract(self):
        self.assertEqual(
            extract_active_contracts([
                link('A', '2026-05-02T08:00:00Z'), link(' A ', '2026-03-15T08:00:00Z'),
                link('B'), link(''), 'C',
            ]),
            {'A': D1, 'B': None},
        )

    def test_extract_rejects_unexpected_response(self):
        with self.assertRaises(OVApiError):
            extract_active_contracts({'detail': 'error'})


class SyncTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # El senyal de baixa del contracte la llegeix en cada save.
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': '0'})
        cls.new = Contract.objects.create(token='OV-NEW')
        cls.no_date = Contract.objects.create(token='OV-NODATE')
        cls.changed = Contract.objects.create(token='OV-CHANGED', virtual_office_date=D1)
        cls.kept = Contract.objects.create(token='OV-KEPT', virtual_office_date=D1)
        cls.gone = Contract.objects.create(token='OV-GONE', virtual_office_date=D1)
        cls.other = Contract.objects.create(token='OV-OTHER')
        cls.inactive = Contract.objects.create(token='OV-INACTIVE', is_active=False)

    def run_sync(self):
        return sync_virtual_office_contracts([
            link('OV-NEW', '2026-03-15T07:06:50.793511Z'),
            link('OV-NODATE'),
            link('OV-CHANGED', '2026-05-02T07:06:50Z'),
            link('OV-KEPT'),
            link('OV-INACTIVE', '2026-03-15T07:06:50Z'),
            link('OV-UNKNOWN', '2026-03-15T07:06:50Z'),
        ])

    def date_of(self, contract):
        contract.refresh_from_db()
        return contract.virtual_office_date

    def test_registers_updates_and_unregisters(self):
        stats = self.run_sync()

        self.assertEqual(self.date_of(self.new), D1)
        self.assertEqual(self.date_of(self.no_date), timezone.localdate())
        self.assertEqual(self.date_of(self.changed), D2)
        self.assertEqual(self.date_of(self.kept), D1)
        self.assertIsNone(self.date_of(self.gone))
        self.assertIsNone(self.date_of(self.other))
        self.assertIsNone(self.date_of(self.inactive))
        self.assertEqual(
            {k: stats[k] for k in ('ov_contracts', 'registered', 'updated', 'unregistered', 'unchanged', 'errors')},
            {'ov_contracts': 6, 'registered': 2, 'updated': 1, 'unregistered': 1, 'unchanged': 1, 'errors': 0},
        )
        self.assertEqual(stats['not_found_tokens'], ['OV-INACTIVE', 'OV-UNKNOWN'])

    def test_changes_go_to_contract_history_as_automatic_process(self):
        self.run_sync()

        logs = ContractLog.objects.filter(field_name='virtual_office_date')
        self.assertEqual(logs.count(), 4)
        gone = logs.get(contract=self.gone)
        self.assertEqual((gone.old_value, gone.new_value, gone.user), (str(D1), None, None))
        new = logs.get(contract=self.new)
        self.assertEqual((new.old_value, new.new_value), (None, str(D1)))

    def test_second_run_changes_nothing(self):
        self.run_sync()
        stats = self.run_sync()
        self.assertEqual((stats['registered'], stats['updated'], stats['unregistered']), (0, 0, 0))

    def test_empty_list_does_not_unregister_everyone(self):
        with self.assertRaises(OVApiError):
            sync_virtual_office_contracts([])
        self.assertEqual(self.date_of(self.gone), D1)

    def test_one_failing_contract_does_not_stop_the_rest(self):
        original_write = sync_module.write_virtual_office_date

        def failing_write(contract_id, *args):
            if contract_id == self.new.pk:
                raise RuntimeError('error de prova')
            return original_write(contract_id, *args)

        with mock.patch.object(sync_module, 'write_virtual_office_date', failing_write), \
                self.assertLogs('integrations.outbound.ov.sync', 'ERROR'):
            stats = self.run_sync()

        self.assertEqual(stats['errors'], 1)
        self.assertIsNone(self.date_of(self.new))
        self.assertIsNone(self.date_of(self.gone))

    def test_does_not_fire_contract_signals(self):
        """Els senyals del contracte fan feina de negoci en desar (p. ex. retornar les
        fiances d'un contracte de baixa): la sincronització no els ha de disparar."""
        saved = []

        def receiver(sender, instance, **kwargs):
            saved.append(instance.pk)

        pre_save.connect(receiver, sender=Contract, dispatch_uid='ov-test-pre')
        post_save.connect(receiver, sender=Contract, dispatch_uid='ov-test-post')
        try:
            self.run_sync()
        finally:
            pre_save.disconnect(sender=Contract, dispatch_uid='ov-test-pre')
            post_save.disconnect(sender=Contract, dispatch_uid='ov-test-post')

        self.assertEqual(saved, [])
        self.assertEqual(self.date_of(self.new), D1)

    def test_without_ov_date_keeps_the_date_read_under_lock(self):
        """Si una altra sincronització ha desat la data mentrestant, no se substitueix per avui."""
        Contract.objects.filter(pk=self.no_date.pk).update(virtual_office_date=D1)

        key = sync_module.write_virtual_office_date(self.no_date.pk, True, None, timezone.localdate())

        self.assertEqual(key, 'unchanged')
        self.assertEqual(self.date_of(self.no_date), D1)

    def test_list_filter(self):
        Contract.objects.filter(pk=self.new.pk).update(virtual_office_date=D1)
        queryset = Contract.objects.filter(token__startswith='OV-')

        with_ov = ContractFilter(data={'has_virtual_office': 'true'}, queryset=queryset).qs
        without_ov = ContractFilter(data={'has_virtual_office': 'false'}, queryset=queryset).qs

        self.assertEqual(set(with_ov.values_list('token', flat=True)), {'OV-NEW', 'OV-CHANGED', 'OV-KEPT', 'OV-GONE'})
        self.assertEqual(set(without_ov.values_list('token', flat=True)), {'OV-NODATE', 'OV-OTHER'})


@override_settings(OV_API_BASE_URL='https://ov.example.com', OV_API_KEY='secret', OV_SYNC_ENABLED=True)
class ClientAndTaskTests(TestCase):
    def test_client_sends_key_and_logs_only_the_count(self):
        response = mock.Mock(ok=True, status_code=200)
        response.json.return_value = [link('A'), link('B')]
        with mock.patch('integrations.outbound.ov.client.requests.get', return_value=response) as get:
            OVClient().get_active_contracts()

        self.assertEqual(get.call_args.args[0], 'https://ov.example.com/api/linked-contracts/')
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'Token secret')
        log = IntegrationRequestLog.objects.get(provider='ov')
        self.assertEqual((log.success, log.response_payload), (True, {'count': 2}))

    def test_client_error_raises_and_is_logged(self):
        response = mock.Mock(ok=False, status_code=500, text='boom')
        with mock.patch('integrations.outbound.ov.client.requests.get', return_value=response):
            with self.assertRaises(OVApiError):
                OVClient().get_active_contracts()
        self.assertFalse(IntegrationRequestLog.objects.get(provider='ov').success)

    def test_task_does_not_expose_error_detail(self):
        with mock.patch(
            'integrations.outbound.ov.tasks.sync_virtual_office_contracts', side_effect=OVApiError('detall intern'),
        ), self.assertLogs('integrations.outbound.ov.tasks', 'ERROR'):
            result = sync_virtual_office_contracts_task()
        self.assertEqual(result['status'], 'error')
        self.assertNotIn('detall intern', result['message'])

    def test_task_reports_partial_when_some_contracts_fail(self):
        stats = {'ov_contracts': 2, 'registered': 1, 'updated': 0, 'unregistered': 0, 'unchanged': 0,
                 'errors': 1, 'not_found_tokens': []}
        with mock.patch('integrations.outbound.ov.tasks.sync_virtual_office_contracts', return_value=stats):
            result = sync_virtual_office_contracts_task()
        self.assertEqual((result['status'], result['errors'], result['registered']), ('partial', 1, 1))

    def test_command_fails_when_some_contracts_fail(self):
        stats = {'ov_contracts': 1, 'registered': 0, 'updated': 0, 'unregistered': 0, 'unchanged': 0,
                 'errors': 1, 'not_found_tokens': []}
        with mock.patch(
            'integrations.management.commands.sync_virtual_office_contracts.sync_virtual_office_contracts',
            return_value=stats,
        ), self.assertRaises(CommandError):
            call_command('sync_virtual_office_contracts', stdout=io.StringIO())

    @override_settings(OV_SYNC_ENABLED=False)
    def test_task_skipped_when_disabled(self):
        with mock.patch('integrations.outbound.ov.tasks.sync_virtual_office_contracts') as sync:
            result = sync_virtual_office_contracts_task()
        self.assertEqual(result['status'], 'skipped')
        sync.assert_not_called()

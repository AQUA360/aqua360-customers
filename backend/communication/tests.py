"""Tests for the supply cut <-> communication process link and its guard policy."""

from django.test import TestCase
from rest_framework.serializers import ValidationError

from communication import process_policy
from communication.models import (
    CommunicationProcess,
    CommunicationProcessStatus,
    CommunicationUseType,
)
from communication.serializers.communication_process_serializer import (
    CommunicationProcessSaveSerializer,
)
from coredata.models import ConfigProject
from service.models import SupplyCut


class SupplyCutProcessTestCase(TestCase):
    """Base fixture.

    The statuses, config tokens and use types the application relies on are
    installation data rather than migrations, so the test database starts
    without them and each test class recreates what it needs.
    """

    PROCESS_STATUSES = (
        ('-2', 'Processant', 'purple'),
        ('1', 'Coms. creades', 'orange'),
        ('2', 'En curs', 'blue'),
        ('0', 'Pendent', 'yellow'),
        ('4', 'Esborrany', None),
        ('3', 'Finalitzat', 'green'),
        ('-1', 'Anulat', None),
    )

    STATUS_CONFIG = {
        'communication_process_status_processing_token': '-2',
        'communication_process_status_files_created_token': '1',
        'communication_process_status_current_token': '2',
        'communication_process_status_cancelled_token': '-1',
        'communication_process_status_completed_token': '3',
    }

    @classmethod
    def setUpTestData(cls):
        for token, name, color in cls.PROCESS_STATUSES:
            CommunicationProcessStatus.objects.get_or_create(
                token=token, defaults={'name': name, 'color': color}
            )
        for token, value in cls.STATUS_CONFIG.items():
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        CommunicationUseType.objects.get_or_create(
            name='Altres', defaults={'is_default': True}
        )

    def make_cut(self):
        return SupplyCut.objects.create()

    def make_process(self, cut, status_token, run_token=None, is_active=True):
        process = CommunicationProcess.objects.create(
            token='PROC-{}'.format(CommunicationProcess.objects.count() + 1),
            status=CommunicationProcessStatus.objects.get(token=status_token),
            run_token=run_token,
            is_active=is_active,
        )
        if cut is not None:
            process.supply_cuts.set([cut.id])
        return process


class SupplyCutPolicyTests(SupplyCutProcessTestCase):
    """The tier the shared policy assigns to a set of processes."""

    def test_no_processes_is_silent(self):
        self.assertEqual(process_policy.classify([]), process_policy.TIER_NONE)

    def test_blocking_tokens_come_from_config(self):
        self.assertEqual(
            process_policy.blocking_tokens(), {'-2', '1', '2'}
        )

    def test_blocking_tokens_fall_back_without_config(self):
        ConfigProject.objects.all().delete()
        self.assertEqual(
            process_policy.blocking_tokens(), set(process_policy.FALLBACK_BLOCKING_TOKENS)
        )

    def test_in_flight_process_blocks(self):
        for token in ('-2', '1', '2'):
            with self.subTest(status=token):
                process = self.make_process(None, token)
                self.assertEqual(process_policy.classify([process]), process_policy.TIER_BLOCK)

    def test_waiting_and_terminal_processes_warn(self):
        # 0 Pendent, 4 Esborrany, 3 Finalitzat, -1 Anulat: a new process is
        # legitimate but the user is told about the existing one first.
        for token in ('0', '4', '3', '-1'):
            with self.subTest(status=token):
                process = self.make_process(None, token)
                self.assertEqual(process_policy.classify([process]), process_policy.TIER_WARN)

    def test_blocking_wins_over_other_statuses(self):
        finished = self.make_process(None, '3')
        running = self.make_process(None, '-2')
        self.assertEqual(process_policy.classify([finished, running]), process_policy.TIER_BLOCK)

    def test_process_without_status_does_not_count(self):
        process = CommunicationProcess.objects.create(token='NO-STATUS')
        self.assertEqual(process_policy.classify([process]), process_policy.TIER_NONE)


class SupplyCutPolicyLookupTests(SupplyCutProcessTestCase):
    """Which processes the lookup returns for a set of cuts."""

    def test_inspect_is_none_for_a_clean_cut(self):
        cut = self.make_cut()
        tier, processes = process_policy.inspect([cut.id])
        self.assertEqual(tier, process_policy.TIER_NONE)
        self.assertEqual(processes, [])

    def test_process_is_found_through_the_link(self):
        cut = self.make_cut()
        self.make_process(cut, '0')
        tier, processes = process_policy.inspect([cut.id])
        self.assertEqual(tier, process_policy.TIER_WARN)
        self.assertEqual(len(processes), 1)

    def test_process_on_another_cut_is_ignored(self):
        cut = self.make_cut()
        other_cut = self.make_cut()
        self.make_process(other_cut, '-2')
        tier, _ = process_policy.inspect([cut.id])
        self.assertEqual(tier, process_policy.TIER_NONE)

    def test_soft_deleted_process_does_not_block(self):
        cut = self.make_cut()
        self.make_process(cut, '-2', is_active=False)
        tier, _ = process_policy.inspect([cut.id])
        self.assertEqual(tier, process_policy.TIER_NONE)

    def test_same_run_token_is_excluded(self):
        # Batched saves create one process per 500 recipients; the second batch
        # must not block itself.
        cut = self.make_cut()
        self.make_process(cut, '-2', run_token='run-a')
        tier, _ = process_policy.inspect([cut.id], exclude_run_token='run-a')
        self.assertEqual(tier, process_policy.TIER_NONE)

        tier, _ = process_policy.inspect([cut.id], exclude_run_token='run-b')
        self.assertEqual(tier, process_policy.TIER_BLOCK)

    def test_updated_process_does_not_block_itself(self):
        cut = self.make_cut()
        process = self.make_process(cut, '-2')
        tier, _ = process_policy.inspect([cut.id], exclude_process_id=process.id)
        self.assertEqual(tier, process_policy.TIER_NONE)

    def test_inspect_without_cuts_is_silent(self):
        tier, processes = process_policy.inspect([])
        self.assertEqual(tier, process_policy.TIER_NONE)
        self.assertEqual(processes, [])

    def test_lock_cuts_returns_only_existing_ids(self):
        cut = self.make_cut()
        with self.captureOnCommitCallbacks(execute=False):
            locked = process_policy.lock_cuts([cut.id, cut.id + 9999])
        self.assertEqual(locked, [cut.id])

    def test_lock_cuts_without_ids(self):
        self.assertEqual(process_policy.lock_cuts([]), [])


class SupplyCutProcessCreationTests(SupplyCutProcessTestCase):
    """The guard and the link as seen from the create serializer."""

    def save(self, **payload):
        serializer = CommunicationProcessSaveSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        # The create task is dispatched via transaction.on_commit; keep it from
        # running so these tests never touch the broker.
        with self.captureOnCommitCallbacks(execute=False):
            return serializer.save()

    def create_raw(self, **payload):
        """Call create() directly, bypassing field validation."""
        serializer = CommunicationProcessSaveSerializer()
        with self.captureOnCommitCallbacks(execute=False):
            return serializer.create(dict(payload))

    def test_cut_from_payload_is_linked(self):
        cut = self.make_cut()
        instance = self.save(supply_cuts=[cut.id])
        self.assertEqual(list(instance.supply_cuts.values_list('id', flat=True)), [cut.id])

    def test_cut_from_fixed_data_is_linked(self):
        # The cut menu and the supply cut management option both arrive as
        # fixed_data, so they need no extra payload.
        cut = self.make_cut()
        instance = self.save(fixed_data='supplycut', fixed_data_id=str(cut.id))
        self.assertEqual(list(instance.supply_cuts.values_list('id', flat=True)), [cut.id])

    def test_payload_and_fixed_data_are_unioned(self):
        cut_a = self.make_cut()
        cut_b = self.make_cut()
        instance = self.save(supply_cuts=[cut_a.id], fixed_data='supplycut', fixed_data_id=str(cut_b.id))
        self.assertEqual(
            sorted(instance.supply_cuts.values_list('id', flat=True)),
            sorted([cut_a.id, cut_b.id]),
        )

    def test_process_without_cuts_is_not_guarded(self):
        # Every non cut launch path keeps working untouched.
        instance = self.save()
        self.assertEqual(instance.supply_cuts.count(), 0)

    def test_in_flight_process_blocks_the_save(self):
        cut = self.make_cut()
        self.make_process(cut, '-2')
        with self.assertRaises(ValidationError) as raised:
            self.save(supply_cuts=[cut.id])
        self.assertEqual(raised.exception.detail.get('tier'), process_policy.TIER_BLOCK)
        self.assertEqual(CommunicationProcess.objects.filter(supply_cuts=cut).count(), 1)

    def test_same_run_token_does_not_block_itself(self):
        cut = self.make_cut()
        self.make_process(cut, '-2', run_token='run-a')
        instance = self.save(supply_cuts=[cut.id], run_token='run-a')
        self.assertEqual(instance.run_token, 'run-a')
        self.assertEqual(instance.supply_cuts.count(), 1)

    def test_different_run_token_is_blocked(self):
        cut = self.make_cut()
        self.make_process(cut, '-2', run_token='run-a')
        with self.assertRaises(ValidationError):
            self.save(supply_cuts=[cut.id], run_token='run-b')

    def test_soft_deleted_process_does_not_block_the_save(self):
        cut = self.make_cut()
        self.make_process(cut, '-2', is_active=False)
        instance = self.save(supply_cuts=[cut.id])
        self.assertEqual(instance.supply_cuts.count(), 1)

    def test_unrelated_cut_does_not_block(self):
        cut = self.make_cut()
        other_cut = self.make_cut()
        self.make_process(other_cut, '-2')
        instance = self.save(supply_cuts=[cut.id])
        self.assertEqual(instance.supply_cuts.count(), 1)

    def test_unknown_cut_id_is_rejected_by_validation(self):
        # Rejected before reaching create(), which still tolerates it
        # defensively.
        cut_id = SupplyCut.objects.create().id + 999999
        serializer = CommunicationProcessSaveSerializer(data={'supply_cuts': [cut_id]})
        self.assertFalse(serializer.is_valid())
        self.assertIn('supply_cuts', serializer.errors)

        instance = self.create_raw(supply_cuts=[cut_id])
        self.assertEqual(instance.supply_cuts.count(), 0)

    def test_rejected_save_leaves_no_partial_process(self):
        cut = self.make_cut()
        self.make_process(cut, '-2')
        before = CommunicationProcess.objects.count()
        with self.assertRaises(ValidationError):
            self.save(supply_cuts=[cut.id])
        self.assertEqual(CommunicationProcess.objects.count(), before)

    def test_use_type_and_status_are_assigned(self):
        cut = self.make_cut()
        instance = self.save(supply_cuts=[cut.id])
        self.assertIsNotNone(instance.status)
        self.assertEqual(instance.use_type, CommunicationUseType.objects.get(is_default=True))
"""Tests for the supply cut <-> communication process link and its guard policy."""

from django.test import TestCase
from rest_framework.serializers import ValidationError

from communication import process_policy
from communication.models import (
    Communication,
    CommunicationFile,
    CommunicationProcess,
    CommunicationProcessStatus,
    CommunicationUseType,
    MessageOrigin,
    MessageTemplate,
    MessageType,
)
from communication.serializers.communication_process_serializer import (
    CommunicationProcessSaveSerializer,
    CommunicationProcessSerializer,
    save_process_exclusions,
)
from communication.views.manage_communication_process_view import _CONFIG_CACHE, filter_by_supply_cut
from communication.utils.communication_service import get_com_values, refactor_text
from contract.models import Contract, ContractStatus
from coredata.models import Address, City, ConfigProject, Country, Person, PersonContact, Street, StreetNumber
from coredata.serializers import PersonCommunicationSerializer
from service.models import SupplyCut, SupplyCutCause, SupplyCutStatus, SupplyPoint


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

class DeleteCancelledTestCase(TestCase):
    """Esborrat lògic de comunicacions i processos cancel·lats."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        from communication.models import CommunicationStatus

        cls.user = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        cls.comm_cancelled = CommunicationStatus.objects.create(token='-1', name='Cancel·lada')
        cls.comm_pending = CommunicationStatus.objects.create(token='0', name='Pendent')
        cls.process_cancelled = CommunicationProcessStatus.objects.create(token='-1', name='Anul·lat')
        cls.process_pending = CommunicationProcessStatus.objects.create(token='0', name='Pendent')

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def make_comm(self, comm_status, process=None):
        from communication.models import Communication

        return Communication.objects.create(status=comm_status, process=process)

    def test_delete_cancelled_communication(self):
        from logger.models import LogCommunicationStatusChange

        comm = self.make_comm(self.comm_cancelled)
        response = self.client.post(f'/communication/communication/{comm.id}/delete-cancelled/')
        self.assertEqual(response.status_code, 200)
        comm.refresh_from_db()
        self.assertFalse(comm.is_active)
        self.assertTrue(LogCommunicationStatusChange.objects.filter(object=comm).exists())

    def test_delete_not_cancelled_communication_is_rejected(self):
        comm = self.make_comm(self.comm_pending)
        response = self.client.post(f'/communication/communication/{comm.id}/delete-cancelled/')
        self.assertEqual(response.status_code, 400)
        comm.refresh_from_db()
        self.assertTrue(comm.is_active)

    def test_delete_requires_delete_permission(self):
        from django.contrib.auth.models import Permission, User

        user = User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        user.user_permissions.add(
            Permission.objects.get(codename='view_communication'),
            Permission.objects.get(codename='add_communication'),
        )
        self.client.force_authenticate(user)
        comm = self.make_comm(self.comm_cancelled)
        response = self.client.post(f'/communication/communication/{comm.id}/delete-cancelled/')
        self.assertEqual(response.status_code, 403)
        comm.refresh_from_db()
        self.assertTrue(comm.is_active)

    def test_delete_cancelled_process_and_its_cancelled_communications(self):
        process = CommunicationProcess.objects.create(status=self.process_cancelled)
        cancelled = self.make_comm(self.comm_cancelled, process)
        pending = self.make_comm(self.comm_pending, process)

        response = self.client.post(f'/communication/communication-process/{process.id}/delete-cancelled/')
        self.assertEqual(response.status_code, 200)
        process.refresh_from_db()
        cancelled.refresh_from_db()
        pending.refresh_from_db()
        self.assertFalse(process.is_active)
        self.assertFalse(cancelled.is_active)
        self.assertTrue(pending.is_active)

    def test_delete_not_cancelled_process_is_rejected(self):
        process = CommunicationProcess.objects.create(status=self.process_pending)
        comm = self.make_comm(self.comm_cancelled, process)
        response = self.client.post(f'/communication/communication-process/{process.id}/delete-cancelled/')
        self.assertEqual(response.status_code, 400)
        process.refresh_from_db()
        comm.refresh_from_db()
        self.assertTrue(process.is_active)
        self.assertTrue(comm.is_active)

    def test_exclude_cancelled_filter(self):
        from communication.filters.communication_filter import CommunicationFilter
        from communication.filters.communication_process_filter import CommunicationProcessFilter
        from communication.models import Communication

        cancelled = self.make_comm(self.comm_cancelled)
        pending = self.make_comm(self.comm_pending)
        queryset = Communication.objects.all()

        ids = set(CommunicationFilter({'exclude_cancelled': 'true'}, queryset=queryset).qs.values_list('id', flat=True))
        self.assertEqual(ids, {pending.id})
        ids = set(CommunicationFilter({}, queryset=queryset).qs.values_list('id', flat=True))
        self.assertEqual(ids, {cancelled.id, pending.id})
        # Un filtre d'estat explícit mana per sobre d'exclude_cancelled.
        ids = set(CommunicationFilter(
            {'exclude_cancelled': 'true', 'status': str(self.comm_cancelled.id)}, queryset=queryset
        ).qs.values_list('id', flat=True))
        self.assertEqual(ids, {cancelled.id})

        cancelled_process = CommunicationProcess.objects.create(status=self.process_cancelled)
        pending_process = CommunicationProcess.objects.create(status=self.process_pending)
        ids = set(CommunicationProcessFilter(
            {'exclude_cancelled': 'true'}, queryset=CommunicationProcess.objects.all()
        ).qs.values_list('id', flat=True))
        self.assertEqual(ids, {pending_process.id})
        self.assertNotIn(cancelled_process.id, ids)


class SupplyCutMessageVariableTests(TestCase):
    """The `%supplycut.*` message variables.

    A process links cuts through an M2M, so every value is joined across the
    linked cuts: nothing is silently dropped and the single-cut case (the norm)
    renders without any extra marker.

    `affected_addresses` is GDPR-scoped: a recipient only ever sees the supply
    points they are the holder, owner or tenant of.
    """

    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(name='Espanya', iso_code='ES')
        cls.city = City.objects.create(name='Barcelona', token='BCN')
        cls.status = SupplyCutStatus.objects.create(token='1', name='Actiu')
        cls.cause = SupplyCutCause.objects.create(token='1', name='Impagament de Factures')
        # The contract post_save signal looks this up on every save.
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': '99'},
        )

    def make_address(self, street_name, number, door=None):
        street = Street.objects.create(name=street_name)
        street_number = StreetNumber.objects.create(street=street, number=number)
        return Address.objects.create(
            street=street,
            street_number=street_number,
            city=self.city,
            country=self.country,
            door=door,
        )

    def make_point(self, address=None):
        return SupplyPoint.objects.create(
            token='SP-{}'.format(SupplyPoint.objects.count() + 1),
            address=address,
        )

    def make_cut(self, token='CUT-1', date_start=None, date_end=None):
        return SupplyCut.objects.create(
            token=token,
            cause=self.cause,
            status=self.status,
            date_start=date_start,
            date_end=date_end,
        )

    def make_communication(self, cuts=()):
        process = CommunicationProcess.objects.create(token='PROC-1')
        process.supply_cuts.set([cut.id for cut in cuts])
        return Communication.objects.create(process=process)

    def make_person(self, name):
        return Person.objects.create(name=name)

    def make_contract(self, holder=None, owner=None, tenant=None, points=(), default=None):
        contract = Contract.objects.create(
            holder=holder, owner=owner, tenant=tenant, supply_point_default=default,
        )
        contract.supply_points.set(points)
        return contract

    def values(self, communication, person=None):
        return get_com_values({'id': person.id} if person else None, communication, None)

    def test_single_cut_renders_without_a_marker(self):
        # The norm is one cut per process: a bare value, not a bullet list.
        cut = self.make_cut()
        communication = self.make_communication([cut])
        self.assertEqual(self.values(communication)['supplycut.cause_name'], 'Impagament de Factures')

    def test_token_status_and_dates_are_exposed(self):
        from datetime import datetime
        from django.utils import timezone
        cut = self.make_cut(
            token='CUT-42',
            date_start=timezone.make_aware(datetime(2026, 10, 5, 8, 0)),
            date_end=timezone.make_aware(datetime(2026, 10, 7, 18, 0)),
        )
        values = self.values(self.make_communication([cut]))
        self.assertEqual(values['supplycut.token'], 'CUT-42')
        self.assertEqual(values['supplycut.status'], 'Actiu')
        self.assertEqual(values['supplycut.date_start'], '05/10/2026')
        self.assertEqual(values['supplycut.date_end'], '07/10/2026')

    def test_affected_addresses_gives_the_full_address(self):
        # For a non-payment cut the exact street, number and door are what make
        # the notice legally actionable.
        cut = self.make_cut()
        point = self.make_point(self.make_address('Carrer Mallorca', '10', door='2r'))
        cut.supply_points.add(point)
        person = self.make_person('Abonat')
        self.make_contract(holder=person, points=[point])
        address = self.values(self.make_communication([cut]), person)['supplycut.affected_addresses']
        self.assertIn('Carrer Mallorca', address)
        self.assertIn('10', address)
        self.assertIn('2r', address)

    def test_addresses_are_bulleted_when_a_cut_has_several_points(self):
        cut = self.make_cut()
        first = self.make_point(self.make_address('Carrer Mallorca', '10'))
        second = self.make_point(self.make_address('Carrer Mallorca', '12'))
        cut.supply_points.add(first, second)
        person = self.make_person('Abonat')
        self.make_contract(holder=person, points=[first, second])
        value = self.values(self.make_communication([cut]), person)['supplycut.affected_addresses']
        self.assertEqual(value.count('\n- '), 1)
        self.assertTrue(value.startswith('Carrer Mallorca, 10'))

    def test_multiple_cuts_are_joined_instead_of_dropping_one(self):
        # The relation is M2M even though the business is 1-to-1: if a second
        # cut ever lands, the letter must still mention both.
        first = self.make_cut(token='CUT-1')
        second = self.make_cut(token='CUT-2')
        values = self.values(self.make_communication([first, second]))
        self.assertEqual(values['supplycut.token'], 'CUT-1\n- CUT-2')

    def test_cut_without_supply_points_yields_empty_string_not_a_list(self):
        # Several pre-existing entries return [], which renders as a literal
        # "[]" in the customer's letter.
        cut = self.make_cut()
        self.assertEqual(self.values(self.make_communication([cut]))['supplycut.affected_addresses'], '')

    def test_no_linked_cut_yields_empty_strings(self):
        values = self.values(self.make_communication())
        self.assertEqual(values['supplycut.token'], '')
        self.assertEqual(values['supplycut.cause_name'], '')

    def test_communication_without_process_does_not_raise(self):
        # `get_com_values` runs for every communication, including ones created
        # outside a process.
        values = self.values(Communication.objects.create())
        self.assertEqual(values['supplycut.token'], '')

    def test_missing_dates_and_exec_dates_stay_empty(self):
        values = self.values(self.make_communication([self.make_cut()]))
        for key in ('supplycut.date_start', 'supplycut.date_end',
                    'supplycut.exec_start', 'supplycut.exec_end'):
            self.assertEqual(values[key], '')

    def test_start_and_end_times_are_in_local_time(self):
        # A la BD les dates són UTC: un tall a les 00:30 (hora local) no pot sortir
        # amb la data del dia abans ni amb l'hora UTC.
        from datetime import datetime, timezone as dt_timezone
        cut = self.make_cut(
            date_start=datetime(2026, 10, 4, 22, 30, tzinfo=dt_timezone.utc),
            date_end=datetime(2026, 10, 5, 12, 0, tzinfo=dt_timezone.utc),
        )
        values = self.values(self.make_communication([cut]))
        self.assertEqual(values['supplycut.date_start'], '05/10/2026')
        self.assertEqual(values['supplycut.time_start'], '00:30')
        self.assertEqual(values['supplycut.time_end'], '14:00')
        body = refactor_text('De %supplycut.time_start a %supplycut.time_end', values)
        self.assertEqual(body, 'De 00:30 a 14:00')

    def test_tokens_are_substituted_in_the_body(self):
        cut = self.make_cut(token='CUT-9')
        communication = self.make_communication([cut])
        body = refactor_text('Tall %supplycut.cause_name (%supplycut.token)', self.values(communication))
        self.assertEqual(body, 'Tall Impagament de Factures (CUT-9)')

    # --- GDPR: recipient-scoped addresses ---------------------------------

    def test_neighbour_address_is_never_included(self):
        # A cut can span several supply points, but each recipient only ever
        # sees their own address, never the neighbour's.
        cut = self.make_cut()
        mine = self.make_point(self.make_address('Carrer Mallorca', '10'))
        neighbour = self.make_point(self.make_address('Carrer Balmes', '20'))
        cut.supply_points.add(mine, neighbour)
        me = self.make_person('Abonat')
        other = self.make_person('Veï')
        self.make_contract(holder=me, points=[mine])
        self.make_contract(holder=other, points=[neighbour])
        communication = self.make_communication([cut])

        mine_address = self.values(communication, me)['supplycut.affected_addresses']
        self.assertIn('Carrer Mallorca', mine_address)
        self.assertNotIn('Carrer Balmes', mine_address)

        other_address = self.values(communication, other)['supplycut.affected_addresses']
        self.assertIn('Carrer Balmes', other_address)
        self.assertNotIn('Carrer Mallorca', other_address)

    def test_no_person_fails_safe_to_empty_addresses(self):
        # With no person the list is empty rather than over-disclosing.
        cut = self.make_cut()
        point = self.make_point(self.make_address('Carrer Mallorca', '10'))
        cut.supply_points.add(point)
        person = self.make_person('Abonat')
        self.make_contract(holder=person, points=[point])
        values = self.values(self.make_communication([cut]), None)
        self.assertEqual(values['supplycut.affected_addresses'], '')
        # Non-address values are unaffected by the GDPR filter.
        self.assertEqual(values['supplycut.cause_name'], 'Impagament de Factures')

    def test_owner_and_tenant_also_see_their_address(self):
        # Not only the holder: the owner and the tenant of the contract see
        # the address too.
        cut = self.make_cut()
        point = self.make_point(self.make_address('Carrer Mallorca', '10'))
        cut.supply_points.add(point)
        owner = self.make_person('Propietari')
        tenant = self.make_person('Llogater')
        self.make_contract(owner=owner, tenant=tenant, points=[point])
        communication = self.make_communication([cut])

        self.assertIn('Carrer Mallorca', self.values(communication, owner)['supplycut.affected_addresses'])
        self.assertIn('Carrer Mallorca', self.values(communication, tenant)['supplycut.affected_addresses'])

    def test_holder_and_owner_on_same_contract_does_not_duplicate(self):
        # A person can be both the holder and the owner of the same contract:
        # the `.distinct()` on the owned-ids subquery keeps the address from
        # being listed twice.
        cut = self.make_cut()
        point = self.make_point(self.make_address('Carrer Mallorca', '10'))
        cut.supply_points.add(point)
        person = self.make_person('Abonat')
        self.make_contract(holder=person, owner=person, points=[point])
        value = self.values(self.make_communication([cut]), person)['supplycut.affected_addresses']
        # `Address.__str__` renders "street, number, city".
        self.assertEqual(value, 'Carrer Mallorca, 10, Barcelona')

    def test_default_contract_supply_point_is_included(self):
        # The supply point can be linked through the contract's default FK
        # instead of the M2M and must still be recognised.
        cut = self.make_cut()
        point = self.make_point(self.make_address('Carrer Mallorca', '10'))
        cut.supply_points.add(point)
        person = self.make_person('Abonat')
        self.make_contract(holder=person, default=point)
        value = self.values(self.make_communication([cut]), person)['supplycut.affected_addresses']
        self.assertIn('Carrer Mallorca', value)

    def test_gdpr_filtered_addresses_are_substituted_in_the_body(self):
        # End-to-end: the rendered body carries the recipient's own address and
        # never the neighbour's.
        cut = self.make_cut()
        mine = self.make_point(self.make_address('Carrer Mallorca', '10'))
        neighbour = self.make_point(self.make_address('Carrer Balmes', '20'))
        cut.supply_points.add(mine, neighbour)
        me = self.make_person('Abonat')
        other = self.make_person('Veï')
        self.make_contract(holder=me, points=[mine])
        self.make_contract(holder=other, points=[neighbour])
        communication = self.make_communication([cut])

        body = refactor_text(
            'Adreces afectades: %supplycut.affected_addresses',
            self.values(communication, me),
        )
        self.assertIn('Carrer Mallorca', body)
        self.assertNotIn('Carrer Balmes', body)


class CommunicationProcessComFilesOrderTests(TestCase):
    """Els documents a descarregar surten agrupats per comunicació (persona): primer la carta,
    després el document de comunicació i la resta, encara que es generin després."""

    def setUp(self):
        from documentmanager.models import Document

        ConfigProject.objects.update_or_create(token='message_type_letter_token', defaults={'value': 'postal'})
        ConfigProject.objects.update_or_create(token='message_type_email_token', defaults={'value': 'email'})
        self.process = CommunicationProcess.objects.create(token='PROC-ORDER')
        comms = [
            Communication.objects.create(process=self.process, type_tokens='postal')
            for _ in range(2)
        ]

        def document(name, entity='FACTURES'):
            return Document.objects.create(entity=entity, entity_id=1, service='hdd', document_name=name)

        # Com al procés real: la carta es crea primer sense fitxer, les factures ja existeixen
        # i els pagaments i el PDF de la carta es generen després
        letters = [CommunicationFile.objects.create(communication=c, is_letter=True) for c in comms]
        invoices = [document(f'factura-{i}') for i in range(2)]
        payments = [document(f'pagament-{i}') for i in range(2)]
        for comm, invoice, payment in zip(comms, invoices, payments):
            CommunicationFile.objects.create(communication=comm, file=invoice)
            CommunicationFile.objects.create(communication=comm, file=payment)
        # El document del pas d'impagats (fa de carta) es genera després de factures i pagaments
        claim_docs = [document(f'avis-{i}', entity='COMUNICACIO') for i in range(2)]
        for comm, claim_doc in zip(comms, claim_docs):
            CommunicationFile.objects.create(communication=comm, file=claim_doc)
        letter_docs = [document(f'carta-{i}', entity='COMUNICACIO') for i in range(2)]
        for letter, letter_doc in zip(letters, letter_docs):
            letter.file = letter_doc
            letter.save()

        self.expected = [
            letter_docs[0].id, claim_docs[0].id, invoices[0].id, payments[0].id,
            letter_docs[1].id, claim_docs[1].id, invoices[1].id, payments[1].id,
        ]

    def test_com_files_grouped_by_communication_with_letter_first(self):
        com_files = CommunicationProcessSerializer().get_com_files(self.process)
        self.assertEqual([f['id'] for f in com_files], self.expected)


class ClaimDocumentsWithGroupedPaymentsTests(TestCase):
    """Amb «Agrupar pagaments» les factures també s'adjunten a la comunicació,
    però no els rebuts individuals (el rebut és el document agrupat)."""

    def setUp(self):
        from billing.models import Invoice, JoinedPayment, Payment
        from claimrequest.models import (
            ClaimRequest, ClaimRequestPayment, ClaimRequestStep, ClaimRequestStepTemplate,
            ClaimRequestTemplate,
        )
        from documentmanager.models import Document

        ConfigProject.objects.update_or_create(token='message_type_email_token', defaults={'value': 'email'})
        # Configuració que demanen els senyals de contracte, factura i pagament
        for token in ('contract_terminated_status', 'invoice_status_cancelled_token'):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': '-1'})
        self.process = CommunicationProcess.objects.create(token='PROC-CLAIM')
        step_template = ClaimRequestStepTemplate.objects.create(
            template=ClaimRequestTemplate.objects.create(), group_payments=True,
        )
        self.claim = ClaimRequest.objects.create()
        step = ClaimRequestStep.objects.create(
            claim_request=self.claim, step_template=step_template, communication_process=self.process,
        )
        self.claim.current_step = step
        self.claim.save()

        self.contract = Contract.objects.create(token='CLAIM-CT')
        self.comm = Communication.objects.create(process=self.process, type_tokens='letter')
        self.comm.contracts.add(self.contract)

        self.invoice_docs = []
        joined = JoinedPayment.objects.create(contract=self.contract, claim_request=self.claim)
        for i in range(2):
            doc = Document.objects.create(entity_id=1, service='hdd', document_name=f'factura-{i}')
            invoice = Invoice.objects.create(invoice_file=doc)
            payment = Payment.objects.create(invoice=invoice)
            ClaimRequestPayment.objects.create(claim_request=self.claim, contract=self.contract, payment=payment)
            joined.payments.add(payment)
            self.invoice_docs.append(doc)
        self.claim_doc = Document.objects.create(entity_id=1, service='hdd', document_name='reclamacio')

    def test_grouped_payments_attach_invoices_and_grouped_claim_document(self):
        from unittest.mock import patch

        from communication.tasks import generate_claim_document_pdf_task

        def claim_step_file(claim_request, contract, comm, *args):
            return CommunicationFile(communication=comm, file=self.claim_doc)

        with patch('communication.tasks._create_claim_step_communication_file', side_effect=claim_step_file), \
                patch('communication.tasks.generate_report_payment_pdf') as payment_pdf:
            result = generate_claim_document_pdf_task([self.comm.id], self.process.id, claim_id=self.claim.id)

        self.assertEqual(result['status'], 'success')
        payment_pdf.assert_not_called()
        files = list(self.comm.files.order_by('id').values_list('file_id', flat=True))
        self.assertEqual(files, [d.id for d in self.invoice_docs] + [self.claim_doc.id])
        self.assertEqual(self.comm.invoices.count(), 2)

    def test_without_extra_docs_only_claim_document_is_attached(self):
        from unittest.mock import patch

        from communication.tasks import generate_claim_document_pdf_task

        ConfigProject.objects.update_or_create(token='attach_extra_docs_in_claims', defaults={'value': 'false'})

        def claim_step_file(claim_request, contract, comm, *args):
            return CommunicationFile(communication=comm, file=self.claim_doc)

        with patch('communication.tasks._create_claim_step_communication_file', side_effect=claim_step_file), \
                patch('communication.tasks.generate_report_payment_pdf') as payment_pdf:
            result = generate_claim_document_pdf_task([self.comm.id], self.process.id, claim_id=self.claim.id)

        self.assertEqual(result['status'], 'success')
        payment_pdf.assert_not_called()
        files = list(self.comm.files.order_by('id').values_list('file_id', flat=True))
        self.assertEqual(files, [self.claim_doc.id])
        # Les factures es vinculen igualment per resoldre les variables %invoice.*
        self.assertEqual(self.comm.invoices.count(), 2)


class SupplyCutRecipientChannelTests(TestCase):
    """Destinataris d'un tall segons els canals triats.

    Un fix no pot rebre SMS: qui només té un fix i cap altre canal queda a la
    llista de descartats amb el motiu, i qui té un altre canal hi continua però
    amb l'avís del canal que no li arriba.
    """

    @classmethod
    def setUpTestData(cls):
        for token, value in {
            'contract_terminated_status': '99',
            'contract_active_token': '1',
            'message_type_email_token': 'email',
            'message_type_letter_token': 'letter',
            'message_type_sms_token': 'sms',
        }.items():
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        cls.active = ContractStatus.objects.create(token='1', name='Actiu')
        cls.cut = SupplyCut.objects.create(token='CUT-1')
        cls.point = SupplyPoint.objects.create(token='SP-1')
        cls.cut.supply_points.add(cls.point)

    def setUp(self):
        # get_config_token guarda els valors en un cache de mòdul.
        _CONFIG_CACHE.clear()

    def make_holder(self, name, phone=None, email=None):
        person = Person.objects.create(name=name)
        contact = PersonContact.objects.create(person=person, phone=phone, email=email)
        contract = Contract.objects.create(holder=person, status=self.active)
        contract.supply_points.add(self.point)
        if phone:
            contract.person_contact_sms.add(contact)
        if email:
            contract.person_contact_email = contact
            contract.save()
        return person

    def search(self, message_types):
        excluded = []
        persons = filter_by_supply_cut(
            {'supply_cuts': [{'id': self.cut.id}], 'message_types': message_types},
            [],
            excluded=excluded,
        )
        return {p['id']: p for p in persons}, {e['id']: e for e in excluded}

    def test_landline_only_is_excluded_with_the_reason(self):
        landline = self.make_holder('Fix', phone='972123456')
        no_phone = self.make_holder('Sense telèfon')
        mobile = self.make_holder('Mòbil', phone='612345678')

        persons, excluded = self.search(['sms'])

        self.assertEqual(set(persons), {mobile.id})
        self.assertTrue(persons[mobile.id]['has_sms'])
        self.assertEqual(excluded[landline.id]['reasons'], ['sms_landline'])
        self.assertEqual(excluded[no_phone.id]['reasons'], ['sms_no_phone'])
        self.assertEqual(excluded[landline.id]['person_type'], 'holder')

    def test_landline_with_email_keeps_email_as_alternative(self):
        person = self.make_holder('Fix amb correu', phone='972123456', email='abonat@example.com')

        persons, excluded = self.search(['sms', 'email'])

        self.assertNotIn(person.id, excluded)
        self.assertFalse(persons[person.id]['has_sms'])
        self.assertEqual(persons[person.id]['unavailable_channels'], ['sms_landline'])
        # Tots els canals, no només els triats: el pas 6 ho necessita per als canals del pas 4.
        self.assertEqual(
            sorted(persons[person.id]['missing_channels']),
            ['electronic_inv_missing', 'letter_missing', 'sms_landline'],
        )
        self.assertEqual(persons[person.id]['contracts'][0]['communication_type'], 'DIGITAL')

    def test_contract_email_of_the_holder_does_not_reach_the_tenant(self):
        # El correu del contracte és del titular: l'arrendatari no el rep (com en
        # crear la comunicació), així que amb només correu queda descartat.
        holder = self.make_holder('Titular', email='titular@example.com')
        contract = Contract.objects.get(holder=holder)
        tenant = Person.objects.create(name='Arrendatari')
        contract.tenant = tenant
        contract.save()

        persons, excluded = self.search(['email'])

        self.assertIn(holder.id, persons)
        self.assertEqual(excluded[tenant.id]['reasons'], ['email_missing'])
        self.assertEqual(excluded[tenant.id]['person_type'], 'tenant')

    def test_sms_phone_only_returns_mobiles(self):
        person = self.make_holder('Dos telèfons', phone='972123456')
        contract = Contract.objects.get(holder=person)
        mobile = PersonContact.objects.create(person=person, phone='+34 612 345 678')
        contract.person_contact_sms.add(mobile)
        person.contract_ids = [contract.id]
        person.invoice_ids = []
        person.reading_ids = []
        self.assertEqual(PersonCommunicationSerializer(person).data['sms_phone'], '+34 612 345 678')

    def test_exclusions_are_saved_on_the_process(self):
        person = self.make_holder('Fix', phone='972123456')
        contract = Contract.objects.get(holder=person)
        process = CommunicationProcess.objects.create(token='PROC-1')

        save_process_exclusions(process, [
            {'id': person.id, 'person_type': 'holder', 'contracts': [contract.id], 'reasons': ['sms_landline']},
            {'id': 999999, 'reasons': ['manual']},  # persona inexistent: s'ignora
        ])

        exclusion = process.exclusions.get()
        self.assertEqual(exclusion.person, person)
        self.assertEqual(exclusion.reasons, ['sms_landline'])
        self.assertEqual(list(exclusion.contracts.all()), [contract])
        data = CommunicationProcessSerializer(process).data
        self.assertEqual(data['exclusions'][0]['reasons'], ['sms_landline'])


class SupplyCutTemplateMigrationTests(TestCase):
    """La migració 0034 crea l'origen i la plantilla d'avís de tall a les instal·lacions existents."""

    def run_migration(self):
        from importlib import import_module
        from django.apps import apps
        migration = import_module('communication.migrations.0034_supplycut_origin_and_template')
        migration.create_supplycut_origin_and_template(apps, None)
        return migration

    def test_creates_origin_and_one_template_per_existing_channel(self):
        MessageOrigin.objects.create(token='other', name='Altres', position=4)
        # Un origen sense posició no pot fer que el nou vagi el primer (NULL primer a Postgres).
        MessageOrigin.objects.create(token='custom', name='Personalitzat', position=None)
        for config_token, value in (('message_type_email_token', 'email'), ('message_type_letter_token', 'letter'),
                                    ('message_type_sms_token', 'sms')):
            ConfigProject.objects.get_or_create(token=config_token, defaults={'value': value})
        MessageType.objects.create(token='email', name='Correu')
        MessageType.objects.create(token='letter', name='Carta')
        # Sense tipus 'sms' a la BD: no se'n crea la plantilla d'SMS.

        from django.test import override_settings
        with override_settings(LANGUAGE='ca'):
            self.run_migration()
            self.run_migration()  # idempotent

        origin = MessageOrigin.objects.get(token='supplycut')
        self.assertEqual(origin.position, 5)
        template = MessageTemplate.objects.get(token='supplycut_notice')
        self.assertEqual(template.origin, origin)
        self.assertEqual(sorted(template.templates.values_list('type__token', flat=True)), ['email', 'letter'])
        self.assertIn('%supplycut.affected_addresses', template.templates.get(type__token='email').body)
        self.assertEqual(origin.name, 'Tall de subministrament')

    def test_template_follows_the_installation_language(self):
        from django.test import override_settings
        MessageOrigin.objects.create(token='other', name='Otros', position=4)
        ConfigProject.objects.get_or_create(token='message_type_email_token', defaults={'value': 'email'})
        MessageType.objects.create(token='email', name='Correo')

        with override_settings(LANGUAGE='es'):
            self.run_migration()

        self.assertEqual(MessageOrigin.objects.get(token='supplycut').name, 'Corte de suministro')
        template = MessageTemplate.objects.get(token='supplycut_notice')
        self.assertEqual(template.name, 'Aviso de corte de suministro')
        self.assertTrue(template.templates.get().body.startswith('Estimado/a %person.name'))

    def test_fresh_database_is_left_to_initial_data(self):
        self.run_migration()
        self.assertFalse(MessageOrigin.objects.exists())
        self.assertFalse(MessageTemplate.objects.exists())


class SmsSendingTests(TestCase):
    """Enviament de l'SMS de les comunicacions via Broadcaster."""

    @classmethod
    def setUpTestData(cls):
        from communication.models import CommunicationStatus, Message

        cls.pending = CommunicationStatus.objects.create(token='0', name='Pendent', is_default=True)
        cls.sent = CommunicationStatus.objects.create(token='2', name='Enviada')
        cls.rejected = CommunicationStatus.objects.create(token='-2', name='Retornada')
        for token, value in (
            ('communication_status_sent_token', '2'),
            ('communication_status_rejected_token', '-2'),
            ('message_type_sms_token', 'sms'),
        ):
            # Algunes migracions ja en creen.
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.sms_type = MessageType.objects.create(token='sms', name='SMS')
        cls.message = Message.objects.create(type=cls.sms_type, body='**BOLD**Avís**BOLD** del %date.today')

    def make_comm(self, type_tokens='sms'):
        comm = Communication.objects.create(
            status=self.pending, used_phones='612345678,+34 698765432', type_tokens=type_tokens,
        )
        comm.messages.add(self.message)
        return comm

    def handle(self, comm):
        from communication.utils.communication_service import handle_communication

        handle_communication(comm, comm.type_tokens.split(','))
        comm.refresh_from_db()

    def make_email_comm(self, type_tokens='email,sms'):
        from communication.models import Message
        from service.models import CompanyConfig, CompanyConfigEmail

        config = CompanyConfig.objects.create()
        config_email = CompanyConfigEmail.objects.create(
            company_config=config, mail_send_user='sender@example.com',
            mail_send_mail='sender@example.com', is_default=True,
        )
        email_type = MessageType.objects.create(token='email', name='Email')
        ConfigProject.objects.update_or_create(
            token='message_type_email_token', defaults={'value': 'email'},
        )
        comm = self.make_comm(type_tokens)
        comm.company_config = config
        comm.company_config_email = config_email
        comm.used_email = 'recipient@example.com'
        comm.save()
        comm.messages.add(Message.objects.create(type=email_type, subject='Avís', body='Avís de tall'))
        return comm

    def test_get_sms_text(self):
        from communication.utils.communication_service import get_sms_text

        self.assertEqual(
            get_sms_text('**BOLD**Tall**BOLD** a  %supplycut.affected_addresses', {'supplycut.affected_addresses': 'carrer'}),
            'Tall a carrer',
        )

    def test_sms_sent(self):
        from unittest.mock import patch

        comm = self.make_comm()
        with patch('integrations.outbound.broadcaster.client.BroadcasterClient.send_sms') as send_sms:
            self.handle(comm)

        kwargs = send_sms.call_args.kwargs
        self.assertEqual(kwargs['phones'], ['612345678', '+34 698765432'])
        self.assertTrue(kwargs['text'].startswith('Avís del '))
        self.assertNotIn('**', kwargs['text'])
        self.assertEqual(comm.status, self.sent)
        self.assertIsNotNone(comm.sent_at)
        self.assertIsNotNone(comm.sms_sent_at)

    def test_sms_error_rejects_communication(self):
        from unittest.mock import patch
        from integrations.outbound.broadcaster.exceptions import BroadcasterError

        comm = self.make_comm()
        with patch('integrations.outbound.broadcaster.client.BroadcasterClient.send_sms', side_effect=BroadcasterError('HTTP 403')):
            self.handle(comm)

        self.assertEqual(comm.status, self.rejected)
        self.assertIn('HTTP 403', comm.rejection_reason)
        self.assertIsNone(comm.sms_sent_at)

    def test_retry_after_email_error_does_not_resend_sms(self):
        from unittest.mock import patch

        def email_fails(comm):
            Communication.objects.filter(id=comm.id).update(status=self.rejected, rejection_reason='Error sending email')

        def email_ok(comm):
            Communication.objects.filter(id=comm.id).update(status=self.sent)

        comm = self.make_comm('email,sms')
        with patch('integrations.outbound.broadcaster.client.BroadcasterClient.send_sms') as send_sms, \
                patch('communication.utils.communication_service.send_electronic_mail', side_effect=email_fails):
            self.handle(comm)
        self.assertEqual(send_sms.call_count, 1)
        self.assertEqual(comm.status, self.rejected)
        self.assertEqual(comm.rejection_reason, 'Error sending email')

        with patch('integrations.outbound.broadcaster.client.BroadcasterClient.send_sms') as send_sms, \
                patch('communication.utils.communication_service.send_electronic_mail', side_effect=email_ok):
            self.handle(comm)
        send_sms.assert_not_called()
        self.assertEqual(comm.status, self.sent)

    def test_retry_after_sms_error_does_not_resend_email(self):
        from unittest.mock import patch
        from integrations.outbound.broadcaster.exceptions import BroadcasterError

        comm = self.make_email_comm()
        with patch('integrations.outbound.broadcaster.client.BroadcasterClient.send_sms',
                   side_effect=[BroadcasterError('HTTP 500'), BroadcasterError('HTTP 500'), None]) as send_sms, \
                patch('communication.utils.communication_service._send_via_smtp') as send_email:
            for _ in range(2):
                self.handle(comm)
                self.assertEqual(comm.status, self.rejected)
                self.assertIsNotNone(comm.sent_at)
                self.assertIsNone(comm.sms_sent_at)
                self.assertEqual(send_email.call_count, 1)
            self.handle(comm)

        self.assertEqual(send_sms.call_count, 3)
        send_email.assert_called_once()
        self.assertEqual(comm.status, self.sent)
        self.assertIsNotNone(comm.sms_sent_at)

    def test_retry_sends_failed_email_without_resending_sms(self):
        from unittest.mock import patch

        comm = self.make_email_comm()
        with patch('integrations.outbound.broadcaster.client.BroadcasterClient.send_sms') as send_sms, \
                patch('communication.utils.communication_service._send_via_smtp',
                      side_effect=[Exception('SMTP unavailable'), None]) as send_email:
            self.handle(comm)
            self.assertEqual(comm.status, self.rejected)
            self.assertIsNone(comm.sent_at)
            self.assertIsNotNone(comm.sms_sent_at)
            self.handle(comm)

        send_sms.assert_called_once()
        self.assertEqual(send_email.call_count, 2)
        self.assertEqual(comm.status, self.sent)
        self.assertIsNotNone(comm.sent_at)

    def test_email_timestamp_is_rechecked_before_sending(self):
        from unittest.mock import patch
        from django.utils import timezone

        comm = self.make_email_comm('email')
        for status in (self.pending, self.rejected):
            with self.subTest(status=status.token):
                comm.sent_at = None
                sent_at = timezone.now()
                Communication.objects.filter(id=comm.id).update(status=status, sent_at=sent_at)
                with patch('communication.utils.communication_service.get_all_documents') as get_documents, \
                        patch('communication.utils.communication_service._send_via_smtp') as send_email:
                    self.handle(comm)
                get_documents.assert_not_called()
                send_email.assert_not_called()
                self.assertEqual(comm.status, status)
                self.assertEqual(comm.sent_at, sent_at)

    def test_email_and_sms_errors_keep_both_reasons(self):
        from unittest.mock import patch
        from integrations.outbound.broadcaster.exceptions import BroadcasterError

        def email_fails(comm):
            Communication.objects.filter(id=comm.id).update(status=self.rejected, rejection_reason='Error sending email')

        comm = self.make_comm('email,sms')
        with patch('integrations.outbound.broadcaster.client.BroadcasterClient.send_sms', side_effect=BroadcasterError('HTTP 500')), \
                patch('communication.utils.communication_service.send_electronic_mail', side_effect=email_fails):
            self.handle(comm)

        self.assertEqual(comm.status, self.rejected)
        self.assertIn('Error sending email', comm.rejection_reason)
        self.assertIn('HTTP 500', comm.rejection_reason)

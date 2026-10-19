"""Tests per la planificació massiva de talls (bulk-plan preview + create)."""
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from contract.models import Contract, ContractStatus
from coredata.models import Address, City, ConfigProject, Country, Person, Street, StreetNumber
from service.models import (
    SupplyCut,
    SupplyCutCause,
    SupplyCutStatus,
    SupplyPoint,
)
from service.utils import supply_cut_bulk_planner as bulk_planner
from service.views.supply_cut_view import SupplyCutViewSet


class BulkPlannerFixtureMixin:
    """Shared fixtures: streets, addresses, points, a cause and a status."""

    @classmethod
    def make_address(cls, street, city, number='1'):
        street_number = StreetNumber.objects.create(street=street, number=number)
        return Address.objects.create(
            street=street,
            street_number=street_number,
            city=city,
            country=cls.country,
        )

    @classmethod
    def make_point(cls, address=None, token=None, is_active=True):
        return SupplyPoint.objects.create(
            token=token or 'SP-{}'.format(SupplyPoint.objects.count() + 1),
            address=address,
            is_active=is_active,
        )

    @classmethod
    def make_person(cls, token, vulnerability_level=0, name='Persona', surname='Test'):
        """Create a test person with the requested vulnerability level."""
        return Person.objects.create(
            token=token, name=name, surname=surname,
            vulnerability_level=vulnerability_level,
        )

    @classmethod
    def make_contract(cls, token, supply_point=None, holder=None, tenant=None, owner=None, is_active=True):
        """Create a test contract with the supplied people and supply point links."""
        contract = Contract.objects.create(
            token=token, supply_point_default=supply_point,
            holder=holder, tenant=tenant, owner=owner, is_active=is_active,
        )
        if supply_point is not None:
            contract.supply_points.set([supply_point])
        return contract


class TestSupplyCutBulkPlannerService(BulkPlannerFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(name='Espanya', iso_code='ES')
        cls.city = City.objects.create(name='Barcelona', token='BCN')
        # The status/cause catalogs are seeded by migrations: reuse, never duplicate.
        cls.cause, _ = SupplyCutCause.objects.get_or_create(token='1', defaults={'name': 'Obres'})
        cls.status_planned, _ = SupplyCutStatus.objects.get_or_create(token='0', defaults={'name': 'Planificat'})
        cls.status_active, _ = SupplyCutStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.status_finished, _ = SupplyCutStatus.objects.get_or_create(token='2', defaults={'name': 'Acabat'})
        cls.status_cancelled, _ = SupplyCutStatus.objects.get_or_create(token='3', defaults={'name': 'Cancel·lat'})
        # The contract post_save signal looks this up on every save.
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': '99'},
        )

        # Generic test streets (never real client data).
        cls.street_mallorca = Street.objects.create(name='Mallorca', city=cls.city)
        cls.street_mallorca_2 = Street.objects.create(name='Mallorca', city=cls.city)
        cls.street_girona = Street.objects.create(name='Girona', city=cls.city)
        cls.street_empty = Street.objects.create(name='Sense adreces', city=cls.city)

        addr_a = cls.make_address(cls.street_mallorca, cls.city, number='10')
        addr_b = cls.make_address(cls.street_mallorca, cls.city, number='12')
        addr_c = cls.make_address(cls.street_mallorca_2, cls.city, number='3')
        addr_d = cls.make_address(cls.street_girona, cls.city, number='7')

        cls.sp_a = cls.make_point(addr_a, token='SP-A')
        cls.sp_b = cls.make_point(addr_b, token='SP-B')
        cls.sp_c = cls.make_point(addr_c, token='SP-C')
        cls.sp_d = cls.make_point(addr_d, token='SP-D')
        cls.sp_inactive_on_mallorca = cls.make_point(
            cls.make_address(cls.street_mallorca, cls.city, number='99'),
            token='SP-INACTIVE',
            is_active=False,
        )

    def test_street_id_resolves_all_points_on_street_including_inactive_excluded(self):
        supply_points, not_found, _ = bulk_planner.resolve_identifiers(
            bulk_planner.IDENTIFIER_STREET_ID, [str(self.street_mallorca.id)]
        )
        found_ids = {sp.id for sp in supply_points}
        # Both numbers of the street resolve; the inactive point is excluded.
        self.assertEqual(found_ids, {self.sp_a.id, self.sp_b.id})
        self.assertEqual(not_found, [])

    def test_two_street_ids_union_without_duplicates(self):
        supply_points, not_found, _ = bulk_planner.resolve_identifiers(
            bulk_planner.IDENTIFIER_STREET_ID,
            [str(self.street_mallorca.id), str(self.street_girona.id)],
        )
        found_ids = [sp.id for sp in supply_points]
        self.assertEqual(sorted(found_ids), sorted([self.sp_a.id, self.sp_b.id, self.sp_d.id]))
        self.assertEqual(len(found_ids), len(set(found_ids)))
        self.assertEqual(not_found, [])

    def test_street_with_no_addresses_is_valid_but_resolves_zero(self):
        supply_points, not_found, _ = bulk_planner.resolve_identifiers(
            bulk_planner.IDENTIFIER_STREET_ID, [str(self.street_empty.id)]
        )
        self.assertEqual(supply_points, [])
        # The street id exists, so it must not be flagged as not_found.
        self.assertEqual(not_found, [])

    def test_non_numeric_line_in_street_mode_is_not_found(self):
        supply_points, not_found, _ = bulk_planner.resolve_identifiers(
            bulk_planner.IDENTIFIER_STREET_ID, ['Mallorca']
        )
        self.assertEqual(supply_points, [])
        self.assertEqual(not_found, ['Mallorca'])

    def test_unknown_street_id_is_not_found(self):
        _, not_found, _ = bulk_planner.resolve_identifiers(
            bulk_planner.IDENTIFIER_STREET_ID, ['999999']
        )
        self.assertEqual(not_found, ['999999'])

    def test_supply_point_id_resolution_and_not_found(self):
        supply_points, not_found, _ = bulk_planner.resolve_identifiers(
            bulk_planner.IDENTIFIER_SUPPLY_POINT_ID,
            [str(self.sp_a.id), str(self.sp_d.id), 'not-a-number', '888888'],
        )
        self.assertEqual({sp.id for sp in supply_points}, {self.sp_a.id, self.sp_d.id})
        self.assertEqual(sorted(not_found), sorted(['not-a-number', '888888']))

    def test_contract_token_resolution_via_m2m_and_default(self):
        contract_m2m = Contract.objects.create(token='CT-001')
        contract_m2m.supply_points.set([self.sp_a])
        contract_default = Contract.objects.create(token='CT-002', supply_point_default=self.sp_b)

        supply_points, not_found, matched = bulk_planner.resolve_identifiers(
            bulk_planner.IDENTIFIER_CONTRACT_TOKEN,
            ['CT-001', 'CT-002', 'no-existeix'],
        )
        self.assertEqual({sp.id for sp in supply_points}, {self.sp_a.id, self.sp_b.id})
        self.assertEqual(not_found, ['no-existeix'])
        self.assertEqual(matched[self.sp_a.id], ['CT-001'])
        self.assertEqual(matched[self.sp_b.id], ['CT-002'])

    def test_normalize_dedupes_preserving_order_and_strips(self):
        result = bulk_planner.normalize_identifiers(
            bulk_planner.IDENTIFIER_SUPPLY_POINT_ID,
            [' 5 ', '', '3', '5', None, ' 3 '],
        )
        self.assertEqual(result, ['5', '3'])

    def test_cap_is_enforced(self):
        ids = [str(i) for i in range(bulk_planner.MAX_IDENTIFIERS + 1)]
        with self.assertRaises(bulk_planner.BulkPlanError) as ctx:
            bulk_planner.build_preview(bulk_planner.IDENTIFIER_SUPPLY_POINT_ID, ids)
        self.assertEqual(ctx.exception.code, 'over_cap')

    def test_unknown_type_is_error(self):
        with self.assertRaises(bulk_planner.BulkPlanError) as ctx:
            bulk_planner.build_preview('street_name', ['Mallorca'])
        self.assertEqual(ctx.exception.code, 'unknown_type')

    def test_conflict_detection_open_vs_closed(self):
        now = timezone.now()
        open_cut = SupplyCut.objects.create(
            token='OPEN-1',
            status=self.status_active,
            cause=self.cause,
            date_start=now,
        )
        open_cut.supply_points.set([self.sp_a])
        closed_cut = SupplyCut.objects.create(
            token='CLOSED-1',
            status=self.status_finished,
            cause=self.cause,
            date_start=now - timedelta(days=30),
        )
        closed_cut.supply_points.set([self.sp_b])
        cancelled_cut = SupplyCut.objects.create(
            token='CANCELLED-1',
            status=self.status_cancelled,
            cause=self.cause,
            date_start=now,
        )
        cancelled_cut.supply_points.set([self.sp_d])

        conflicts = bulk_planner.detect_conflicts([self.sp_a.id, self.sp_b.id, self.sp_d.id])
        conflict_sp_ids = {c['supply_point_id'] for c in conflicts}
        # Only the ACTIVE cut counts as open; Acabat/Cancel·lat do not.
        self.assertEqual(conflict_sp_ids, {self.sp_a.id})
        self.assertEqual(conflicts[0]['cuts'][0]['id'], open_cut.id)

    def test_detect_conflicts_respects_exclude_cut_id(self):
        now = timezone.now()
        cut = SupplyCut.objects.create(
            token='SELF-1', status=self.status_active, cause=self.cause, date_start=now,
        )
        cut.supply_points.set([self.sp_a])
        self.assertEqual(bulk_planner.detect_conflicts([self.sp_a.id], exclude_cut_id=cut.id), [])

    def test_detect_vulnerable_empty_ids_returns_empty(self):
        """An empty point selection has no vulnerable people."""
        self.assertEqual(bulk_planner.detect_vulnerable([]), [])

    def test_detect_vulnerable_flags_any_nonzero_level_in_any_role(self):
        # Holder level 2 (Vulnerable) via the M2M relation.
        """Detect vulnerable holders, tenants and owners through both contract relations."""
        holder = self.make_person('P-VULN-1', vulnerability_level=2)
        self.make_contract('CT-VULN-1', supply_point=self.sp_a, holder=holder)
        # Tenant level 1 (En Risc) via the default FK relation.
        tenant = self.make_person('P-RISK-1', vulnerability_level=1)
        contract_b = Contract.objects.create(token='CT-VULN-2', supply_point_default=self.sp_b, tenant=tenant)
        # Owner level 2 on a contract linked only through the M2M.
        owner = self.make_person('P-VULN-2', vulnerability_level=2)
        contract_c = Contract.objects.create(token='CT-VULN-3', owner=owner)
        contract_c.supply_points.set([self.sp_d])

        vulnerable = bulk_planner.detect_vulnerable([self.sp_a.id, self.sp_b.id, self.sp_d.id])
        by_sp = {v['supply_point_id']: v['people'] for v in vulnerable}
        self.assertEqual(set(by_sp), {self.sp_a.id, self.sp_b.id, self.sp_d.id})
        self.assertEqual(by_sp[self.sp_a.id][0]['role'], 'holder')
        self.assertEqual(by_sp[self.sp_a.id][0]['vulnerability_level'], 2)
        self.assertEqual(by_sp[self.sp_b.id][0]['role'], 'tenant')
        self.assertEqual(by_sp[self.sp_b.id][0]['vulnerability_level'], 1)
        self.assertEqual(by_sp[self.sp_d.id][0]['role'], 'owner')
        self.assertEqual(by_sp[self.sp_d.id][0]['vulnerability_level'], 2)

    def test_detect_vulnerable_ignores_level_zero_and_inactive_contracts(self):
        """Exclude safe people and vulnerable people on inactive contracts."""
        safe_holder = self.make_person('P-SAFE', vulnerability_level=0)
        self.make_contract('CT-SAFE', supply_point=self.sp_a, holder=safe_holder)

        # Vulnerable holder, but the contract is inactive: must not count.
        vuln_holder = self.make_person('P-INACT', vulnerability_level=2)
        self.make_contract('CT-INACT', supply_point=self.sp_b, holder=vuln_holder, is_active=False)

        self.assertEqual(bulk_planner.detect_vulnerable([self.sp_a.id, self.sp_b.id]), [])

    def test_detect_vulnerable_dedupes_same_person_and_role_across_contracts(self):
        """Report a shared holder only once per supply point across linked contracts."""
        holder = self.make_person('P-DEDUP', vulnerability_level=2)
        self.make_contract('CT-DEDUP-1', supply_point=self.sp_a, holder=holder)
        self.make_contract('CT-DEDUP-2', supply_point=self.sp_a, holder=holder)

        vulnerable = bulk_planner.detect_vulnerable([self.sp_a.id])
        self.assertEqual(len(vulnerable), 1)
        self.assertEqual(len(vulnerable[0]['people']), 1)
        self.assertEqual(vulnerable[0]['people'][0]['person_id'], holder.id)

    def test_detect_vulnerable_uses_two_queries_regardless_of_sp_count(self):
        """No N+1: exactly two queries (M2M + default FK) for any SP count."""
        for index, sp in enumerate([self.sp_a, self.sp_b, self.sp_c, self.sp_d]):
            holder = self.make_person('P-N1-{}'.format(index), vulnerability_level=2)
            self.make_contract('CT-N1-{}'.format(index), supply_point=sp, holder=holder)

        with self.assertNumQueries(2):
            bulk_planner.detect_vulnerable([self.sp_a.id, self.sp_b.id, self.sp_c.id, self.sp_d.id])

    def test_build_preview_stats_and_vulnerable_flags(self):
        """Expose vulnerability counts, affected people and per-row flags in previews."""
        holder = self.make_person('P-PREVIEW', vulnerability_level=2)
        self.make_contract('CT-PREVIEW', supply_point=self.sp_a, holder=holder)

        preview = bulk_planner.build_preview(
            bulk_planner.IDENTIFIER_STREET_ID,
            [str(self.street_mallorca.id), str(self.street_girona.id)],
        )
        self.assertEqual(preview['stats']['vulnerable'], 1)
        self.assertEqual(len(preview['vulnerable']), 1)
        self.assertEqual(preview['vulnerable'][0]['supply_point_id'], self.sp_a.id)
        self.assertEqual(preview['vulnerable'][0]['people'][0]['role'], 'holder')

        by_id = {row['supply_point_id']: row for row in preview['resolved']}
        self.assertTrue(by_id[self.sp_a.id]['has_vulnerable_person'])
        self.assertFalse(by_id[self.sp_b.id]['has_vulnerable_person'])
        self.assertFalse(by_id[self.sp_d.id]['has_vulnerable_person'])

    def test_build_preview_stats_and_conflict_flags(self):
        now = timezone.now()
        cut = SupplyCut.objects.create(
            token='OPEN-2', status=self.status_active, cause=self.cause, date_start=now,
        )
        cut.supply_points.set([self.sp_a])

        preview = bulk_planner.build_preview(
            bulk_planner.IDENTIFIER_STREET_ID,
            [str(self.street_mallorca.id), str(self.street_mallorca.id), str(self.street_girona.id)],
        )
        self.assertEqual(preview['stats']['total_input'], 3)
        self.assertEqual(preview['stats']['unique'], 2)
        self.assertEqual(preview['stats']['duplicates_in_input'], 1)
        self.assertEqual(preview['stats']['resolved'], 3)
        self.assertEqual(preview['stats']['conflicts'], 1)

        by_id = {row['supply_point_id']: row for row in preview['resolved']}
        self.assertTrue(by_id[self.sp_a.id]['has_conflict'])
        self.assertFalse(by_id[self.sp_b.id]['has_conflict'])
        self.assertEqual(by_id[self.sp_a.id]['street_id'], self.street_mallorca.id)


class TestSupplyCutBulkPlannerEndpoints(BulkPlannerFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        """Seed streets, points, planned and active statuses, and both cause types for API tests."""
        super().setUpTestData()
        cls.country = Country.objects.create(name='Espanya', iso_code='ES')
        cls.city = City.objects.create(name='Barcelona', token='BCN')
        cls.cause, _ = SupplyCutCause.objects.get_or_create(token='1', defaults={'name': 'Obres'})
        # `is_temporary` defaults to False, so `cls.cause` is a permanent
        # cause; the vulnerable-override tests need an explicitly temporary
        # one because permanent + vulnerable is a hard 400 with no override.
        cls.cause_temporary, _ = SupplyCutCause.objects.get_or_create(
            token='TMP-BULK', defaults={'name': 'Obres temporals', 'is_temporary': True},
        )
        cls.status_planned, _ = SupplyCutStatus.objects.get_or_create(token='0', defaults={'name': 'Planificat'})
        cls.status_active, _ = SupplyCutStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        # The contract post_save signal looks this up on every save.
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': '99'},
        )

        cls.street = Street.objects.create(name='Mallorca', city=cls.city)
        cls.street2 = Street.objects.create(name='Diagonal', city=cls.city)
        addr = cls.make_address(cls.street, cls.city, number='10')
        cls.sp = cls.make_point(addr, token='SP-EP')
        addr2 = cls.make_address(cls.street2, cls.city, number='20')
        cls.sp2 = cls.make_point(addr2, token='SP-EP-2')

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='bulkcut', password='password')
        ct = ContentType.objects.get_for_model(SupplyCut)
        add_perm = Permission.objects.get(content_type=ct, codename='add_supplycut')
        self.user.user_permissions.add(add_perm)

    def _preview(self, payload):
        view = SupplyCutViewSet.as_view({'post': 'bulk_plan_preview'})
        request = self.factory.post(
            '/service/supplycut/bulk-plan/preview/', payload, format='json',
        )
        force_authenticate(request, user=self.user)
        return view(request)

    def _create(self, payload):
        view = SupplyCutViewSet.as_view({'post': 'bulk_plan'})
        request = self.factory.post(
            '/service/supplycut/bulk-plan/', payload, format='json',
        )
        force_authenticate(request, user=self.user)
        return view(request)

    def test_preview_endpoint_resolves_street_ids(self):
        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['resolved'], 1)
        self.assertEqual(response.data['resolved'][0]['supply_point_id'], self.sp.id)
        self.assertEqual(response.data['resolved'][0]['street_id'], self.street.id)

    def test_preview_unknown_type_400(self):
        response = self._preview({'identifier_type': 'street_name', 'identifiers': ['x']})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'unknown_type')

    def test_create_builds_one_planned_cut_with_all_points(self):
        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'cause_id': self.cause.id,
            'date_start': '2030-01-01T08:00:00Z',
            'date_end': '2030-01-01T12:00:00Z',
        })
        self.assertEqual(response.status_code, 201)
        cut = SupplyCut.objects.get(id=response.data['cut_id'])
        # Born PLANNED, source manual, points linked but not cut at create.
        self.assertEqual(cut.status_id, self.status_planned.id)
        self.assertEqual(cut.source, 'manual')
        self.assertEqual(list(cut.supply_points.all()), [self.sp])
        self.assertRegex(cut.token, r'^\d{5}-\d{8}$')

    def test_create_over_conflict_without_override_is_409(self):
        now = timezone.now()
        open_cut = SupplyCut.objects.create(
            token='OPEN-EP', status=self.status_active, cause=self.cause, date_start=now,
        )
        open_cut.supply_points.set([self.sp])

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'cause_id': self.cause.id,
            'date_start': '2030-01-01T08:00:00Z',
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'conflicts')
        self.assertEqual(SupplyCut.objects.count(), 1)  # only the pre-existing open cut

    def test_create_over_conflict_with_override_succeeds(self):
        now = timezone.now()
        open_cut = SupplyCut.objects.create(
            token='OPEN-EP2', status=self.status_active, cause=self.cause, date_start=now,
        )
        open_cut.supply_points.set([self.sp])

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'cause_id': self.cause.id,
            'date_start': '2030-01-01T08:00:00Z',
            'override_conflicts': True,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['conflict_count'], 1)
        self.assertEqual(SupplyCut.objects.count(), 2)  # pre-existing open cut + new one

    def test_create_with_zero_resolved_is_400(self):
        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': ['999999'],
            'cause_id': self.cause.id,
            'date_start': '2030-01-01T08:00:00Z',
        })
        self.assertEqual(response.status_code, 400)

    def test_create_over_vulnerable_without_override_is_409(self):
        """Reject a temporary bulk cut over vulnerable people without an override."""
        holder = self.make_person('P-EP-VULN', vulnerability_level=2)
        self.make_contract('CT-EP-VULN', supply_point=self.sp, holder=holder)

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'cause_id': self.cause_temporary.id,
            'date_start': '2030-01-01T08:00:00Z',
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'vulnerable')
        self.assertEqual(response.data['vulnerable'][0]['supply_point_id'], self.sp.id)
        self.assertEqual(SupplyCut.objects.count(), 0)

    def test_create_permanent_over_vulnerable_is_400_even_with_override(self):
        """Block permanent bulk cuts over vulnerable people even with an override."""
        holder = self.make_person('P-EP-VULN-PERM', vulnerability_level=2)
        self.make_contract('CT-EP-VULN-PERM', supply_point=self.sp, holder=holder)

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'cause_id': self.cause.id,  # permanent (is_temporary defaults to False)
            'date_start': '2030-01-01T08:00:00Z',
            'override_vulnerable': True,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'vulnerability_blocked')
        self.assertEqual(response.data['vulnerable'][0]['supply_point_id'], self.sp.id)
        self.assertEqual(SupplyCut.objects.count(), 0)

    def test_create_over_vulnerable_with_override_succeeds(self):
        """Allow a temporary bulk cut over vulnerable people with an explicit override."""
        holder = self.make_person('P-EP-VULN2', vulnerability_level=2)
        self.make_contract('CT-EP-VULN2', supply_point=self.sp, holder=holder)

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'cause_id': self.cause_temporary.id,
            'date_start': '2030-01-01T08:00:00Z',
            'date_end': '2030-01-02T08:00:00Z',
            'override_vulnerable': True,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['vulnerable_count'], 1)
        self.assertEqual(SupplyCut.objects.count(), 1)

    def test_create_safe_points_still_succeeds_without_override(self):
        """Create a bulk cut without an override when all linked people are safe."""
        safe_holder = self.make_person('P-EP-SAFE', vulnerability_level=0)
        self.make_contract('CT-EP-SAFE', supply_point=self.sp, holder=safe_holder)

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'cause_id': self.cause.id,
            'date_start': '2030-01-01T08:00:00Z',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['vulnerable_count'], 0)

    def test_preview_endpoint_surfaces_vulnerable_points(self):
        """Include vulnerable point details and counts in the preview endpoint response."""
        holder = self.make_person('P-EP-PREVIEW', vulnerability_level=1)
        self.make_contract('CT-EP-PREVIEW', supply_point=self.sp, holder=holder)

        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['vulnerable'], 1)
        self.assertEqual(response.data['vulnerable'][0]['supply_point_id'], self.sp.id)
        self.assertTrue(response.data['resolved'][0]['has_vulnerable_person'])

    def test_preview_merges_manual_supply_points_and_identifiers(self):
        """Merge manual points with text matches and label the manual row origin."""
        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [self.sp2.id],
        })
        self.assertEqual(response.status_code, 200)
        ids = {row['supply_point_id'] for row in response.data['resolved']}
        self.assertEqual(ids, {self.sp.id, self.sp2.id})
        self.assertEqual(response.data['stats']['resolved'], 2)
        self.assertEqual(response.data['not_found'], [])
        manual_row = next(r for r in response.data['resolved'] if r['supply_point_id'] == self.sp2.id)
        self.assertEqual(manual_row['matched_by'], ['manual'])

    def test_preview_dedupes_manual_duplicate_of_identifier(self):
        """Include a point selected both manually and through text only once."""
        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [self.sp.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['resolved'], 1)
        self.assertEqual(len(response.data['resolved']), 1)

    def test_preview_reports_unknown_manual_ids_as_not_found(self):
        """Report missing numeric and malformed manual point IDs without losing valid matches."""
        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [999999, 'not-a-number'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['supply_point_id'] for row in response.data['resolved']}, {self.sp.id})
        self.assertIn('999999', response.data['not_found'])
        self.assertIn('not-a-number', response.data['not_found'])

    def test_preview_expands_manual_contract_ids(self):
        """Expand selected contracts into points without reporting resolved contracts as misses."""
        contract = self.make_contract('CT-EP-MANUAL', supply_point=self.sp2)
        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'contract_ids': [contract.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['resolved'], 2)
        self.assertIn(self.sp2.id, {row['supply_point_id'] for row in response.data['resolved']})
        # Regression: fully-resolved contract ids must never be reported as misses
        # (the miss check used to compare contract ids against supply-point ids).
        self.assertEqual(response.data['not_found'], [])

    def test_preview_contract_without_points_reports_token_as_not_found(self):
        """Report the commercial token of a selected contract with no supply points."""
        contract = self.make_contract('CT-EP-NOSP', supply_point=None)
        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'contract_ids': [contract.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['supply_point_id'] for row in response.data['resolved']}, {self.sp.id})
        self.assertEqual(response.data['not_found'], ['CT-EP-NOSP'])

    def test_preview_unknown_contract_id_reports_raw_id_as_not_found(self):
        """Use the raw ID as the missing label when the selected contract does not exist."""
        response = self._preview({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'contract_ids': [999999],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['supply_point_id'] for row in response.data['resolved']}, {self.sp.id})
        self.assertEqual(response.data['not_found'], ['999999'])

    def test_create_hybrid_saves_combined_list(self):
        """Persist the union of text-resolved and manually selected supply points."""
        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [self.sp2.id],
            'cause_id': self.cause.id,
            'date_start': '2030-01-01T08:00:00Z',
        })
        self.assertEqual(response.status_code, 201)
        cut = SupplyCut.objects.get(id=response.data['cut_id'])
        self.assertEqual(set(cut.supply_points.values_list('id', flat=True)), {self.sp.id, self.sp2.id})
        self.assertEqual(response.data['resolved_count'], 2)

    def test_create_hybrid_vulnerable_manual_point_is_409_then_override(self):
        """Require an override for vulnerable manual points in a temporary hybrid cut."""
        holder = self.make_person('P-EP-HYBRID', vulnerability_level=2)
        self.make_contract('CT-EP-HYBRID', supply_point=self.sp2, holder=holder)

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [self.sp2.id],
            'cause_id': self.cause_temporary.id,
            'date_start': '2030-01-01T08:00:00Z',
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'vulnerable')
        self.assertEqual(response.data['vulnerable'][0]['supply_point_id'], self.sp2.id)
        self.assertEqual(SupplyCut.objects.count(), 0)

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [self.sp2.id],
            'cause_id': self.cause_temporary.id,
            'date_start': '2030-01-01T08:00:00Z',
            'date_end': '2030-01-02T08:00:00Z',
            'override_vulnerable': True,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['vulnerable_count'], 1)
        cut = SupplyCut.objects.get(id=response.data['cut_id'])
        self.assertEqual(set(cut.supply_points.values_list('id', flat=True)), {self.sp.id, self.sp2.id})

    def test_create_hybrid_permanent_vulnerable_manual_point_is_400(self):
        """Block permanent hybrid cuts when a manual point has vulnerable people."""
        holder = self.make_person('P-EP-HYBRID-PERM', vulnerability_level=2)
        self.make_contract('CT-EP-HYBRID-PERM', supply_point=self.sp2, holder=holder)

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [self.sp2.id],
            'cause_id': self.cause.id,  # permanent
            'date_start': '2030-01-01T08:00:00Z',
            'override_vulnerable': True,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'vulnerability_blocked')
        self.assertEqual(response.data['vulnerable'][0]['supply_point_id'], self.sp2.id)
        self.assertEqual(SupplyCut.objects.count(), 0)

    def test_create_hybrid_conflict_on_manual_point_is_409(self):
        """Detect an existing open cut on a manually selected point in a hybrid request."""
        now = timezone.now()
        open_cut = SupplyCut.objects.create(
            token='OPEN-EP-HY', status=self.status_active, cause=self.cause, date_start=now,
        )
        open_cut.supply_points.set([self.sp2])

        response = self._create({
            'identifier_type': 'street_id',
            'identifiers': [str(self.street.id)],
            'supply_points': [self.sp2.id],
            'cause_id': self.cause.id,
            'date_start': '2030-01-01T08:00:00Z',
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'conflicts')
        self.assertEqual(SupplyCut.objects.count(), 1)

    def test_create_without_permission_is_403(self):
        other = User.objects.create_user(username='nocreate', password='password')
        view = SupplyCutViewSet.as_view({'post': 'bulk_plan'})
        request = self.factory.post(
            '/service/supplycut/bulk-plan/',
            {
                'identifier_type': 'street_id',
                'identifiers': [str(self.street.id)],
                'cause_id': self.cause.id,
                'date_start': '2030-01-01T08:00:00Z',
            },
            format='json',
        )
        force_authenticate(request, user=other)
        response = view(request)
        self.assertEqual(response.status_code, 403)


class TestStreetResolveIdsEndpoint(TestCase):
    """Sanity-check helper: street ids -> display labels for the bulk planner."""

    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(name='Espanya', iso_code='ES')
        cls.city = City.objects.create(name='Barcelona', token='BCN')
        cls.street_a = Street.objects.create(name='Mallorca', city=cls.city)
        cls.street_b = Street.objects.create(name='Girona', city=cls.city)

    def test_resolve_ids_returns_labels(self):
        from coredata.views.street_view import StreetViewSet
        factory = APIRequestFactory()
        user = User.objects.create_user(username='streetuser', password='password')
        view = StreetViewSet.as_view({'post': 'resolve_ids'})
        request = factory.post(
            '/coredata/street/resolve-ids/',
            {'ids': [str(self.street_a.id), str(self.street_b.id), 'not-a-number', '999999']},
            format='json',
        )
        force_authenticate(request, user=user)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        streets = response.data['streets']
        self.assertEqual({s['id'] for s in streets}, {self.street_a.id, self.street_b.id})
        labels = {s['id']: s['label'] for s in streets}
        self.assertIn('Mallorca', labels[self.street_a.id])
        # Unknown / non-numeric ids are silently dropped, never crash.
        self.assertNotIn('999999', [str(s['id']) for s in streets])

    def test_resolve_ids_requires_list(self):
        from coredata.views.street_view import StreetViewSet
        factory = APIRequestFactory()
        user = User.objects.create_user(username='streetuser2', password='password')
        view = StreetViewSet.as_view({'post': 'resolve_ids'})
        request = factory.post('/coredata/street/resolve-ids/', {'ids': 'nope'}, format='json')
        force_authenticate(request, user=user)
        response = view(request)
        self.assertEqual(response.status_code, 400)


class TestSupplyCutLifecycleVulnerability(BulkPlannerFixtureMixin, TestCase):
    """Immutabilitat de membres (PUT), canvi de motiu i re-validació a l'activar."""

    @classmethod
    def setUpTestData(cls):
        """Seed points, cause types and statuses for membership and activation tests."""
        super().setUpTestData()
        cls.country = Country.objects.create(name='Espanya', iso_code='ES')
        cls.city = City.objects.create(name='Barcelona', token='BCN')
        cls.cause_temporary, _ = SupplyCutCause.objects.get_or_create(
            token='TMP', defaults={'name': 'Obres temporals', 'is_temporary': True},
        )
        cls.cause_permanent, _ = SupplyCutCause.objects.get_or_create(
            token='PERM', defaults={'name': 'Xarxa permanent', 'is_temporary': False},
        )
        cls.status_planned, _ = SupplyCutStatus.objects.get_or_create(token='0', defaults={'name': 'Planificat'})
        cls.status_active, _ = SupplyCutStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(
            token='1', defaults={'name': 'Actiu', 'is_default': True},
        )
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': '99'},
        )
        cls.street = Street.objects.create(name='Rossello', city=cls.city)
        addr_a = cls.make_address(cls.street, cls.city, number='10')
        addr_b = cls.make_address(cls.street, cls.city, number='12')
        cls.sp_1 = cls.make_point(addr_a, token='SP-LC-1')
        cls.sp_2 = cls.make_point(addr_b, token='SP-LC-2')

    def setUp(self):
        """Create an authenticated request factory and grant the required cut permissions."""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='lifecycle', password='password')
        ct = ContentType.objects.get_for_model(SupplyCut)
        self.user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='add_supplycut'),
            Permission.objects.get(content_type=ct, codename='change_supplycut'),
        )

    def _make_cut(self, points, cause=None, status=None):
        """Create a cut with the requested points, defaulting to planned and temporary."""
        cut = SupplyCut.objects.create(
            token='LC-CUT-{}'.format(SupplyCut.objects.count()),
            status=status or self.status_planned,
            cause=cause or self.cause_temporary,
            date_start=timezone.now(),
            date_end=timezone.now() + timedelta(hours=2),
        )
        cut.supply_points.set(points)
        return cut

    def _make_active_contract(self, token, supply_point, holder):
        """Create a linked contract and assign the fixture active status."""
        contract = self.make_contract(token, supply_point=supply_point, holder=holder)
        contract.status = self.contract_status
        contract.save()
        return contract

    def _put(self, cut, payload):
        """Submit an authenticated update request for the given cut."""
        view = SupplyCutViewSet.as_view({'put': 'update'})
        request = self.factory.put(
            '/service/supplycut/{}/'.format(cut.id), payload, format='json',
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=str(cut.id))

    def _start(self, cut, payload=None):
        """Submit an authenticated activation request with optional override data."""
        view = SupplyCutViewSet.as_view({'post': 'start_cut'})
        request = self.factory.post(
            '/service/supplycut/{}/start-cut/'.format(cut.id), payload or {}, format='json',
        )
        force_authenticate(request, user=self.user)
        return view(request, pk=str(cut.id))

    def test_put_adding_supply_points_is_400(self):
        """Reject adding points to an existing cut and preserve its membership."""
        cut = self._make_cut([self.sp_1])
        original_token = cut.token
        response = self._put(cut, {
            'supply_points': [self.sp_1.id, self.sp_2.id],
            'token': 'must-not-be-saved',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('supply_points', response.data)
        cut.refresh_from_db()
        self.assertEqual(list(cut.supply_points.all()), [self.sp_1])
        self.assertEqual(cut.token, original_token)

    def test_put_removing_supply_points_is_400(self):
        """Reject removing points through update and preserve the existing membership."""
        cut = self._make_cut([self.sp_1, self.sp_2])
        response = self._put(cut, {'supply_points': [self.sp_1.id]})
        self.assertEqual(response.status_code, 400)
        self.assertIn('supply_points', response.data)
        cut.refresh_from_db()
        self.assertEqual(set(cut.supply_points.values_list('id', flat=True)), {self.sp_1.id, self.sp_2.id})

    def test_put_identical_supply_points_is_noop_200(self):
        """Accept an unchanged point selection without altering membership."""
        cut = self._make_cut([self.sp_1])
        response = self._put(cut, {'supply_points': [self.sp_1.id]})
        self.assertEqual(response.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(list(cut.supply_points.all()), [self.sp_1])

    def test_put_cause_flip_to_permanent_with_vulnerable_is_400(self):
        """Block changing a vulnerable cut to permanent and preserve its previous cause."""
        holder = self.make_person('P-LC-BLOCK', vulnerability_level=2)
        self._make_active_contract('CT-LC-BLOCK', self.sp_1, holder)
        cut = self._make_cut([self.sp_1])

        response = self._put(cut, {'cause_id': self.cause_permanent.id})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'vulnerability_blocked')
        cut.refresh_from_db()
        self.assertEqual(cut.cause_id, self.cause_temporary.id)

    def test_put_cause_flip_to_temporary_requires_confirmation(self):
        """Require the confirmation word before changing a vulnerable cut to temporary."""
        holder = self.make_person('P-LC-CONFIRM', vulnerability_level=1)
        self._make_active_contract('CT-LC-CONFIRM', self.sp_1, holder)
        cut = self._make_cut([self.sp_1], cause=self.cause_permanent)

        response = self._put(cut, {'cause_id': self.cause_temporary.id})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'vulnerability_confirm_required')

        response = self._put(cut, {
            'cause_id': self.cause_temporary.id,
            'date_end': (timezone.now() + timedelta(hours=2)).isoformat(),
            'vulnerable_confirmation': 'CONFIRMAR',
        })
        self.assertEqual(response.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(cut.cause_id, self.cause_temporary.id)

    def test_put_cause_change_without_vulnerable_people_succeeds(self):
        """Allow a cause change when no linked people are vulnerable."""
        cut = self._make_cut([self.sp_1])
        response = self._put(cut, {'cause_id': self.cause_permanent.id})
        self.assertEqual(response.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(cut.cause_id, self.cause_permanent.id)

    def test_start_cut_with_vulnerable_is_409(self):
        """Keep a vulnerable temporary cut planned until an override is provided."""
        holder = self.make_person('P-LC-START', vulnerability_level=2)
        self._make_active_contract('CT-LC-START', self.sp_1, holder)
        cut = self._make_cut([self.sp_1])

        response = self._start(cut)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'vulnerable')
        self.assertEqual(response.data['vulnerable'][0]['supply_point_id'], self.sp_1.id)
        cut.refresh_from_db()
        self.assertEqual(cut.status_id, self.status_planned.id)

    def test_start_cut_with_vulnerable_and_override_succeeds(self):
        """Activate a vulnerable temporary cut when an explicit override is provided."""
        holder = self.make_person('P-LC-START2', vulnerability_level=2)
        self._make_active_contract('CT-LC-START2', self.sp_1, holder)
        cut = self._make_cut([self.sp_1])

        response = self._start(cut, {'override_vulnerable': True})
        self.assertEqual(response.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(cut.status_id, self.status_active.id)

    def test_start_cut_permanent_with_vulnerable_is_400_even_with_override(self):
        # Vulnerability may have been registered AFTER the cut was created:
        # re-validation at start-cut must apply the strict permanent rule.
        """Recheck vulnerability at activation and block permanent cuts despite overrides."""
        holder = self.make_person('P-LC-START-PERM', vulnerability_level=2)
        self._make_active_contract('CT-LC-START-PERM', self.sp_1, holder)
        cut = self._make_cut([self.sp_1], cause=self.cause_permanent)

        response = self._start(cut, {'override_vulnerable': True})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'vulnerability_blocked')
        self.assertEqual(response.data['vulnerable'][0]['supply_point_id'], self.sp_1.id)
        cut.refresh_from_db()
        self.assertEqual(cut.status_id, self.status_planned.id)

    def test_start_cut_without_vulnerable_people_succeeds(self):
        """Activate a cut without an override when no linked people are vulnerable."""
        safe_holder = self.make_person('P-LC-SAFE', vulnerability_level=0)
        self._make_active_contract('CT-LC-SAFE', self.sp_1, safe_holder)
        cut = self._make_cut([self.sp_1])

        response = self._start(cut)
        self.assertEqual(response.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(cut.status_id, self.status_active.id)


    def test_start_cut_without_cause_blocks_vulnerable_even_with_override(self):
        holder = self.make_person('P-NO-CAUSE', vulnerability_level=2)
        self._make_active_contract('CT-NO-CAUSE', self.sp_1, holder)
        cut = self._make_cut([self.sp_1])
        cut.cause = None
        cut.save()

        response = self._start(cut, {'override_vulnerable': True})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'vulnerability_blocked')
        cut.refresh_from_db()
        self.assertEqual(cut.status_id, self.status_planned.id)
        self.assertIsNone(cut.exec_start)

    def test_service_rechecks_vulnerability_added_after_creation(self):
        from service.utils import supply_cut_service

        holder = self.make_person('P-LATE-VULN', vulnerability_level=0)
        contract = self._make_active_contract('CT-LATE-VULN', self.sp_1, holder)
        contract.supply_points.clear()
        cut = self._make_cut([self.sp_1], cause=self.cause_permanent)
        holder.vulnerability_level = 2
        holder.save()

        with self.assertRaises(supply_cut_service.SupplyCutActivationError) as raised:
            supply_cut_service.start_cut(cut, override_vulnerable=True)
        self.assertEqual(raised.exception.detail['code'], 'vulnerability_blocked')
        cut.refresh_from_db()
        self.assertEqual(cut.status_id, self.status_planned.id)
        self.assertIsNone(cut.exec_start)
        self.sp_1.refresh_from_db()
        self.assertIsNone(self.sp_1.status_id)

    def test_scheduled_activation_skips_late_vulnerability_and_continues(self):
        from service.models import SupplyPointStatus
        from service.tasks import activate_supply_cut

        cut_point_status = SupplyPointStatus.objects.create(token='test-cut', name='Tallat')
        ConfigProject.objects.update_or_create(
            token='supply_point_status_cut_token', defaults={'value': cut_point_status.token},
        )
        ConfigProject.objects.update_or_create(
            token='supply_cut_status_active_token', defaults={'value': self.status_active.token},
        )
        holder = self.make_person('P-SCHEDULED-LATE', vulnerability_level=0)
        contract = self._make_active_contract('CT-SCHEDULED-LATE', self.sp_1, holder)
        contract.supply_points.clear()
        blocked = self._make_cut([self.sp_1], cause=self.cause_permanent)
        safe = self._make_cut([self.sp_2], cause=self.cause_permanent)
        holder.vulnerability_level = 1
        holder.save()

        activate_supply_cut()

        blocked.refresh_from_db()
        safe.refresh_from_db()
        self.sp_1.refresh_from_db()
        self.sp_2.refresh_from_db()
        self.assertEqual(blocked.status_id, self.status_planned.id)
        self.assertIsNone(blocked.exec_start)
        self.assertIsNone(self.sp_1.status_id)
        self.assertEqual(safe.status_id, self.status_active.id)
        self.assertIsNotNone(safe.exec_start)
        self.assertEqual(self.sp_2.status_id, cut_point_status.id)

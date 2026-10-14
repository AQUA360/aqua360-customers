"""Tests per la planificació massiva de talls (bulk-plan preview + create)."""
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from contract.models import Contract
from coredata.models import Address, City, ConfigProject, Country, Street, StreetNumber
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
        super().setUpTestData()
        cls.country = Country.objects.create(name='Espanya', iso_code='ES')
        cls.city = City.objects.create(name='Barcelona', token='BCN')
        cls.cause, _ = SupplyCutCause.objects.get_or_create(token='1', defaults={'name': 'Obres'})
        cls.status_planned, _ = SupplyCutStatus.objects.get_or_create(token='0', defaults={'name': 'Planificat'})
        cls.status_active, _ = SupplyCutStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})

        cls.street = Street.objects.create(name='Mallorca', city=cls.city)
        addr = cls.make_address(cls.street, cls.city, number='10')
        cls.sp = cls.make_point(addr, token='SP-EP')

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

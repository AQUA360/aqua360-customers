"""Tests de rutes: ruta efectiva dels punts, afegir carrer, importació i ruta pròpia."""
import io

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from coredata.models import City, Street, StreetNumber
from service.models import Property, Route, RoutePosition, SupplyPoint
from service.serializers.route_serializer import RoutePositionSerializer
from service.utils import route_bulk_service
from service.utils.route_scope import (
    effective_route,
    position_supply_points_q,
    route_supply_points_q,
    serialize_effective_route,
    without_route_q,
)
from service.views.route_view import RouteViewSet


def _file(content, name='rutes.csv'):
    buf = io.BytesIO(content.encode('utf-8-sig'))
    buf.name = name
    return buf


class RouteTestMixin:
    def setUp(self):
        self.city = City.objects.create(token='C1', name='Ciutat')
        self.street = Street.objects.create(name='Major', token='ST-MAJOR', city=self.city)
        self.monthly = Route.objects.create(token='M1', name='Mensual')
        self.quarterly = Route.objects.create(token='T1', name='Trimestral')

    def make_property(self, token, number=None, route_position=None):
        street_number = None
        if number is not None:
            street_number = StreetNumber.objects.create(street=self.street, number=number)
        return Property.objects.create(
            token=token,
            address_street=self.street,
            address_street_number=street_number,
            address_city=self.city,
            route_position=route_position,
        )

    def make_position(self, route, position):
        return RoutePosition.objects.create(route=route, position=position, token=f'{route.token}_{position}')


class TestEffectiveRoute(RouteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.position = self.make_position(self.quarterly, 1)
        self.prop = self.make_property('P1', 1, self.position)
        self.sp_inherited = SupplyPoint.objects.create(token='SP1', property=self.prop)
        self.sp_own = SupplyPoint.objects.create(token='SP2', property=self.prop)
        self.monthly_position = self.make_position(self.monthly, 1)
        self.sp_own.route_position = self.monthly_position
        self.sp_own.save()
        self.sp_orphan = SupplyPoint.objects.create(token='SP3')

    def test_route_membership(self):
        quarterly_ids = set(SupplyPoint.objects.filter(route_supply_points_q(self.quarterly)).values_list('id', flat=True))
        monthly_ids = set(SupplyPoint.objects.filter(route_supply_points_q(self.monthly)).values_list('id', flat=True))
        self.assertEqual(quarterly_ids, {self.sp_inherited.id})
        self.assertEqual(monthly_ids, {self.sp_own.id})

    def test_position_membership_and_without_route(self):
        ids = set(SupplyPoint.objects.filter(position_supply_points_q(self.monthly_position)).values_list('id', flat=True))
        self.assertEqual(ids, {self.sp_own.id})
        orphans = set(SupplyPoint.objects.filter(without_route_q()).values_list('id', flat=True))
        self.assertEqual(orphans, {self.sp_orphan.id})

    def test_effective_route_helpers(self):
        self.assertEqual(effective_route(self.sp_inherited), self.quarterly)
        self.assertEqual(effective_route(self.sp_own), self.monthly)
        self.assertIsNone(effective_route(self.sp_orphan))
        data = serialize_effective_route(self.sp_own)
        self.assertEqual(data['route_token'], 'M1')
        self.assertFalse(data['inherited'])
        self.assertTrue(serialize_effective_route(self.sp_inherited)['inherited'])

    def test_route_counts(self):
        from service.utils.route_positions_service import route_count_total_readings
        self.assertEqual(route_count_total_readings(self.quarterly), 1)
        self.assertEqual(route_count_total_readings(self.monthly), 1)

    def test_position_serializer_lists_only_effective_supply_points(self):
        quarterly = RoutePositionSerializer(self.position).data['properties']
        monthly = RoutePositionSerializer(self.monthly_position).data['properties']
        self.assertEqual([sp['token'] for sp in quarterly[0]['supply_points']], ['SP1'])
        self.assertEqual(monthly[0]['token'], 'P1')
        self.assertEqual([sp['token'] for sp in monthly[0]['supply_points']], ['SP2'])
        self.assertTrue(monthly[0]['supply_points'][0]['own_route_position'])

    def test_position_update_does_not_detach_supply_points_from_property(self):
        serializer = RoutePositionSerializer(
            self.position,
            data={'property_ids': [self.prop.id], 'supply_points_ids': []},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.sp_inherited.refresh_from_db()
        self.sp_own.refresh_from_db()
        self.assertEqual(self.sp_inherited.property_id, self.prop.id)
        self.assertEqual(self.sp_own.property_id, self.prop.id)
        # El punt amb ruta pròpia en una altra posició no es toca.
        self.assertEqual(self.sp_own.route_position_id, self.monthly_position.id)


class TestSetSupplyPointRoute(RouteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.position = self.make_position(self.quarterly, 1)
        self.make_position(self.monthly, 1)
        self.make_position(self.monthly, 2)
        self.prop = self.make_property('P1', 1, self.position)
        self.sp_a = SupplyPoint.objects.create(token='SPA', property=self.prop)
        self.sp_b = SupplyPoint.objects.create(token='SPB', property=self.prop)

    def test_assign_reuse_and_reset(self):
        route_bulk_service.set_supply_point_route(self.sp_a, self.monthly)
        self.sp_a.refresh_from_db()
        own_position = self.sp_a.route_position
        self.assertEqual(own_position.route, self.monthly)
        self.assertEqual(own_position.position, 3)
        self.assertEqual(own_position.address_street, self.street)

        # Un altre punt de la mateixa finca reutilitza la mateixa parada.
        route_bulk_service.set_supply_point_route(self.sp_b, self.monthly)
        self.sp_b.refresh_from_db()
        self.assertEqual(self.sp_b.route_position, own_position)

        # Tornar a la ruta de la finca; la parada s'elimina quan queda buida.
        route_bulk_service.set_supply_point_route(self.sp_a, None)
        route_bulk_service.set_supply_point_route(self.sp_b, None)
        self.sp_a.refresh_from_db()
        self.assertIsNone(self.sp_a.route_position)
        self.assertFalse(RoutePosition.objects.filter(id=own_position.id).exists())

    def test_assign_at_position_shifts_following(self):
        route_bulk_service.set_supply_point_route(self.sp_a, self.monthly, position=1)
        positions = list(RoutePosition.objects.filter(route=self.monthly).order_by('position').values_list('position', 'token'))
        self.assertEqual(positions, [(1, 'M1_1'), (2, 'M1_2'), (3, 'M1_3')])
        self.sp_a.refresh_from_db()
        self.assertEqual(self.sp_a.route_position.position, 1)

    def test_same_route_as_property_inherits(self):
        route_bulk_service.set_supply_point_route(self.sp_a, self.quarterly)
        self.sp_a.refresh_from_db()
        self.assertIsNone(self.sp_a.route_position)


class TestAddStreet(RouteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.existing = self.make_position(self.monthly, 1)
        self.other_position = self.make_position(self.quarterly, 1)
        self.p1 = self.make_property('P1', 1)
        self.p2 = self.make_property('P2', 2)
        self.p2b = Property.objects.create(token='P2B', address_street=self.street,
                                           address_street_number=self.p2.address_street_number)
        self.p3 = self.make_property('P3', 3, self.other_position)
        self.p4 = self.make_property('P4', 4)
        SupplyPoint.objects.create(token='S1', property=self.p1)
        SupplyPoint.objects.create(token='S2', property=self.p2)

    def plan(self, **extra):
        data = {'street_id': self.street.id}
        data.update(extra)
        params = route_bulk_service.parse_add_street_params(data)
        return route_bulk_service.build_add_street_plan(self.monthly, params)

    def test_preview_groups_by_number_and_skips_assigned(self):
        data = route_bulk_service.serialize_add_street_plan(self.plan())
        self.assertEqual(data['insert_at'], 2)
        self.assertEqual(data['shift'], 0)
        self.assertEqual(data['totals']['positions'], 3)  # 1, 2 (dues finques), 4
        self.assertEqual(data['totals']['properties'], 4)
        self.assertEqual(data['totals']['skipped'], 1)
        self.assertEqual(data['totals']['supply_points'], 2)
        skipped = [p for g in data['positions'] for p in g['properties'] if p['action'] == 'skip']
        self.assertEqual(skipped[0]['current_route']['token'], 'T1')

    def test_apply_even_numbers_desc_inserted_at_start(self):
        result = route_bulk_service.apply_add_street_plan(
            self.plan(parity='even', order='desc', insert_at=1, assigned='move'))
        self.assertEqual(result['created_positions'], 2)
        self.assertEqual(result['assigned_properties'], 3)
        self.existing.refresh_from_db()
        self.assertEqual((self.existing.position, self.existing.token), (3, 'M1_3'))
        self.p4.refresh_from_db()
        self.p2.refresh_from_db()
        self.p2b.refresh_from_db()
        self.assertEqual(self.p4.route_position.position, 1)
        self.assertEqual(self.p2.route_position.position, 2)
        self.assertEqual(self.p2b.route_position, self.p2.route_position)

    def test_move_assigned(self):
        route_bulk_service.apply_add_street_plan(self.plan(number_from=3, number_to=3, assigned='move'))
        self.p3.refresh_from_db()
        self.assertEqual(self.p3.route_position.route, self.monthly)

    def test_endpoint(self):
        user = User.objects.create_superuser('admin_routes', 'a@a.cat', 'x')
        factory = APIRequestFactory()
        request = factory.post(f'/service/route/{self.monthly.id}/add-street/preview/',
                               {'street_id': self.street.id}, format='json')
        force_authenticate(request, user=user)
        response = RouteViewSet.as_view({'post': 'add_street_preview'})(request, pk=self.monthly.id)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['totals']['positions'], 3)

        request = factory.post(f'/service/route/{self.monthly.id}/add-street/preview/', {}, format='json')
        force_authenticate(request, user=user)
        response = RouteViewSet.as_view({'post': 'add_street_preview'})(request, pk=self.monthly.id)
        self.assertEqual(response.status_code, 400)


class TestRouteImport(RouteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.old_position = self.make_position(self.monthly, 1)
        self.p_old = self.make_property('POLD', 9, self.old_position)
        self.p1 = self.make_property('P1', 1)
        self.p5 = self.make_property('P5', 5)
        self.sp = SupplyPoint.objects.create(token='SPX', property=self.p_old)

    def plan(self, content, mode, name='rutes.csv'):
        rows = route_bulk_service.read_import_file(_file(content, name))
        return route_bulk_service.build_import_plan(rows, mode)

    def test_preview_statuses(self):
        content = (
            "route_token;position;property_token;supply_point_token;street;street_number\n"
            "M1;2;P1;;;\n"
            "NEW;1;;SPX;;\n"
            "M1;3;;;Major;5\n"
            "M1;4;PNOEXIST;;;\n"
            "M1;5;P1;;;\n"
        )
        data = route_bulk_service.serialize_import_plan(self.plan(content, 'append'))
        statuses = [(r['row'], r['status'], r['action']) for r in data['rows']]
        self.assertEqual(statuses, [
            (2, 'ok', 'add'),
            (3, 'warning', 'create_route'),
            (4, 'ok', 'add'),
            (5, 'error', 'none'),
            (6, 'error', 'none'),
        ])
        self.assertEqual(data['totals']['errors'], 2)
        self.assertEqual(data['totals']['new_routes'], 1)

    def test_new_route_only_from_valid_rows(self):
        content = (
            "route_token;position;property_token\n"
            "NOVA1;1;PNOEXIST\n"
            "NOVA2;1;PNOEXIST\n"
            "NOVA2;2;P1\n"
        )
        plan = self.plan(content, 'append')
        data = route_bulk_service.serialize_import_plan(plan)
        self.assertEqual(data['totals']['new_routes'], 1)
        self.assertEqual([(r['row'], r['status'], r['action']) for r in data['rows']], [
            (2, 'error', 'none'),
            (3, 'error', 'none'),
            (4, 'ok', 'create_route'),
        ])
        route_bulk_service.apply_import_plan(plan)
        self.assertFalse(Route.objects.filter(token='NOVA1').exists())
        self.assertTrue(Route.objects.filter(token='NOVA2').exists())

    def test_append_and_own_route(self):
        content = (
            "ruta;posicio;finca;punt\n"
            "M1;10;P1;\n"
            "M1;20;P5;\n"
            "T1;1;;SPX\n"
        )
        result = route_bulk_service.apply_import_plan(self.plan(content, 'append'))
        self.assertEqual(result['positions_created'], 3)
        self.p1.refresh_from_db()
        self.p5.refresh_from_db()
        self.sp.refresh_from_db()
        # Mode afegir: al final de la ruta, mantenint l'ordre del fitxer.
        self.assertEqual(self.p1.route_position.position, 2)
        self.assertEqual(self.p5.route_position.position, 3)
        self.assertEqual(self.sp.route_position.route, self.quarterly)
        self.p_old.refresh_from_db()
        self.assertEqual(self.p_old.route_position, self.old_position)

    def test_replace(self):
        content = "route_token,position,property_token\nM1,4,P1\n"
        route_bulk_service.apply_import_plan(self.plan(content, 'replace'))
        self.p_old.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertIsNone(self.p_old.route_position)
        self.assertFalse(RoutePosition.objects.filter(id=self.old_position.id).exists())
        self.assertEqual(self.p1.route_position.position, 4)
        self.assertEqual(self.p1.route_position.token, 'M1_4')

    def test_xlsx_template_roundtrip(self):
        from openpyxl import load_workbook
        content = route_bulk_service.build_import_template()
        workbook = load_workbook(io.BytesIO(content))
        sheet = workbook.worksheets[0]
        sheet.append(['M1', '', '', '7', 'P1'])
        out = io.BytesIO()
        workbook.save(out)
        out.seek(0)
        out.name = 'rutes.xlsx'
        rows = route_bulk_service.read_import_file(out)
        self.assertEqual(rows, [(2, {
            'route_token': 'M1', 'route_name': '', 'route_zone': '', 'position': '7', 'property_token': 'P1',
            'supply_point_token': '', 'street': '', 'street_number': '', 'notebook': '', 'reader_observation': '',
        })])

    def test_missing_route_column(self):
        with self.assertRaises(ValueError):
            route_bulk_service.read_import_file(_file("position;property_token\n1;P1\n"))

    def test_corrupted_file_hides_internal_error(self):
        broken = io.BytesIO(b'no es un excel')
        broken.name = 'rutes.xlsx'
        with self.assertLogs('service.utils.route_bulk_service', level='ERROR'):
            with self.assertRaises(route_bulk_service.RouteBulkError) as ctx:
                route_bulk_service.read_import_file(broken)
        self.assertEqual(ctx.exception.message, "No s'ha pogut llegir el fitxer. Comprova que no estigui malmès.")


class TestReadingBatchWithOwnRoute(RouteTestMixin, TestCase):
    """Una finca amb un punt trimestral (ruta de la finca) i un de mensual (ruta pròpia)."""

    def setUp(self):
        super().setUp()
        from coredata.models import ConfigProject
        from service.models import Meter, MeterStatus
        ConfigProject.objects.create(token='contract_active_token', value='ACT')
        ConfigProject.objects.create(token='token_meter_status_no_meter', value='NOMETER')
        ConfigProject.objects.create(token='supply_point_status_activate_token', value='1')
        meter_status = MeterStatus.objects.create(token='OK', name='OK')
        self.position = self.make_position(self.quarterly, 1)
        self.prop = self.make_property('P1', 1, self.position)
        self.sp_quarterly = SupplyPoint.objects.create(
            token='SPQ', property=self.prop, meter=Meter.objects.create(code='MQ', status=meter_status))
        self.sp_monthly = SupplyPoint.objects.create(
            token='SPM', property=self.prop, meter=Meter.objects.create(code='MM', status=meter_status))
        route_bulk_service.set_supply_point_route(self.sp_monthly, self.monthly)

    def make_batch(self, route):
        from billing.models import ReadingBatch
        batch = ReadingBatch.objects.create(token=f'B-{route.token}', include_manual=True)
        batch.routes.add(route)
        return batch

    def test_batch_supply_points(self):
        from billing.utils.reading_batch_service import get_batch_supply_point_ids
        self.assertEqual(get_batch_supply_point_ids(self.make_batch(self.quarterly)), {self.sp_quarterly.id})
        self.assertEqual(get_batch_supply_point_ids(self.make_batch(self.monthly)), {self.sp_monthly.id})

    def test_batch_export_walk(self):
        from billing.tasks import _reading_batch_export_row_contexts
        monthly = _reading_batch_export_row_contexts(self.make_batch(self.monthly))
        quarterly = _reading_batch_export_row_contexts(self.make_batch(self.quarterly))
        self.assertEqual([(c['supply_point'].token, c['route_label']) for c in monthly], [('SPM', 'M1')])
        self.assertEqual([(c['supply_point'].token, c['route_label']) for c in quarterly], [('SPQ', 'T1')])

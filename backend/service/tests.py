# service/tests.py
from django.db import connection
from django.core.management import call_command
from django.test import TestCase
from coredata.models import Address
from service.models import SupplyPoint, SupplyPointStatus, Meter, Connection
from contract.models import Contract
from service.utils.supply_point_service import (
    supply_point_activate,
    supply_point_deactivate,
    supply_point_change_meter,
    supply_point_change_connection,
    supply_point_change_address
)
from logger.models import LogSupplyPointChange
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from rest_framework.test import APIRequestFactory, force_authenticate

class TestSupplyPointService(TestCase):

    @classmethod
    def load_fixtures(cls):
        
        # Deshabilitar tots els signals
        from django.db.models.signals import post_save
        from django.dispatch import receiver
        
        
        # Disable debug cursor
        connection.force_debug_cursor = False

        try:
            # Load your fixtures
            call_command('loaddata', 'coredata/fixtures/tests/all_data.json')
            
        finally:
            # Reconnectar el signal
            
            # Re-enable debug cursor
            connection.force_debug_cursor = True

    @classmethod
    def setUpTestData(cls):
        cls.load_fixtures()
        # Intentar recuperar l'usuari de les fixtures
        try:
            cls.user = User.objects.get(username='customers')
        except User.DoesNotExist:
            # Crear l'usuari de prova si no existeix
            cls.user = User.objects.create_user(username='customers', password='customers')

        cls.active_status = SupplyPointStatus.objects.get(token='1')
        cls.inactive_status = SupplyPointStatus.objects.get(token='-1')
        cls.supply_point = SupplyPoint.objects.get(token='29001')

        # Crear metres per a les proves
        cls.previous_meter = Meter.objects.create(code='P19N34567890')
        cls.current_meter = Meter.objects.create(code='P19S89012345')

        # Crear connexions per a les proves
        cls.previous_connection = Connection.objects.create(token='2258797')
        cls.current_connection = Connection.objects.create(token='5548796')

    def test_supply_point_activate(self):
        # Verifica l'estat inicial
        self.supply_point.status = self.inactive_status
        self.supply_point.save()
        
        # Activa el SupplyPoint
        supply_point_activate(self.user, self.supply_point.id)
        
        # Actualitza l'objecte
        self.supply_point.refresh_from_db()
        
        # Assercions
        self.assertEqual(self.supply_point.status, self.active_status)
        
        # Verifica el log
        log = LogSupplyPointChange.objects.get(supply_point=self.supply_point, action='activate')
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.field_changed, 'status')
        self.assertEqual(log.previous_value, self.inactive_status.name)
        self.assertEqual(log.current_value, self.active_status.name)

    def test_supply_point_deactivate(self):
        # Assegura't que el punt d'abast està actiu inicialment
        self.supply_point.status = self.active_status
        self.supply_point.removal_at = None
        self.supply_point.removal_reason = None
        self.supply_point.save()

        # Defineix la data i la raó de desactivació
        removal_date = timezone.now() + timedelta(days=1)
        removal_reason = 'Requested by user'

        # Desactiva el punt d'abast
        updated_supply_point = supply_point_deactivate(
            self.user,
            self.supply_point.id,
            removal_date,
            removal_reason
        )

        # Actualitza l'objecte
        self.supply_point.refresh_from_db()

        # Assercions per verificar l'estat
        self.assertEqual(self.supply_point.status, self.inactive_status)
        self.assertEqual(self.supply_point.removal_reason, removal_reason)

        # Verifica el log
        log = LogSupplyPointChange.objects.get(
            supply_point=self.supply_point,
            action='deactivate'
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.field_changed, 'status')
        self.assertEqual(log.previous_value, self.active_status.name)
        self.assertEqual(log.current_value, self.inactive_status.name)
        self.assertEqual(log.observation, removal_reason)

    def test_supply_point_change_meter(self):
        # Assegura't que els meters inicials estan correctament configurats
        self.assertEqual(self.previous_meter.code, 'P19N34567890')
        self.assertEqual(self.current_meter.code, 'P19S89012345')
        
        # Guardar log meter
        supply_point_change_meter(
            self.user,
            self.supply_point.id,
            self.previous_meter,
            self.current_meter
        )
        
        # Verifica el log
        log = LogSupplyPointChange.objects.get(
            supply_point=self.supply_point,
            action='meter'
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.field_changed, 'meter')
        self.assertEqual(log.previous_value, self.previous_meter.code)
        self.assertEqual(log.current_value, self.current_meter.code)
        self.assertEqual(log.previous_related_id, self.previous_meter.id)
        self.assertEqual(log.current_related_id, self.current_meter.id)
        self.assertIsNone(log.observation)

    def test_supply_point_change_connection(self):
        # Assegura't que les connexions inicials estan correctament configurades
        self.assertEqual(self.previous_connection.token, '2258797')
        self.assertEqual(self.current_connection.token, '5548796')

        # Assigna la connexió inicial al SupplyPoint
        self.supply_point.connection = self.previous_connection
        self.supply_point.save()

        # Canvia la connexió
        supply_point_change_connection(
            self.user,
            self.supply_point.id,
            self.previous_connection,
            self.current_connection
        )

        # Actualitza l'objecte
        self.supply_point.refresh_from_db()

        # Verifica el log
        log = LogSupplyPointChange.objects.get(
            supply_point=self.supply_point,
            action='connection'
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.field_changed, 'connection')
        self.assertEqual(log.previous_value, self.previous_connection.token)
        self.assertEqual(log.current_value, self.current_connection.token)
        self.assertEqual(log.previous_related_id, self.previous_connection.id)
        self.assertEqual(log.current_related_id, self.current_connection.id)
        self.assertIsNone(log.observation)

    def test_supply_point_change_address(self):
        # Defineix les adreces inicials i finals
        previous_address = self.supply_point.address
        current_address = Address.objects.get(id=11)

        # Canvia l'adreça
        supply_point_change_address(
            self.user,
            self.supply_point.id,
            previous_address,
            current_address
        )
        
        # Verifica el log
        log = LogSupplyPointChange.objects.get(
            supply_point=self.supply_point,
            action='address'
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.field_changed, 'address')
        self.assertEqual(log.previous_value, str(previous_address))
        self.assertEqual(log.current_value, str(current_address))
        self.assertIsNone(log.previous_related_id)
        self.assertIsNone(log.current_related_id)
        self.assertIsNone(log.observation)

    def test_bulk_update_property(self):
        from service.models import Property
        from service.views.supply_point_view import SupplyPointViewSet
        from rest_framework.test import APIRequestFactory, force_authenticate

        # Grant superuser permission to the test user so the permission checks pass.
        self.user.is_superuser = True
        self.user.save()

        # Create two properties
        prop1 = Property.objects.create(name="Property Test 1")
        prop2 = Property.objects.create(name="Property Test 2")

        # Create supply points
        sp1 = SupplyPoint.objects.create(token="SP_TEST_1", property=prop1)
        sp2 = SupplyPoint.objects.create(token="SP_TEST_2", property=prop1)
        sp3 = SupplyPoint.objects.create(token="SP_TEST_3", property=prop2)

        # Call bulk-update-property to keep sp1 on prop1, remove sp2 from prop1, and add sp3 to prop1.
        factory = APIRequestFactory()
        view = SupplyPointViewSet.as_view({'post': 'bulk_update_property'})

        data = [
            {
                "property_id": prop1.id,
                "supply_points": [sp1.id, sp3.id]
            }
        ]

        request = factory.post('/service/supply-point/bulk-update-property/', data, format='json')
        force_authenticate(request, user=self.user)
        response = view(request)

        self.assertEqual(response.status_code, 200)

        # Refresh from database
        sp1.refresh_from_db()
        sp2.refresh_from_db()
        sp3.refresh_from_db()

        # Assert property associations
        self.assertEqual(sp1.property_id, prop1.id)  # Unchanged
        self.assertIsNone(sp2.property)              # Unlinked
        self.assertEqual(sp3.property_id, prop1.id)  # Linked to prop1

        # Check logs
        # sp2 should have an unlink log
        log_sp2 = LogSupplyPointChange.objects.filter(supply_point=sp2, action='property').first()
        self.assertIsNotNone(log_sp2)
        self.assertEqual(log_sp2.previous_related_id, prop1.id)
        self.assertIsNone(log_sp2.current_related_id)

        # sp3 should have a link log
        log_sp3 = LogSupplyPointChange.objects.filter(supply_point=sp3, action='property').first()
        self.assertIsNotNone(log_sp3)
        self.assertEqual(log_sp3.previous_related_id, prop2.id)
        self.assertEqual(log_sp3.current_related_id, prop1.id)

        # sp1 should NOT have a log because its property association did not change
        log_sp1 = LogSupplyPointChange.objects.filter(supply_point=sp1, action='property').first()
        self.assertIsNone(log_sp1)

    def test_supply_point_list_ordering(self):
        from service.views.supply_point_view import SupplyPointViewSet
        from rest_framework.test import APIRequestFactory, force_authenticate

        self.user.is_superuser = True
        self.user.save()

        factory = APIRequestFactory()
        view = SupplyPointViewSet.as_view({'get': 'list'})

        # Test ordering by address_complete
        request = factory.get('/service/supply-point/', {'ordering': 'address_complete'})
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)

        # Test ordering by address_city
        request = factory.get('/service/supply-point/', {'ordering': 'address_city'})
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_property_list_serializer_route_fields(self):
        from service.models import Property, Route, RoutePosition
        from service.serializers.property_serializer import PropertyListSerializer

        route = Route.objects.create(token="ROUTE_TEST", name="Test Route")
        route_pos = RoutePosition.objects.create(route=route, position=42, token="RP_TEST")
        prop = Property.objects.create(name="Property with route", route_position=route_pos)

        serializer = PropertyListSerializer(prop)
        data = serializer.data

        self.assertIn('route', data)
        self.assertIsNotNone(data['route'])
        self.assertEqual(data['route']['id'], route.id)
        self.assertEqual(data['route']['token'], "ROUTE_TEST")
        self.assertEqual(data['route']['name'], "Test Route")
        
        self.assertIn('route_position', data)
        self.assertEqual(data['route_position'], 42)


class TestMeterLog(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.status_actiu = MeterStatus.objects.create(token='actiu', name='Actiu')
        self.status_baixa = MeterStatus.objects.create(token='baixa', name='Baixa')

    def test_meter_create_and_update_logs(self):
        from service.middleware import set_current_user
        from service.models import MeterLog
        from rest_framework.test import APIRequestFactory, force_authenticate
        from service.views.meter_view import MeterViewSet

        set_current_user(self.user)
        try:
            # 1. Test create log
            meter = Meter.objects.create(code='M12345', status=self.status_actiu)
            create_log = MeterLog.objects.filter(meter=meter, operation_token='create').first()
            self.assertIsNotNone(create_log)
            self.assertEqual(create_log.user, self.user)

            # 2. Test update log
            meter.status = self.status_baixa
            meter.save()
        finally:
            set_current_user(None)

        update_log = MeterLog.objects.filter(meter=meter, field_name='status').first()
        self.assertIsNotNone(update_log)
        self.assertEqual(update_log.user, self.user)

        # 3. Test ViewSet Logs Action Endpoint
        factory = APIRequestFactory()
        view = MeterViewSet.as_view({'get': 'logs'})
        request = factory.get(f'/service/meter/{meter.id}/logs/')
        force_authenticate(request, user=self.user)
        response = view(request, pk=meter.id)

        self.assertEqual(response.status_code, 200)
        logs_data = response.data
        self.assertEqual(len(logs_data), 2)  # One for create, one for status update
        
        # Check update log serialization format
        update_log_data = next(item for item in logs_data if item['field_name'] == 'status_name')
        self.assertEqual(update_log_data['operation_token'], 'update')
        self.assertEqual(update_log_data['old_value'], 'Actiu')
        self.assertEqual(update_log_data['new_value'], 'Baixa')
        self.assertEqual(update_log_data['user']['username'], 'testuser')

        # Check create log serialization format
        create_log_data = next(item for item in logs_data if item['operation_token'] == 'create')
        self.assertIsNone(create_log_data['field_name'])
        self.assertIsNone(create_log_data['old_value'])
        self.assertIsNone(create_log_data['new_value'])
        self.assertEqual(create_log_data['user']['username'], 'testuser')


class TestSupplyCutTerminalStatuses(TestCase):

    @classmethod
    def setUpTestData(cls):
        from coredata.models import ConfigProject
        from service.models import SupplyCutStatus, SupplyPoint, SupplyPointStatus

        cls.active_pt_status = SupplyPointStatus.objects.create(token='1', name='Actiu', color='green')
        cls.cut_pt_status = SupplyPointStatus.objects.create(token='tallat', name='Tallat', color='red')

        cls.planned_cut_status = SupplyCutStatus.objects.create(token='0', name='Planificat')
        cls.finished_cut_status = SupplyCutStatus.objects.create(token='2', name='Acabat')
        cls.cancelled_cut_status = SupplyCutStatus.objects.create(token='3', name='Cancel·lat')
        cls.open_cut_status = SupplyCutStatus.objects.create(token='1', name='Actiu')

        ConfigProject.objects.update_or_create(
            token='supply_cut_status_closed_tokens',
            defaults={'name': 'Terminal supply cut status tokens', 'value': '2,3'},
        )
        ConfigProject.objects.get_or_create(
            token='supply_point_status_cut_token',
            defaults={'name': 'Token Supply Point Status Cut', 'value': 'tallat'},
        )
        ConfigProject.objects.get_or_create(
            token='supply_point_status_activate_token',
            defaults={'name': 'Estat del Punt de Subministrament quan està actiu', 'value': '1'},
        )

        cls.supply_point = SupplyPoint.objects.create(token='test-sp', status=cls.cut_pt_status)

    def _given_cut(self, status):
        from service.models import SupplyCut
        cut = SupplyCut.objects.create(token=f'test-cut-{status.token}', status=status)
        cut.supply_points.set([self.supply_point])
        return cut

    def _sync(self, previous_status, cut):
        from types import SimpleNamespace
        from service.serializers.supply_cut_serializer import SupplyCutSerializer
        serializer = SupplyCutSerializer(context={'request': SimpleNamespace(user=None)})
        serializer._sync_supply_points_status(previous_status, cut)

    def test_enter_terminal_status_restores_points(self):
        cut = self._given_cut(self.planned_cut_status)

        cut.status = self.finished_cut_status
        cut.save()
        self._sync(self.planned_cut_status, cut)

        self.supply_point.refresh_from_db()
        self.assertEqual(self.supply_point.status, self.active_pt_status)

    def test_terminal_to_terminal_keeps_points_active(self):
        cut = self._given_cut(self.planned_cut_status)
        cut.status = self.finished_cut_status
        cut.save()
        self._sync(self.planned_cut_status, cut)

        cut.status = self.cancelled_cut_status
        cut.save()
        self._sync(self.finished_cut_status, cut)

        self.supply_point.refresh_from_db()
        self.assertEqual(self.supply_point.status, self.active_pt_status)

    def test_terminal_to_open_recuts_points(self):
        cut = self._given_cut(self.planned_cut_status)
        cut.status = self.cancelled_cut_status
        cut.save()
        self._sync(self.planned_cut_status, cut)

        cut.status = self.open_cut_status
        cut.save()
        self._sync(self.cancelled_cut_status, cut)

        self.supply_point.refresh_from_db()
        self.assertEqual(self.supply_point.status, self.cut_pt_status)

    def test_is_supply_cut_closed_for_terminal_statuses(self):
        from service.utils import supply_cut_service
        for status in (self.finished_cut_status, self.cancelled_cut_status):
            cut = self._given_cut(status)
            self.assertTrue(supply_cut_service.is_supply_cut_closed(cut))
        for status in (self.planned_cut_status, self.open_cut_status):
            cut = self._given_cut(status)
            self.assertFalse(supply_cut_service.is_supply_cut_closed(cut))


class TestSupplyCutSerializerNPlusOne(TestCase):

    @classmethod
    def setUpTestData(cls):
        from service.models import SupplyCutStatus, SupplyPointStatus
        cls.cut_status = SupplyCutStatus.objects.create(token='pendent', name='pendent')
        cls.pt_status = SupplyPointStatus.objects.create(token='1', name='Actiu', color='green')

    def _build_cut(self, count):
        from service.models import SupplyCut, SupplyPoint
        cut = SupplyCut.objects.create(token=f'test-cut-{count}', status=self.cut_status)
        points = [
            SupplyPoint.objects.create(token=f'test-sp-{count}-{i}', status=self.pt_status)
            for i in range(count)
        ]
        cut.supply_points.set(points)
        return cut

    def _serialize_query_count(self, cut):
        from types import SimpleNamespace
        from django.test.utils import CaptureQueriesContext
        from service.serializers.supply_cut_serializer import SupplyCutSerializer
        with CaptureQueriesContext(connection) as captured:
            SupplyCutSerializer(cut, context={'request': SimpleNamespace(user=None)}).data
        return len(captured)

    def test_cut_detail_queries_do_not_scale_with_supply_point_count(self):
        small_count = self._serialize_query_count(self._build_cut(3))
        large_count = self._serialize_query_count(self._build_cut(6))
        self.assertEqual(small_count, large_count)
        self.assertLessEqual(large_count, 12)


class TestSupplyCutListSortingAndStatusFilter(TestCase):

    @classmethod
    def setUpTestData(cls):
        from service.models import SupplyCut, SupplyCutStatus
        from service.views.supply_cut_view import SupplyCutViewSet

        cls.factory = APIRequestFactory()
        cls.view = SupplyCutViewSet.as_view({'get': 'simple_list'})
        cls.user = User.objects.create_superuser(username='cutlist', password='p', email='cutlist@example.com')

        cls.status_alfa = SupplyCutStatus.objects.create(token='alfa', name='Alfa', color='green')
        cls.status_beta = SupplyCutStatus.objects.create(token='beta', name='Beta', color='yellow')
        cls.status_gamma = SupplyCutStatus.objects.create(token='gamma', name='Gamma', color='red')

        now = timezone.now()
        # date_end is the default list ordering; deliberately NOT aligned
        # with id so sorting checks are meaningful.
        cls.cut_late = SupplyCut.objects.create(
            token='cut-late', status=cls.status_alfa, date_end=now + timedelta(days=3)
        )
        cls.cut_mid = SupplyCut.objects.create(
            token='cut-mid', status=cls.status_beta, date_end=now + timedelta(days=1)
        )
        cls.cut_early = SupplyCut.objects.create(
            token='cut-early', status=cls.status_gamma, date_end=now
        )

    def _list(self, params):
        request = self.factory.get('/service/supply-cut/list/', params)
        force_authenticate(request, user=self.user)
        return self.view(request)

    def test_sorting_by_id_is_applied(self):
        plain_ids = [item['id'] for item in self._list({}).data['results']]
        asc_ids = [item['id'] for item in self._list({'ordering': 'id'}).data['results']]
        desc_ids = [item['id'] for item in self._list({'ordering': '-id'}).data['results']]

        self.assertEqual(asc_ids, sorted(plain_ids))
        self.assertEqual(desc_ids, sorted(plain_ids, reverse=True))

    def test_sorting_by_status_name_is_applied(self):
        asc = self._list({'ordering': 'status_name'})
        self.assertEqual(asc.status_code, 200)
        self.assertEqual([item['status_name'] for item in asc.data['results']], ['Alfa', 'Beta', 'Gamma'])

        desc = self._list({'ordering': '-status_name'})
        self.assertEqual(desc.status_code, 200)
        self.assertEqual([item['status_name'] for item in desc.data['results']], ['Gamma', 'Beta', 'Alfa'])

    def test_status_filter_by_ids(self):
        ids = f"{self.status_alfa.id},{self.status_beta.id}"
        response = self._list({'status': ids})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item['id'] for item in response.data['results']},
            {self.cut_late.id, self.cut_mid.id},
        )

    def test_status_filter_accepts_names_and_tokens_without_500(self):
        for value in ('Alfa', 'alfa', 'does-not-exist'):
            response = self._list({'status': value})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self._list({'status': 'Alfa'}).data['count'], 1)
        self.assertEqual(self._list({'status': 'alfa'}).data['count'], 1)
        self.assertEqual(self._list({'status': 'does-not-exist'}).data['count'], 0)


class TestSupplyCutCatalogResolution(TestCase):
    """Never-mint / mapa-first: la sync de Giswater NOMÉS resol amb els mapes de
    ConfigProject, MAI encunya catàleg; els valors buits no generen revisió; una
    correcció manual sobreviu a la sync; els talls en quarantena MAI arriben als
    buckets d'auto-activació/tancament; el comandament review_supply_cuts resol
    només allò mapejable.
    """

    @classmethod
    def setUpTestData(cls):
        from coredata.models import ConfigProject
        from service.models import SupplyCutCause, SupplyCutStatus

        # El catàleg d'Estats ja el sembra la migració 0126 (token '1' Actiu);
        # s'agafa, no es duplica.
        cls.status_open = SupplyCutStatus.objects.get(token='1', name='Actiu')
        cls.status_pending = SupplyCutStatus.objects.create(token='pendent', name='pendent')
        cls.cause_accidental = SupplyCutCause.objects.create(token='9', name='Accidental')

        for token, value in (
            ('supply_cut_status_active_token', '1'),
            ('supply_cut_status_closed_tokens', '2,3'),
        ):
            ConfigProject.objects.get_or_create(
                token=token,
                defaults={'name': token, 'value': value},
            )

    def test_empty_values_do_not_quarantine(self):
        from integrations.outbound.giswater.sync import _resolve_catalog_with_map
        for value in (None, '', '   '):
            resolved, ok = _resolve_catalog_with_map({}, None, value)
            self.assertIsNone(resolved)
            self.assertTrue(ok)

    def test_unmapped_values_are_unresolved_and_never_mint(self):
        from integrations.outbound.giswater.sync import _resolve_catalog_with_map
        from service.models import SupplyCutStatus
        count_before = SupplyCutStatus.objects.count()
        resolved, ok = _resolve_catalog_with_map({'1': '1'}, SupplyCutStatus, '42')
        self.assertIsNone(resolved)
        self.assertFalse(ok)
        resolved, ok = _resolve_catalog_with_map({'999': '999'}, SupplyCutStatus, '999')
        self.assertIsNone(resolved)
        self.assertFalse(ok)
        self.assertEqual(SupplyCutStatus.objects.count(), count_before)

    def test_mapped_value_resolves_to_existing_catalog_row(self):
        from integrations.outbound.giswater.sync import _resolve_catalog_with_map
        from service.models import SupplyCutStatus
        resolved, ok = _resolve_catalog_with_map({'1': '1'}, SupplyCutStatus, '1')
        self.assertEqual(resolved, self.status_open)
        self.assertTrue(ok)
        resolved, ok = _resolve_catalog_with_map({'Actiu': '1'}, SupplyCutStatus, 'Actiu')
        self.assertEqual(resolved, self.status_open)
        self.assertTrue(ok)

    def test_quarantined_cuts_never_reach_auto_buckets(self):
        from service.models import SupplyCut
        from service.utils import supply_cut_service

        now = timezone.now()
        quarantined = SupplyCut.objects.create(
            token='gw-q', source='giswater', status=self.status_pending,
            requires_review=True,
            exec_start=now - timedelta(days=1),
            exec_end=now - timedelta(days=1),
        )
        resolved_cut = SupplyCut.objects.create(
            token='gw-ok', source='giswater', status=self.status_pending,
            requires_review=False,
            exec_start=now - timedelta(days=1),
        )

        self.assertNotIn(quarantined, supply_cut_service.supply_cuts_due_to_activate())
        self.assertNotIn(quarantined, supply_cut_service.supply_cuts_due_to_deactivate())
        self.assertIn(resolved_cut, supply_cut_service.supply_cuts_due_to_activate())

    def test_sync_respects_manual_fix(self):
        import json
        from unittest.mock import patch

        from coredata.models import ConfigProject
        from integrations.outbound.giswater import sync as sync_mod
        from service.models import SupplyCut

        ConfigProject.objects.update_or_create(
            token='giswater_mincut_state_map',
            defaults={'name': 'estat', 'value': json.dumps({'1': '1'})},
        )
        ConfigProject.objects.update_or_create(
            token='giswater_mincut_cause_map',
            defaults={'name': 'motiu', 'value': json.dumps({})},
        )

        manual = SupplyCut.objects.create(
            token='777', cause=self.cause_accidental, status=self.status_open,
            cause_raw='Accidental', state_raw='1', requires_review=False,
        )
        payload = [
            {'id': '777', 'anl_cause': 'Accidental', 'state': '1'},
            {'id': '778', 'anl_cause': 'Accidental', 'state': '1'},
        ]
        with patch.object(sync_mod, 'fetch_om_mincuts', return_value=payload), \
             patch.object(sync_mod, 'extract_fields', side_effect=lambda r: r), \
             patch.object(sync_mod, 'fetch_om_mincut_connecs', return_value=[]):
            sync_mod.sync_supply_cuts_from_giswater()

        manual.refresh_from_db()
        self.assertFalse(manual.requires_review)
        self.assertEqual(manual.cause, self.cause_accidental)
        self.assertEqual(manual.status, self.status_open)

        quarantined = SupplyCut.objects.get(token='778')
        self.assertTrue(quarantined.requires_review)
        self.assertIsNone(quarantined.cause)
        self.assertEqual(quarantined.status, self.status_open)
        self.assertEqual(quarantined.cause_raw, 'Accidental')
        self.assertEqual(quarantined.state_raw, '1')

    def test_review_command_commit_resolves_only_mappable(self):
        import json
        from coredata.models import ConfigProject
        from service.models import SupplyCut
        from django.core.management import call_command

        ConfigProject.objects.update_or_create(
            token='giswater_mincut_state_map',
            defaults={'name': 'estat', 'value': json.dumps({'1': '1'})},
        )
        ConfigProject.objects.update_or_create(
            token='giswater_mincut_cause_map',
            defaults={'name': 'motiu', 'value': json.dumps({'Accidental': '9'})},
        )

        mappable = SupplyCut.objects.create(
            token='gw-a', source='giswater', requires_review=True,
            cause_raw='Accidental', state_raw='1',
        )
        unmappable = SupplyCut.objects.create(
            token='gw-b', source='giswater', requires_review=True,
            cause_raw='ALTRES', state_raw='4',
        )

        call_command('review_supply_cuts', '--commit')

        mappable.refresh_from_db()
        self.assertFalse(mappable.requires_review)
        self.assertEqual(mappable.cause, self.cause_accidental)
        self.assertEqual(mappable.status, self.status_open)
        self.assertEqual(mappable.mincut_cause_token, '9')
        self.assertEqual(mappable.mincut_state_token, '1')

        unmappable.refresh_from_db()
        self.assertTrue(unmappable.requires_review)
        self.assertIsNone(unmappable.cause)
        self.assertIsNone(unmappable.status)
        self.assertEqual(unmappable.cause_raw, 'ALTRES')
        self.assertEqual(unmappable.state_raw, '4')

    def test_review_command_refresh_restores_canonical_maps(self):
        import json
        from coredata.models import ConfigProject
        from integrations.outbound.giswater.sync import _load_mincut_config_maps
        from service.management.commands.review_supply_cuts import (
            EXPLICIT_CAUSE_MAP,
            EXPLICIT_STATE_MAP,
        )
        from service.models import SupplyCutStatus
        from django.core.management import call_command

        ConfigProject.objects.update_or_create(
            token='giswater_mincut_state_map',
            defaults={'name': 'estat', 'value': json.dumps({'corromput': 'x'})},
        )
        ConfigProject.objects.update_or_create(
            token='giswater_mincut_cause_map',
            defaults={'name': 'motiu', 'value': json.dumps({'corromput': 'x'})},
        )
        SupplyCutStatus.objects.create(token='nova5', name='NouEstat')

        call_command('review_supply_cuts', '--refresh')

        maps = _load_mincut_config_maps()
        self.assertEqual(maps['giswater_mincut_state_map'], EXPLICIT_STATE_MAP)
        self.assertEqual(maps['giswater_mincut_cause_map'], EXPLICIT_CAUSE_MAP)
        self.assertNotIn('nova5', maps['giswater_mincut_state_map'])
        self.assertNotIn('NouEstat', maps['giswater_mincut_state_map'])

    def test_review_command_empty_raws_are_resolvable(self):
        from service.models import SupplyCut
        from django.core.management import call_command

        cut = SupplyCut.objects.create(
            token='gw-c', source='giswater', requires_review=True,
            cause_raw='', state_raw=None,
        )
        call_command('review_supply_cuts', '--commit')
        cut.refresh_from_db()
        self.assertFalse(cut.requires_review)
        self.assertIsNone(cut.cause)
        self.assertIsNone(cut.status)

    def test_list_serializer_exposes_requires_review(self):
        from service.models import SupplyCut
        from service.serializers.supply_cut_serializer import SupplyCutMinimalSerializer
        cut = SupplyCut.objects.create(
            token='gw-s', source='giswater', requires_review=True,
        )
        data = SupplyCutMinimalSerializer(cut).data
        self.assertTrue(data['requires_review'])


class TestSupplyCutSyncConflicteFlag(TestCase):
    """Fase 2: l'estat «Conflicte» (token 5) del catàleg resol la FK però
    s'auto-marca requires_review=True; «Accidental» resol cap al motiu propi
    del catàleg (is_temporary). Els mapes són els canònics de la 0126."""

    def test_sync_conflicte_resolves_and_flags(self):
        import json
        from unittest.mock import patch

        from coredata.models import ConfigProject
        from integrations.outbound.giswater import sync as sync_mod
        from service.models import SupplyCut

        ConfigProject.objects.update_or_create(
            token='giswater_mincut_state_map',
            defaults={'name': 'estat',
                      'value': json.dumps({'5': '5', 'Conflicte': '5', '1': '1'})},
        )
        ConfigProject.objects.update_or_create(
            token='giswater_mincut_cause_map',
            defaults={'name': 'motiu',
                      'value': json.dumps({'1': 'Accidental', 'Accidental': 'Accidental'})},
        )

        payload = [
            {'id': 'c1', 'anl_cause': 'Accidental', 'state': 'Conflicte'},
            {'id': 'c2', 'anl_cause': 'Accidental', 'state': '1'},
        ]
        with patch.object(sync_mod, 'fetch_om_mincuts', return_value=payload), \
             patch.object(sync_mod, 'extract_fields', side_effect=lambda r: r), \
             patch.object(sync_mod, 'fetch_om_mincut_connecs', return_value=[]):
            sync_mod.sync_supply_cuts_from_giswater()

        conflicte = SupplyCut.objects.get(token='c1')
        self.assertEqual(conflicte.status.token, '5')
        self.assertTrue(conflicte.requires_review)
        self.assertEqual(conflicte.mincut_state_token, '5')
        self.assertEqual(conflicte.cause.token, 'Accidental')
        self.assertTrue(conflicte.cause.is_temporary)

        normal = SupplyCut.objects.get(token='c2')
        self.assertEqual(normal.status.token, '1')
        self.assertFalse(normal.requires_review)
        self.assertEqual(normal.cause.token, 'Accidental')

    def test_never_finished_is_prevented_from_sync_buckets(self):
        from coredata.models import ConfigProject
        from service.models import SupplyCut
        from service.utils import supply_cut_service
        from django.utils import timezone as tz

        ConfigProject.objects.update_or_create(
            token='supply_cut_status_active_token',
            defaults={'name': 'actiu', 'value': '1'},
        )
        now = tz.now()

        conflicte = SupplyCut.objects.create(
            token='c3', source='giswater',
            status_id=self._status_for('5').id,
            cause_raw='Accidental', state_raw='Conflicte', requires_review=True,
            exec_start=now - tz.timedelta(days=1), exec_end=now - tz.timedelta(days=1),
        )
        self.assertNotIn(conflicte, supply_cut_service.supply_cuts_due_to_activate())
        self.assertNotIn(conflicte, supply_cut_service.supply_cuts_due_to_deactivate())
        self.assertTrue(SupplyCut.objects.get(token='c3').requires_review)

    @staticmethod
    def _status_for(token):
        from service.models import SupplyCutStatus
        return SupplyCutStatus.objects.get(token=token)


class TestSupplyCutCauseAwarePropagation(TestCase):
    """Fase 3: només els talls INDEFINITS i fora de quarantena alteren l'estat
    del punt de subministrament; el canvi d'estat és state-driven (Actiu talla,
    terminal restaura, Conflicte és inert) i les transicions segueixen la
    màquina d'estats centralitzada."""

    @classmethod
    def setUpTestData(cls):
        from coredata.models import ConfigProject
        from service.models import SupplyCutCause, SupplyCutStatus, SupplyPoint, SupplyPointStatus

        cls.active_pt = SupplyPointStatus.objects.create(token='1', name='Actiu', color='green')
        cls.cut_pt = SupplyPointStatus.objects.create(token='tallat', name='Tallat', color='red')
        cls.sp = SupplyPoint.objects.create(token='sp-prop', status=cls.active_pt)

        ConfigProject.objects.update_or_create(
            token='supply_point_status_cut_token',
            defaults={'name': 'cut', 'value': 'tallat'},
        )
        ConfigProject.objects.update_or_create(
            token='supply_point_status_activate_token',
            defaults={'name': 'active', 'value': '1'},
        )
        ConfigProject.objects.update_or_create(
            token='supply_cut_status_active_token',
            defaults={'name': 'active', 'value': '1'},
        )
        ConfigProject.objects.update_or_create(
            token='supply_cut_status_closed_tokens',
            defaults={'name': 'closed', 'value': '2,3'},
        )

        cls.indefinite = SupplyCutCause.objects.get(token='0')          # Altres: NO temporal
        cls.temporary = SupplyCutCause.objects.get(token='4')           # Manteniment: temporal
        cls.accidental = SupplyCutCause.objects.get(token='Accidental')
        cls.status_planned = SupplyCutStatus.objects.get(token='0')
        cls.status_active = SupplyCutStatus.objects.get(token='1')
        cls.status_finished = SupplyCutStatus.objects.get(token='2')
        cls.status_cancelled = SupplyCutStatus.objects.get(token='3')

    @staticmethod
    def _build_cut(cause, status_token='0', **extra):
        from service.models import SupplyCut, SupplyCutStatus
        cut = SupplyCut.objects.create(
            token='sp-cut',
            cause=cause,
            status_id=SupplyCutStatus.objects.get(token=status_token).id,
            **extra,
        )
        cut.supply_points.set([TestSupplyCutCauseAwarePropagation.sp])
        return cut

    def _sync(self, previous, cut):
        from types import SimpleNamespace
        from service.serializers.supply_cut_serializer import SupplyCutSerializer
        SupplyCutSerializer(context={'request': SimpleNamespace(user=None)})._sync_supply_points_status(previous, cut)

    def test_temporary_cut_entering_active_does_not_cut_sp(self):
        cut = self._build_cut(self.temporary)
        cut.status = self.status_active
        self._sync(self.status_planned, cut)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

    def test_indefinite_cut_entering_active_cuts_sp(self):
        cut = self._build_cut(self.indefinite)
        cut.status = self.status_active
        self._sync(self.status_planned, cut)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt)

    def test_active_to_finished_restores_sp(self):
        cut = self._build_cut(self.indefinite)
        cut.status = self.status_active
        self._sync(self.status_planned, cut)
        cut.status = self.status_finished
        self._sync(self.status_active, cut)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

    def test_planned_to_cancelled_restores_without_dates(self):
        cut = self._build_cut(self.indefinite)
        cut.status = self.status_cancelled
        self._sync(self.status_planned, cut)
        cut.refresh_from_db()
        self.assertIsNone(cut.exec_end, "Un pla cancel·lat no registra execució.")
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

    def test_active_to_cancelled_allowed_and_restores(self):
        cut = self._build_cut(self.indefinite)
        cut.status = self.status_active
        self._sync(self.status_planned, cut)
        cut.status = self.status_cancelled
        self._sync(self.status_active, cut)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

    def test_serializer_rejects_invalid_transitions(self):
        from service.serializers.supply_cut_serializer import SupplyCutSerializer

        cancelled = self._build_cut(self.indefinite, status_token='3')
        invalid = SupplyCutSerializer(cancelled, data={'status': self.status_active.id}, partial=True)
        self.assertFalse(invalid.is_valid())
        self.assertIn('status', invalid.errors)

        planned = self._build_cut(self.indefinite, status_token='0')
        to_finished = SupplyCutSerializer(planned, data={'status': self.status_finished.id}, partial=True)
        self.assertFalse(to_finished.is_valid(), "Un pla no pot passar a Acabat sense estat Actiu.")
        self.assertIn('status', to_finished.errors)

        active = self._build_cut(self.indefinite, status_token='1')
        to_conflicte = SupplyCutSerializer(active, data={'status': self.status_cancelled.id}, partial=True)
        self.assertTrue(to_conflicte.is_valid())

    def test_notifiable_temporary_requires_date_end_manual(self):
        from service.serializers.supply_cut_serializer import SupplyCutSerializer
        from service.models import SupplyCutCause

        # Manteniment (temporal, no accidental) → data de fi obligatòria.
        without_end = SupplyCutSerializer(data={'token': 'm1', 'cause_id': self.temporary.id})
        self.assertFalse(without_end.is_valid())
        self.assertIn('date_end', without_end.errors)

        with_end = SupplyCutSerializer(data={
            'token': 'm2', 'cause_id': self.temporary.id, 'date_end': '2026-12-31T00:00:00Z',
        })
        self.assertTrue(with_end.is_valid())

    def test_gis_accidental_does_not_require_date_end(self):
        from service.serializers.supply_cut_serializer import SupplyCutSerializer
        accidental = SupplyCutSerializer(data={
            'token': 'acc-1', 'source': 'giswater', 'cause_id': self.accidental.id,
        })
        self.assertTrue(accidental.is_valid(), accidental.errors)

    def test_create_does_not_cut_points(self):
        from service.serializers.supply_cut_serializer import SupplyCutSerializer
        serializer = SupplyCutSerializer(
            data={'token': 'born-planned-2', 'cause_id': self.indefinite.id, 'supply_points': [self.sp.id]},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        cut = serializer.save()
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '0')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt, "Neix Planificat: no talla.")

    # -- Canvi de motiu amb el tall ACTIU (mateix estat) -------------------
    # Un tall ACTIU temporal no talla, però si el motiu passa a indefinit el
    # PP s'ha de tallar (operaris de manteniment que hi troben un problema de
    # seguretat); i a l'inrevés, un indefinit que passa a puntual deixa de
    # mantenir-lo tallat. Es prova per la via del serializer (update), que és
    # on es captura el motiu anterior.

    @staticmethod
    def _put_cause(cut, cause_id, **extra):
        from types import SimpleNamespace
        from service.serializers.supply_cut_serializer import SupplyCutSerializer
        payload = {'cause_id': str(cause_id), **extra}
        serializer = SupplyCutSerializer(
            cut, data=payload, partial=True,
            context={'request': SimpleNamespace(user=None)},
        )
        if not serializer.is_valid():
            raise AssertionError(f"Payload invàlid: {serializer.errors}")
        return serializer.save()

    def test_active_temporary_reason_to_indefinite_cuts_sp(self):
        from datetime import timedelta
        from django.utils import timezone

        cut = self._build_cut(self.temporary, date_end=timezone.now() + timedelta(days=1))
        cut.status = self.status_active
        self._sync(self.status_planned, cut)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

        self._put_cause(cut, self.indefinite.id)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt, "Motiu indefinit: el PP s'ha de tallar.")

    def test_active_indefinite_reason_to_temporary_restores_sp(self):
        from datetime import timedelta
        from django.utils import timezone

        cut = self._build_cut(self.indefinite)
        cut.status = self.status_active
        self._sync(self.status_planned, cut)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt)

        self._put_cause(cut, self.temporary.id, date_end=timezone.now() + timedelta(days=1))
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt, "Motiu puntual: el PP s'ha de restaurar.")

    def test_active_reason_flip_restore_blocked_by_other_open_cut(self):
        from datetime import timedelta
        from django.utils import timezone

        keeper = self._build_cut(self.indefinite)
        keeper.status = self.status_active
        keeper.save(update_fields=['status', 'updated_at'])
        self._sync(self.status_planned, keeper)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt)

        flip = self._build_cut(self.indefinite)
        flip.status = self.status_active
        flip.save(update_fields=['status', 'updated_at'])
        self._sync(self.status_planned, flip)

        self._put_cause(flip, self.temporary.id, date_end=timezone.now() + timedelta(days=1))
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt, "Un altre tall ACTIU indefinit encara el talla.")

        self._put_cause(keeper, self.temporary.id, date_end=timezone.now() + timedelta(days=2))
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt, "Sense talls indefinits oberts: restaura.")

    def test_planned_reason_flip_does_not_touch_sp(self):
        cut = self._build_cut(self.temporary, status_token='0', date_end='2026-12-31T00:00:00Z')
        self._put_cause(cut, self.indefinite.id)
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '0')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt, "Planificat: mai toca els PP.")


class TestSupplyCutCatalogFinalState(TestCase):
    """Estat final del catàleg i la config (migració 0126), que el test DB hereta
    en construir-se des de les migracions: estats 0/1/2/3/5 (Conflicte amb
    requires_review), motius 0..5 + Accidental/Planificada (is_temporary),
    config pendent/innactive eliminada, tancats = {2, 3} i mapes explícits."""

    def test_canonical_status_catalog(self):
        from service.models import SupplyCutStatus

        tokens = {s.token: s for s in SupplyCutStatus.objects.all()}
        self.assertEqual(
            set(tokens),
            {'0', '1', '2', '3', '5'},
            "El catàleg d'estats ha de ser 0/1/2/3/5.",
        )
        self.assertTrue(tokens['5'].requires_review)
        for token in ('0', '1', '2', '3'):
            self.assertFalse(tokens[token].requires_review)
        self.assertTrue(tokens['1'].is_default)

    def test_temporary_causes_flagged(self):
        from service.models import SupplyCutCause

        causes = {c.token: c for c in SupplyCutCause.objects.all()}
        self.assertEqual(
            set(causes),
            {'0', '1', '2', '3', '4', '5', 'Accidental', 'Planificada'},
        )
        self.assertTrue(causes['Accidental'].is_temporary)
        self.assertTrue(causes['Planificada'].is_temporary)
        self.assertTrue(causes['4'].is_temporary)
        for token in ('0', '1', '2', '3', '5'):
            self.assertFalse(causes[token].is_temporary)

    def test_removed_config_and_closed_family(self):
        from coredata.models import ConfigProject
        from service.utils import supply_cut_service

        self.assertFalse(
            ConfigProject.objects.filter(
                token__in=['supply_cut_status_pending_token', 'supply_cut_status_innactive_token']
            ).exists(),
            "Els tokens de config pendent/innactive han d'haver-se eliminat.",
        )
        self.assertEqual(supply_cut_service.closed_status_tokens(), {'2', '3'})
        self.assertEqual(supply_cut_service.closed_status_token(), '2')

    def test_canonical_maps_match_review_command_literals(self):
        import json
        from coredata.models import ConfigProject
        from integrations.outbound.giswater.sync import _load_mincut_config_maps
        from service.management.commands.review_supply_cuts import (
            EXPLICIT_CAUSE_MAP,
            EXPLICIT_STATE_MAP,
        )

        maps = _load_mincut_config_maps()
        self.assertEqual(maps['giswater_mincut_state_map'], EXPLICIT_STATE_MAP)
        self.assertEqual(maps['giswater_mincut_cause_map'], EXPLICIT_CAUSE_MAP)

        self.assertEqual(json.loads(
            ConfigProject.objects.get(token='giswater_mincut_state_map').value
        )['4'], '0')
        self.assertEqual(json.loads(
            ConfigProject.objects.get(token='giswater_mincut_state_map').value
        )['Sobre la planificació'], '0')
        self.assertEqual(json.loads(
            ConfigProject.objects.get(token='giswater_mincut_cause_map').value
        )['Accidental'], 'Accidental')

    def test_manual_cut_is_born_planned(self):
        from coredata.models import ConfigProject
        from service.models import SupplyCut, SupplyPointStatus
        from service.serializers.supply_cut_serializer import SupplyCutSerializer

        SupplyPointStatus.objects.create(token='tallat', name='Tallat', color='red')
        ConfigProject.objects.update_or_create(
            token='supply_point_status_cut_token',
            defaults={'name': 'Token Supply Point Status Cut', 'value': 'tallat'},
        )

        serializer = SupplyCutSerializer(data={'token': 'born-planned'}, context={'request': None})
        self.assertTrue(serializer.is_valid())
        cut = serializer.save()
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '0')
        self.assertEqual(SupplyCut.objects.get(id=cut.id).status.token, '0')
        self.assertFalse(cut.requires_review)


class TestSupplyCutManualLifecycle(TestCase):
    """Fase 4: accions start/finish. Un tall mai Actiu no es registra Acabat
    (s'ha de cancel·lar); els plans cancel·lats no marquen execució."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from coredata.models import ConfigProject
        from service.models import SupplyCutCause, SupplyCutStatus, SupplyPoint, SupplyPointStatus

        cls.active_pt = SupplyPointStatus.objects.create(token='1', name='Actiu', color='green')
        cls.cut_pt = SupplyPointStatus.objects.create(token='tallat', name='Tallat', color='red')
        cls.sp = SupplyPoint.objects.create(token='sp-lc', status=cls.active_pt)
        cls.superuser = get_user_model().objects.create_superuser(username='root-lc')

        ConfigProject.objects.update_or_create(
            token='supply_point_status_cut_token',
            defaults={'name': 'cut', 'value': 'tallat'},
        )
        ConfigProject.objects.update_or_create(
            token='supply_point_status_activate_token',
            defaults={'name': 'active', 'value': '1'},
        )
        cls.indefinite = SupplyCutCause.objects.get(token='0')
        cls.temporary = SupplyCutCause.objects.get(token='4')

    @staticmethod
    def _cut(cause, **extra):
        from service.models import SupplyCut, SupplyCutStatus
        extra.setdefault('status_id', SupplyCutStatus.objects.get(token='0').id)
        cut = SupplyCut.objects.create(token='lc-%s' % cause.token, cause=cause, **extra)
        cut.supply_points.set([TestSupplyCutManualLifecycle.sp])
        return cut

    def test_start_planned_indefinite_cuts_sp(self):
        from service.utils import supply_cut_service
        cut = self._cut(self.indefinite)
        supply_cut_service.start_cut(cut)
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '1')
        self.assertIsNotNone(cut.exec_start)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt)

    def test_start_planned_temporary_does_not_cut_sp(self):
        from service.utils import supply_cut_service
        cut = self._cut(self.temporary)
        supply_cut_service.start_cut(cut)
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '1', "El temporal s'activa però no talla.")
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

    def test_finish_active_restores_sp_and_dates(self):
        from service.utils import supply_cut_service
        cut = self._cut(self.indefinite)
        supply_cut_service.start_cut(cut)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt)
        supply_cut_service.finish_cut(cut)
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '2')
        self.assertIsNotNone(cut.exec_end)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

    def test_finish_from_planned_is_rejected(self):
        from service.utils import supply_cut_service
        cut = self._cut(self.indefinite)
        with self.assertRaises(ValueError):
            supply_cut_service.finish_cut(cut)

    def test_start_from_terminal_is_rejected(self):
        from service.utils import supply_cut_service
        from service.models import SupplyCutStatus
        cut = self._cut(self.indefinite, status_id=SupplyCutStatus.objects.get(token='2').id)
        with self.assertRaises(ValueError):
            supply_cut_service.start_cut(cut)

    def test_actions_endpoints(self):
        from django.urls import reverse
        from rest_framework.test import APIClient

        cut = self._cut(self.indefinite)
        client = APIClient()
        client.force_authenticate(user=self.superuser)

        # finish des de Planned → 400
        resp = client.post(reverse('supplycut-finish-cut', kwargs={'pk': cut.id}), {}, format='json')
        self.assertEqual(resp.status_code, 400)

        # start → 200
        resp = client.post(reverse('supplycut-start-cut', kwargs={'pk': cut.id}), {}, format='json')
        self.assertEqual(resp.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '1')

        # start de nou (ara Actiu) → 400
        resp = client.post(reverse('supplycut-start-cut', kwargs={'pk': cut.id}), {}, format='json')
        self.assertEqual(resp.status_code, 400)

        # finish → 200
        resp = client.post(reverse('supplycut-finish-cut', kwargs={'pk': cut.id}), {}, format='json')
        self.assertEqual(resp.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '2')


class TestSupplyCutResolveReviewAndAlert(TestCase):
    """Fase 5: resolució de quarantenes i l'alert de tall vigent als PP."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from coredata.models import ConfigProject
        from service.models import SupplyCutCause, SupplyCutStatus, SupplyPoint, SupplyPointStatus

        cls.active_pt = SupplyPointStatus.objects.create(token='1', name='Actiu', color='green')
        cls.cut_pt = SupplyPointStatus.objects.create(token='tallat', name='Tallat', color='red')
        cls.sp = SupplyPoint.objects.create(token='sp-rr', status=cls.active_pt)
        cls.superuser = get_user_model().objects.create_superuser(username='root-rr')

        ConfigProject.objects.update_or_create(
            token='supply_point_status_cut_token',
            defaults={'name': 'cut', 'value': 'tallat'},
        )
        ConfigProject.objects.update_or_create(
            token='supply_point_status_activate_token',
            defaults={'name': 'active', 'value': '1'},
        )
        cls.indefinite = SupplyCutCause.objects.get(token='0')
        cls.temporary = SupplyCutCause.objects.get(token='4')
        cls.conflicte = SupplyCutStatus.objects.get(token='5')

        coredata = __import__('coredata.models', fromlist=['ConfigProject'])
        for token, value in [
            ('fraud_status_pending_token', 'pendent'),
            ('fraud_status_active_token', 'actiu'),
            ('contract_active_token', 'actiu'),
        ]:
            ConfigProject.objects.update_or_create(
                token=token, defaults={'name': token, 'value': value},
            )
        from fraud.models import FraudStatus
        FraudStatus.objects.update_or_create(token='pendent', defaults={'name': 'Pendent'})
        FraudStatus.objects.update_or_create(token='actiu', defaults={'name': 'Actiu'})
        from contract.models import ContractStatus
        ContractStatus.objects.update_or_create(token='actiu', defaults={'name': 'Actiu'})

    @staticmethod
    def _quarantine(cause, sp=None, **extra):
        from service.models import SupplyCut, SupplyCutStatus
        cut = SupplyCut.objects.create(
            token='q-%s' % cause.token,
            cause=cause,
            status_id=SupplyCutStatus.objects.get(token='5').id,
            requires_review=True,
            **extra,
        )
        cut.supply_points.set([sp or TestSupplyCutResolveReviewAndAlert.sp])
        return cut

    def test_resolve_to_active_cuts_sp(self):
        from django.urls import reverse
        from rest_framework.test import APIClient

        cut = self._quarantine(self.indefinite)
        client = APIClient()
        client.force_authenticate(user=self.superuser)
        resp = client.post(
            reverse('supplycut-resolve-review', kwargs={'pk': cut.id}),
            {'status': '1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        cut.refresh_from_db()
        self.assertFalse(cut.requires_review)
        self.assertEqual(cut.status.token, '1')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.cut_pt, "Resolt a Actiu (indefinit): talla.")

    def test_resolve_to_finished_does_not_stamp_execution(self):
        from django.urls import reverse
        from rest_framework.test import APIClient

        cut = self._quarantine(self.indefinite)
        client = APIClient()
        client.force_authenticate(user=self.superuser)
        resp = client.post(
            reverse('supplycut-resolve-review', kwargs={'pk': cut.id}),
            {'status': '2'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(cut.status.token, '2')
        self.assertIsNone(cut.exec_end, "Resolt des de Conflicte: no inventa execució.")
        self.assertFalse(cut.requires_review)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, self.active_pt)

    def test_resolve_rejects_invalid_and_non_quarantine(self):
        from django.urls import reverse
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.superuser)

        # estat destí no vàlid (Conflicte mateixa / inexistent)
        cut = self._quarantine(self.indefinite)
        resp = client.post(
            reverse('supplycut-resolve-review', kwargs={'pk': cut.id}),
            {'status': '5'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

        # tall que no requereix revisió → 400
        cut.requires_review = False
        cut.save()
        resp = client.post(
            reverse('supplycut-resolve-review', kwargs={'pk': cut.id}),
            {'status': '1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_alert_field_on_serializers(self):
        from service.serializers.supply_point_serializer import (
            SupplyPointListSerializer,
            SupplyPointMinimalSerializer,
        )
        from django.db.models import Prefetch
        from service.models import SupplyCut, SupplyCutStatus

        cut = self._quarantine(self.indefinite)  # continues quarantine
        obj = SupplyPoint.objects.prefetch_related(
            Prefetch(
                'supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            )
        ).get(id=self.sp.id)
        self.assertIsNone(SupplyPointMinimalSerializer(obj).data['supply_cut_alert'])

        cut.requires_review = False
        cut.status = SupplyCutStatus.objects.get(token='0')
        cut.save()
        obj = SupplyPoint.objects.prefetch_related(
            Prefetch(
                'supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            )
        ).get(id=self.sp.id)
        alert = SupplyPointMinimalSerializer(obj).data['supply_cut_alert']
        self.assertEqual(alert['id'], cut.id)
        self.assertEqual(alert['status_token'], '0')
        self.assertIn('supply_cut_alert', SupplyPointListSerializer(obj).data)

    def test_alert_expires_for_past_temporary_cut(self):
        """Un tall puntual (temporal) amb date_end ja superat ja no genera
        alerta, encara que continuï Planificat."""
        from datetime import timedelta

        from django.db.models import Prefetch
        from django.utils import timezone

        from service.models import SupplyCut, SupplyCutStatus
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer

        cut = SupplyCut.objects.create(
            token='q-expired',
            cause=self.temporary,
            status=SupplyCutStatus.objects.get(token='0'),
            requires_review=False,
            date_end=timezone.now() - timedelta(days=1),
        )
        cut.supply_points.set([self.sp])

        def alert_for():
            obj = SupplyPoint.objects.prefetch_related(
                Prefetch(
                    'supply_cuts',
                    queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                    to_attr='_prefetched_supply_cuts',
                )
            ).get(id=self.sp.id)
            return SupplyPointMinimalSerializer(obj).data['supply_cut_alert']

        self.assertIsNone(alert_for(), "Temporal amb date_end passat: sense alerta.")

        cut.date_end = timezone.now() + timedelta(days=1)
        cut.save()
        self.assertIsNotNone(alert_for(), "Temporal dins del termini: alerta present.")

    def test_active_indefinite_cut_keeps_alert_with_past_date_end(self):
        """Un tall ACTIU i indefinit NO decau per tenir la data de fi superada:
        la regla d'expiració (fi prevista) només s'aplica als plans i als
        motius temporals; un tall vigent ha de continuar alertant."""
        from datetime import timedelta

        from django.db.models import Prefetch
        from django.utils import timezone

        from service.models import SupplyCut, SupplyCutStatus
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer

        cut = SupplyCut.objects.create(
            token='q-active-indef',
            cause=self.indefinite,
            status=SupplyCutStatus.objects.get(token='1'),
            requires_review=False,
            date_end=timezone.now() - timedelta(days=5),
        )
        cut.supply_points.set([self.sp])

        obj = SupplyPoint.objects.prefetch_related(
            Prefetch(
                'supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            )
        ).get(id=self.sp.id)
        self.assertIsNotNone(
            SupplyPointMinimalSerializer(obj).data['supply_cut_alert'],
            "Actiu indefinit amb date_end passat: encara alerta.",
        )

    def test_planned_cut_is_stale_by_past_forecast_end(self):
        """Un tall manual Planificat amb la fi prevista (date_end) ja superada
        no genera alerta; amb la fi al futur, sí."""
        from datetime import timedelta

        from django.db.models import Prefetch
        from django.utils import timezone

        from service.models import SupplyCut, SupplyCutStatus
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer

        def alert_for(cut):
            obj = SupplyPoint.objects.prefetch_related(
                Prefetch(
                    'supply_cuts',
                    queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                    to_attr='_prefetched_supply_cuts',
                )
            ).get(id=self.sp.id)
            return SupplyPointMinimalSerializer(obj).data['supply_cut_alert']

        stale = SupplyCut.objects.create(
            token='q-stale-manual',
            source=SupplyCut.SOURCE_MANUAL,
            cause=self.indefinite,
            status=SupplyCutStatus.objects.get(token='0'),
            requires_review=False,
            date_end=timezone.now() - timedelta(days=10),
        )
        stale.supply_points.set([self.sp])
        self.assertIsNone(alert_for(stale), "Pla amb la fi prevista passada: sense alerta.")

        forthcoming = SupplyCut.objects.create(
            token='q-future-manual',
            source=SupplyCut.SOURCE_MANUAL,
            cause=self.indefinite,
            status=SupplyCutStatus.objects.get(token='0'),
            requires_review=False,
            date_end=timezone.now() + timedelta(days=3),
        )
        forthcoming.supply_points.set([self.sp])
        alert = alert_for(forthcoming)
        self.assertIsNotNone(alert, "Pla amb la fi prevista al futur: alerta present.")
        self.assertEqual(alert['id'], forthcoming.id)

    def test_planned_cut_staleness_uses_forecast_end_not_execution(self):
        """L'obsolescència del pla es decideix SOLS per la fi prevista
        (forecast end): una execució real passada (exec_start) sense fi
        prevista superada manté l'alerta, i una fi prevista superada l'elimina
        encara que no hi hagi execució (exec_start None)."""
        from datetime import timedelta

        from django.db.models import Prefetch
        from django.utils import timezone

        from service.models import SupplyCut, SupplyCutStatus, SupplyPoint, SupplyPointStatus
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer

        def alert_for(cut):
            obj = SupplyPoint.objects.prefetch_related(
                Prefetch(
                    'supply_cuts',
                    queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                    to_attr='_prefetched_supply_cuts',
                )
            ).get(id=self.sp.id)
            return SupplyPointMinimalSerializer(obj).data['supply_cut_alert']

        still_open = SupplyCut.objects.create(
            token='q-gis-exec-past',
            source=SupplyCut.SOURCE_GISWATER,
            cause=self.indefinite,
            status=SupplyCutStatus.objects.get(token='0'),
            requires_review=False,
            exec_start=timezone.now() - timedelta(days=5),
            date_end=timezone.now() + timedelta(days=2),
        )
        still_open.supply_points.set([self.sp])
        self.assertIsNotNone(
            alert_for(still_open),
            "exec_start passat però fi prevista futura: encara alerta (l'execució no compta).",
        )

        # Escenari aïllat: el PP només mira el tall obsolet.
        sp2 = SupplyPoint.objects.create(token='sp-rr2', status=SupplyPointStatus.objects.get(token=self.active_pt.token))
        stale = SupplyCut.objects.create(
            token='q-gis-forecast-end-past',
            source=SupplyCut.SOURCE_GISWATER,
            cause=self.indefinite,
            status=SupplyCutStatus.objects.get(token='0'),
            requires_review=False,
            exec_start=None,
            date_end=timezone.now() - timedelta(days=5),
        )
        stale.supply_points.set([sp2])

        obj = SupplyPoint.objects.prefetch_related(
            Prefetch(
                'supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            )
        ).get(id=sp2.id)
        self.assertIsNone(
            SupplyPointMinimalSerializer(obj).data['supply_cut_alert'],
            "Fi prevista passada sense execució (exec_start null): pla obsolet, sense alerta.",
        )



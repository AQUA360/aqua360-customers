"""Sincronització de talls amb Giswater: Customers té prioritat camp a camp."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from coredata.models import ConfigProject
from integrations.outbound.giswater import sync as sync_mod
from logger.models import LogSupplyCutStatus
from service.models import (
    Connection, SupplyCut, SupplyCutCause, SupplyCutStatus, SupplyPoint, SupplyPointStatus,
)
from service.utils import supply_cut_service


def _catalog(model, token, **defaults):
    row = model.objects.filter(token=token).first()
    return row or model.objects.create(token=token, **defaults)


class TestGiswaterSyncCustomersPriority(TestCase):

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('supply_point_status_cut_token', 'sp-cut'),
            ('supply_point_status_activate_token', 'sp-active'),
            ('supply_cut_status_active_token', '1'),
            ('supply_cut_status_closed_tokens', '2,3'),
            ('giswater_mincut_state_map', json.dumps({'0': '0', '1': '1', '2': '2'})),
            ('giswater_mincut_cause_map', json.dumps({'0': '0', '4': '4'})),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'name': token, 'value': value})

        cls.sp_active = SupplyPointStatus.objects.create(token='sp-active', name='Actiu')
        cls.sp_cut = SupplyPointStatus.objects.create(token='sp-cut', name='Tallat')
        cls.planned = _catalog(SupplyCutStatus, '0', name='Planificat')
        cls.active = _catalog(SupplyCutStatus, '1', name='Actiu')
        cls.finished = _catalog(SupplyCutStatus, '2', name='Acabat')
        cls.indefinite = _catalog(SupplyCutCause, '0', name='Altres', is_temporary=False)
        cls.temporary = _catalog(SupplyCutCause, '4', name='Manteniment', is_temporary=True)

        cls.points = {}
        for code in ('C1', 'C2', 'C3'):
            connection = Connection.objects.create(code_gis=code)
            cls.points[code] = SupplyPoint.objects.create(
                token=f'sp-{code}', status=cls.sp_active, connection=connection
            )

    def _sync(self, mincuts, connecs):
        """`connecs`: {id mincut: [connec_id, ...]}."""
        with patch.object(sync_mod, 'fetch_om_mincuts', return_value=mincuts), \
             patch.object(sync_mod, 'fetch_om_mincut_connecs', side_effect=lambda mid: connecs.get(mid, [])), \
             patch.object(sync_mod, 'extract_fields', side_effect=lambda value: [
                 {'connec_id': c} if isinstance(c, str) else c for c in value
             ]):
            return sync_mod.sync_supply_cuts_from_giswater()

    def _status_of(self, code):
        self.points[code].refresh_from_db()
        return self.points[code].status

    def test_new_active_mincut_cuts_points_and_logs(self):
        self._sync([{'id': 'm1', 'anl_cause': '0', 'state': '1'}], {'m1': ['C1']})

        cut = SupplyCut.objects.get(token='m1')
        self.assertEqual(cut.status, self.active)
        self.assertEqual(cut.giswater_connec_ids, ['C1'])
        self.assertEqual(self._status_of('C1'), self.sp_cut)
        self.assertTrue(LogSupplyCutStatus.objects.filter(object=cut, current_status=self.active).exists())

    def test_unlocked_cut_follows_giswater_state_and_points(self):
        self._sync([{'id': 'm2', 'anl_cause': '0', 'state': '0'}], {'m2': ['C1', 'C2']})
        self.assertEqual(self._status_of('C1'), self.sp_active)

        # Giswater l'executa i treu C2: s'activa, talla C1 i C2 surt del tall.
        start = timezone.now() - timedelta(hours=1)
        self._sync(
            [{'id': 'm2', 'anl_cause': '0', 'state': '1', 'exec_start': start.isoformat()}],
            {'m2': ['C1']},
        )
        cut = SupplyCut.objects.get(token='m2')
        self.assertEqual(cut.status, self.active)
        self.assertIsNotNone(cut.exec_start)
        self.assertEqual(set(cut.supply_points.values_list('id', flat=True)), {self.points['C1'].id})
        self.assertEqual(self._status_of('C1'), self.sp_cut)
        self.assertEqual(self._status_of('C2'), self.sp_active)

        # Giswater el tanca: es restauren els punts.
        self._sync([{'id': 'm2', 'anl_cause': '0', 'state': '2'}], {'m2': ['C1']})
        self.assertEqual(SupplyCut.objects.get(token='m2').status, self.finished)
        self.assertEqual(self._status_of('C1'), self.sp_active)

    def test_locked_fields_are_not_overwritten(self):
        forecast = timezone.now() + timedelta(days=2)
        self._sync([{'id': 'm3', 'anl_cause': '0', 'state': '0'}], {'m3': ['C1']})
        cut = SupplyCut.objects.get(token='m3')
        cut.status = self.finished
        cut.date_start = forecast
        cut.customers_locked_fields = ['status', 'date_start']
        cut.save()

        other_forecast = forecast + timedelta(days=5)
        self._sync(
            [{'id': 'm3', 'anl_cause': '4', 'state': '1', 'forecast_start': other_forecast.isoformat()}],
            {'m3': ['C1']},
        )
        cut.refresh_from_db()
        self.assertEqual(cut.status, self.finished)
        self.assertEqual(cut.date_start, forecast)
        self.assertEqual(cut.state_raw, '1')
        # El motiu no està protegit: segueix Giswater.
        self.assertEqual(cut.cause, self.temporary)

    def test_empty_giswater_date_does_not_erase_value(self):
        exec_start = timezone.now() - timedelta(hours=3)
        self._sync(
            [{'id': 'm4', 'anl_cause': '0', 'state': '0', 'exec_start': exec_start.isoformat()}],
            {'m4': []},
        )
        self._sync([{'id': 'm4', 'anl_cause': '0', 'state': '0'}], {'m4': []})
        self.assertIsNotNone(SupplyCut.objects.get(token='m4').exec_start)

    def test_locked_points_only_receive_new_connecs(self):
        self._sync([{'id': 'm5', 'anl_cause': '0', 'state': '1'}], {'m5': ['C1', 'C2']})
        cut = SupplyCut.objects.get(token='m5')
        # A Customers es treu C2 del tall.
        supply_cut_service.remove_supply_points_from_cut(cut, [self.points['C2'].id])
        supply_cut_service.lock_fields(cut, 'supply_points')
        self.assertEqual(self._status_of('C2'), self.sp_active)

        # Giswater continua enviant C2 i hi afegeix C3: només entra C3, i es talla.
        self._sync([{'id': 'm5', 'anl_cause': '0', 'state': '1'}], {'m5': ['C1', 'C2', 'C3']})
        cut.refresh_from_db()
        self.assertEqual(
            set(cut.supply_points.values_list('id', flat=True)),
            {self.points['C1'].id, self.points['C3'].id},
        )
        self.assertEqual(self._status_of('C2'), self.sp_active)
        self.assertEqual(self._status_of('C3'), self.sp_cut)

        # I si Giswater treu C1, en un tall protegit no se'n treu cap.
        self._sync([{'id': 'm5', 'anl_cause': '0', 'state': '1'}], {'m5': ['C3']})
        self.assertIn(self.points['C1'], SupplyCut.objects.get(token='m5').supply_points.all())

    def test_locked_points_without_previous_sync_only_store_baseline(self):
        cut = SupplyCut.objects.create(
            token='m6', status=self.planned, cause=self.indefinite, source=SupplyCut.SOURCE_GISWATER,
            customers_locked_fields=['supply_points'],
        )
        cut.supply_points.set([self.points['C1']])
        self._sync([{'id': 'm6', 'anl_cause': '0', 'state': '0'}], {'m6': ['C1', 'C2']})
        cut.refresh_from_db()
        self.assertEqual(list(cut.supply_points.all()), [self.points['C1']])
        self.assertEqual(cut.giswater_connec_ids, ['C1', 'C2'])


class TestCustomersActionsLockFields(TestCase):

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('supply_point_status_cut_token', 'sp-cut'),
            ('supply_point_status_activate_token', 'sp-active'),
            ('supply_cut_status_active_token', '1'),
            ('supply_cut_status_closed_tokens', '2,3'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'name': token, 'value': value})
        SupplyPointStatus.objects.create(token='sp-active', name='Actiu')
        SupplyPointStatus.objects.create(token='sp-cut', name='Tallat')
        cls.planned = _catalog(SupplyCutStatus, '0', name='Planificat')
        cls.active = _catalog(SupplyCutStatus, '1', name='Actiu')
        cls.finished = _catalog(SupplyCutStatus, '2', name='Acabat')
        cls.cause = _catalog(SupplyCutCause, '4', name='Manteniment', is_temporary=True)
        cls.user = User.objects.create_superuser(username='locker', password='p', email='locker@example.com')
        cls.factory = APIRequestFactory()

    def _post(self, action, cut, data=None):
        from service.views.supply_cut_view import SupplyCutViewSet

        request = self.factory.post(f'/service/supply-cut/{cut.id}/', data or {}, format='json')
        force_authenticate(request, user=self.user)
        return SupplyCutViewSet.as_view({'post': action})(request, pk=cut.id)

    def _cut(self, status):
        return SupplyCut.objects.create(
            token='lock', status=status, cause=self.cause, source=SupplyCut.SOURCE_GISWATER,
        )

    def test_start_and_finish_lock_status_and_exec_dates(self):
        cut = self._cut(self.planned)
        self.assertEqual(self._post('start_cut', cut).status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(set(cut.customers_locked_fields), {'status', 'exec_start'})

        self.assertEqual(self._post('finish_cut', cut).status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(set(cut.customers_locked_fields), {'status', 'exec_start', 'exec_end'})

    def test_resolve_review_locks_status_and_given_fields(self):
        cut = self._cut(self.planned)
        cut.requires_review = True
        cut.save()
        response = self._post('resolve_review', cut, {'status': '0', 'cause': self.cause.id})
        self.assertEqual(response.status_code, 200)
        cut.refresh_from_db()
        self.assertEqual(set(cut.customers_locked_fields), {'status', 'cause'})

    def test_lock_fields_ignores_unknown_and_duplicates(self):
        cut = self._cut(self.planned)
        supply_cut_service.lock_fields(cut, 'status', 'status', 'token')
        cut.refresh_from_db()
        self.assertEqual(cut.customers_locked_fields, ['status'])

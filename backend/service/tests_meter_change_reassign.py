import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject, Person
from logger.models import LogSupplyPointChange
from service.models import Meter, MeterStatus, SupplyPoint
from service.services.meter_change_service import (
    MeterAssignedElsewhereError, MeterChangeService, get_meter_assignments_elsewhere,
)


class MeterReassignBase(TestCase):
    """Un comptador que ja és a un altre punt no es mou sense confirmació expressa."""

    CHANGE_DATE = datetime.date(2026, 9, 15)

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('meter_status_active_token', '1'),
            ('meter_status_inactive_token', '-1'),
            ('contract_terminated_status', '99'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.status_active, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        MeterStatus.objects.get_or_create(token='-1', defaults={'name': 'Inactiu'})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'A'})
        cls.user = get_user_model().objects.create_superuser(username='meter-reassign', password='x')

    def setUp(self):
        self.old_meter = Meter.objects.create(code='OLD-R', status=self.status_active)
        self.other_meter = Meter.objects.create(code='OTHER-R', status=self.status_active)
        self.target = SupplyPoint.objects.create(token='SP-TARGET', meter=self.old_meter)
        self.origin = SupplyPoint.objects.create(token='SP-ORIGIN', meter=self.other_meter)
        holder = Person.objects.create(name='Nom', surname='Cognom')
        self.origin_contract = Contract.objects.create(status=self.contract_status, token='C-ORIGIN', holder=holder)
        self.origin_contract.supply_points.add(self.origin)

    def _apply(self, confirm_reassign=False):
        MeterChangeService(user=self.user).apply(
            supply_point_id=self.target.id,
            prev_meter_id=self.old_meter.id,
            new_meter_id=self.other_meter.id,
            origin=None,
            change_date=self.CHANGE_DATE,
            previous_reading_data={},
            new_reading_data={},
            confirm_reassign=confirm_reassign,
        )


class MeterAssignmentsTest(MeterReassignBase):

    def test_lists_other_supply_points_with_contracts(self):
        assignments = get_meter_assignments_elsewhere(self.other_meter, self.target.id)

        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]['supply_point_token'], 'SP-ORIGIN')
        self.assertEqual(assignments[0]['contracts'], [
            {'id': self.origin_contract.id, 'token': 'C-ORIGIN', 'holder': 'Nom Cognom'},
        ])

    def test_excludes_the_target_supply_point(self):
        self.assertEqual(get_meter_assignments_elsewhere(self.other_meter, self.origin.id), [])

    def test_general_meter_is_never_assigned_elsewhere(self):
        self.other_meter.is_general = True
        self.other_meter.save()
        self.assertEqual(get_meter_assignments_elsewhere(self.other_meter, self.target.id), [])


class MeterChangeServiceReassignTest(MeterReassignBase):

    def test_without_confirmation_nothing_changes(self):
        with self.assertRaises(MeterAssignedElsewhereError) as ctx:
            self._apply()

        self.assertEqual(ctx.exception.assignments[0]['supply_point_id'], self.origin.id)
        self.target.refresh_from_db()
        self.origin.refresh_from_db()
        self.assertEqual(self.target.meter_id, self.old_meter.id)
        self.assertEqual(self.origin.meter_id, self.other_meter.id)
        self.assertFalse(LogSupplyPointChange.objects.exists())

    def test_with_confirmation_moves_meter_and_logs_origin(self):
        self._apply(confirm_reassign=True)

        self.target.refresh_from_db()
        self.origin.refresh_from_db()
        self.assertEqual(self.target.meter_id, self.other_meter.id)
        self.assertIsNone(self.origin.meter_id)
        origin_log = LogSupplyPointChange.objects.get(supply_point=self.origin)
        self.assertEqual(origin_log.action, 'meter')
        self.assertEqual(origin_log.previous_value, 'OTHER-R')
        self.assertIsNone(origin_log.current_value)
        self.assertIn('SP-TARGET', origin_log.observation)
        self.assertTrue(LogSupplyPointChange.objects.filter(supply_point=self.target).exists())

    def test_free_meter_needs_no_confirmation(self):
        self.origin.meter = None
        self.origin.save()

        self._apply()

        self.target.refresh_from_db()
        self.assertEqual(self.target.meter_id, self.other_meter.id)


class SupplyPointMeterViewsReassignTest(MeterReassignBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # El queryset del punt anota els fraus a partir d'aquests tokens.
        for token in ('fraud_status_pending_token', 'fraud_status_active_token',
                      'fraud_status_resolved_token', 'fraud_status_expired_token'):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': token})

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        # La resposta serialitza el punt sencer (fraus, cobraments...): no és el que es prova aquí.
        serializer = mock.patch('service.views.supply_point_view.SupplyPointSerializer')
        serializer.start().return_value.data = {}
        self.addCleanup(serializer.stop)

    def _save_meter_change(self, **extra):
        return self.client.post('/service/supply-point/save-meter-change/', {
            'supply_point': self.target.id,
            'prev_meter': self.old_meter.id,
            'new_meter': self.other_meter.id,
            'change_date': '2026-09-15',
            'previous_reading': {'reading_value': 10, 'calculated_value': 0, 'leak_value': 0, 'is_close': True},
            'new_reading': {'reading_value': 0, 'calculated_value': 0, 'leak_value': 0, 'is_close': False},
            'origin': 'Canvi de comptador',
            **extra,
        }, format='json')

    def test_save_meter_change_without_confirmation_returns_409(self):
        response = self._save_meter_change()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'meter_assigned')
        self.assertEqual(response.data['assignments'][0]['supply_point_token'], 'SP-ORIGIN')
        self.origin.refresh_from_db()
        self.assertEqual(self.origin.meter_id, self.other_meter.id)

    def test_save_meter_change_with_confirmation(self):
        response = self._save_meter_change(confirm_reassign=True)

        self.assertEqual(response.status_code, 200)
        self.origin.refresh_from_db()
        self.target.refresh_from_db()
        self.assertIsNone(self.origin.meter_id)
        self.assertEqual(self.target.meter_id, self.other_meter.id)
        self.assertTrue(LogSupplyPointChange.objects.filter(supply_point=self.origin).exists())

    def test_update_meter_without_confirmation_returns_409(self):
        response = self.client.post('/service/supply-point/update-meter/', {
            'supply_point_id': self.target.id, 'meter_id': self.other_meter.id,
        }, format='json')

        self.assertEqual(response.status_code, 409)
        self.origin.refresh_from_db()
        self.assertEqual(self.origin.meter_id, self.other_meter.id)

    def test_update_meter_with_confirmation(self):
        response = self.client.post('/service/supply-point/update-meter/', {
            'supply_point_id': self.target.id, 'meter_id': self.other_meter.id, 'confirm_reassign': True,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.origin.refresh_from_db()
        self.assertIsNone(self.origin.meter_id)

    def test_meter_assignments_endpoint(self):
        response = self.client.get(
            f'/service/meter/{self.other_meter.id}/assignments/?supply_point={self.target.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([a['supply_point_id'] for a in response.data['assignments']], [self.origin.id])

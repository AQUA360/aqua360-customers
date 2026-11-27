import json
from unittest import mock

from django.test import TestCase

from billing.models import Reading, ReadingBatch, ReadingBatchStatus
from coredata.models import ConfigProject
from lecturapp.models import ReadingOperator
from lecturapp.tasks import LECTURAPP_ROUTES_TASK_KIND
from lecturapp.utils.batch_scope_service import (
    get_open_reading_batch,
    meter_in_reading_batch,
    open_reading_batches,
    property_in_open_batch,
)
from lecturapp.utils.sync_readings_service import process_sync_reading_row
from service.models import Meter, MeterStatus, Property, Route, RoutePosition, SupplyPoint


class LecturappBatchScopeTests(TestCase):
    """L'operari només llegeix i escriu lots oberts i comptadors que són del lot."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(token='contract_active_token', defaults={'value': 'ACTIVE'})
        for config_token, value in (
            ('batch_status_finish_token', 'FINISH'),
            ('batch_status_cancel_token', 'CANCEL'),
            ('batch_status_billed_token', 'BILLED'),
        ):
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': value})
        cls.status_open = ReadingBatchStatus.objects.create(token='OPEN', name='Obert')
        cls.status_billed = ReadingBatchStatus.objects.create(token='BILLED', name='Facturat')
        meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})

        position = RoutePosition.objects.create(route=Route.objects.create(name='R-lot'), position=1)
        cls.property = Property.objects.create(name='Finca del lot', route_position=position)
        cls.route_meter = Meter.objects.create(code='M-RUTA', status=meter_status)
        cls.sub_meter = Meter.objects.create(code='M-SUB', status=meter_status, meter_general=cls.route_meter)
        SupplyPoint.objects.create(token='SP-RUTA', meter=cls.route_meter, property=cls.property)
        cls.fix_meter = Meter.objects.create(code='M-FIX', status=meter_status)

        other_position = RoutePosition.objects.create(route=Route.objects.create(name='R-altra'), position=1)
        cls.other_property = Property.objects.create(name='Altra finca', route_position=other_position)
        cls.other_meter = Meter.objects.create(code='M-ALTRE', status=meter_status)
        cls.other_sp = SupplyPoint.objects.create(token='SP-ALTRE', meter=cls.other_meter, property=cls.other_property)

        cls.batch = ReadingBatch.objects.create(token='LOT-OBERT', name='Obert', status=cls.status_open)
        cls.batch.routes.add(position.route)
        cls.batch.fix_meters.add(cls.fix_meter)
        cls.billed_batch = ReadingBatch.objects.create(token='LOT-FACT', name='Facturat', status=cls.status_billed)
        cls.billed_batch.routes.add(position.route)
        cls.inactive_batch = ReadingBatch.objects.create(token='LOT-ESBORRAT', name='Esborrat', is_active=False)

        cls.operator = ReadingOperator.objects.create(name='Op', surname='Test', username='op-abast', password='x')

    def setUp(self):
        self.headers = {'HTTP_X_APP_TOKEN': self.operator.generate_token().token}

    def _sync(self, batch, readings):
        return self.client.post(
            f'/lecturapp/sync-readings/{batch.id}/', json.dumps({'readings': readings}),
            content_type='application/json', **self.headers,
        )

    # Servei

    def test_lots_oberts(self):
        self.assertEqual(list(open_reading_batches().values_list('token', flat=True)), ['LOT-OBERT'])
        self.assertIsNone(get_open_reading_batch(self.billed_batch.id))
        self.assertIsNone(get_open_reading_batch(self.inactive_batch.id))

    def test_comptadors_del_lot(self):
        self.assertTrue(meter_in_reading_batch(self.route_meter, self.batch))
        self.assertTrue(meter_in_reading_batch(self.sub_meter, self.batch))
        self.assertTrue(meter_in_reading_batch(self.fix_meter, self.batch))
        self.assertFalse(meter_in_reading_batch(self.other_meter, self.batch))

    def test_comptador_amb_lectura_al_lot_compta_com_del_lot(self):
        Reading.objects.create(batch=self.batch, meter=self.other_meter, token='L-1')
        self.assertTrue(meter_in_reading_batch(self.other_meter, self.batch))

    def test_finques_dels_lots_oberts(self):
        self.assertTrue(property_in_open_batch(self.property.id))
        self.assertFalse(property_in_open_batch(self.other_property.id))

    # Vistes

    def test_rutes_d_un_lot_tancat_responen_404(self):
        response = self.client.get(f'/lecturapp/reading-batch/{self.billed_batch.id}/routes/', **self.headers)
        self.assertEqual(response.status_code, 404)

    @mock.patch('lecturapp.views.process_reading_batch_routes_detailed.delay')
    def test_rutes_detallades_d_un_lot_tancat_no_llancen_la_tasca(self, delay):
        response = self.client.get(
            f'/lecturapp/reading-batch/{self.billed_batch.id}/routes/detailed/', **self.headers,
        )
        self.assertEqual(response.status_code, 404)
        delay.assert_not_called()

    def test_sincronitzar_a_un_lot_tancat_respon_409_i_no_desa_res(self):
        response = self._sync(self.billed_batch, [{'id': self.route_meter.id, 'changes_to_save': ''}])
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['success'])

    def test_rebutja_lectures_de_comptadors_que_no_son_del_lot(self):
        response = self._sync(self.batch, [
            {'id': self.other_meter.id, 'new_reading': 10, 'new_reading_date': '2026-11-20',
             'changes_to_save': 'new_reading,new_reading_date'},
            {'id': self.fix_meter.id, 'changes_to_save': ''},
        ])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rejected_meter_ids'], [self.other_meter.id])
        self.assertEqual(response.json()['meter_ids'], [self.fix_meter.id])
        self.assertFalse(Reading.objects.filter(meter=self.other_meter).exists())

    @mock.patch('lecturapp.views.AsyncResult')
    def test_l_estat_no_dona_resultats_d_altres_tasques(self, async_result):
        async_result.return_value = mock.Mock(state='SUCCESS', result={'status': 'completed', 'data': ['x']})
        response = self.client.get('/lecturapp/reading-batch/routes/detailed/status/altra/', **self.headers)
        self.assertEqual(response.status_code, 404)

        async_result.return_value = mock.Mock(
            state='SUCCESS', result={'kind': LECTURAPP_ROUTES_TASK_KIND, 'status': 'completed', 'data': []},
        )
        response = self.client.get('/lecturapp/reading-batch/routes/detailed/status/propia/', **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'completed')

    # Sincronització: dades que envia l'app

    def test_no_crea_lectures_en_punts_d_un_altre_comptador(self):
        process_sync_reading_row(
            {'id': self.route_meter.id, 'supply_token': self.other_sp.token, 'new_reading': 5,
             'new_reading_date': '2026-11-20', 'changes_to_save': 'new_reading,new_reading_date'},
            self.batch, self.operator, 'ACTIVE',
        )
        self.assertFalse(Reading.objects.filter(supply_point=self.other_sp).exists())
        self.assertTrue(Reading.objects.filter(meter=self.route_meter, supply_point__token='SP-RUTA').exists())

    def test_ignora_la_lectura_anterior_d_un_altre_comptador(self):
        foreign = Reading.objects.create(meter=self.other_meter, supply_point=self.other_sp, token='ALTRA')
        process_sync_reading_row(
            {'id': self.route_meter.id, 'previous_reading_id': foreign.id, 'new_reading': 5,
             'new_reading_date': '2026-11-20', 'changes_to_save': 'new_reading,new_reading_date'},
            self.batch, self.operator, 'ACTIVE',
        )
        reading = Reading.objects.get(meter=self.route_meter, batch=self.batch)
        self.assertNotEqual(reading.previous_reading_id, foreign.id)
        foreign.refresh_from_db()
        self.assertFalse(foreign.is_control)

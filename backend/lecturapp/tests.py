from datetime import date

from django.test import TestCase

from billing.models import Biller, Billing, Reading, ReadingBatch
from billing.utils.invoice_service import recalc_consumption_gen_meter
from billing.utils.reading_service import fanout_general_meter_readings
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from lecturapp.models import ReadingOperator
from lecturapp.utils.sync_readings_service import process_sync_reading_row
from service.models import (
    Company,
    Meter,
    MeterStatus,
    Property,
    Route,
    RoutePosition,
    SupplyPoint,
    SupplyPointStatus,
)


class TestSyncReadingsSharedMeter(TestCase):
    """
    A lecturapp reading for a meter shared by several supply points must create
    one reading per supply point when the meter is general, each with its own
    previous reading, linked to the original via copied_from.
    """

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(token='contract_active_token', defaults={'value': 'ACTIVE'})
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': 'TERMINATED'})
        ConfigProject.objects.get_or_create(
            token='supply_point_status_activate_token', defaults={'value': 'SP_ACTIVE'}
        )
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.company = Company.objects.create(name='Company shared meter')
        cls.operator = ReadingOperator.objects.create(name='Op', surname='Test', username='op-shared', password='x')

        cls.biller = Biller.objects.create(token='biller-shared', name='Biller', period_type='trimestral')
        route = Route.objects.create(name='R-shared', biller=cls.biller)
        position = RoutePosition.objects.create(route=route, position=1)
        cls.property = Property.objects.create(name='Property shared', route_position=position)

        cls.old_batch = ReadingBatch.objects.create(token='batch-shared-old', name='Old')
        cls.batch = ReadingBatch.objects.create(token='batch-shared-new', name='New')

    def _create_meter(self, code, is_general, total_supply_points=2):
        meter = Meter.objects.create(code=code, status=self.meter_status, is_general=is_general)
        pairs = []
        for i in range(1, total_supply_points + 1):
            sp = SupplyPoint.objects.create(
                token=f'{code}-SP{i}', meter=meter, status=self.sp_status, property=self.property
            )
            contract = Contract.objects.create(
                company=self.company,
                token=f'{code}-C{i}',
                status=self.contract_status,
                is_active=True,
                supply_point_default=sp,
            )
            contract.supply_points.add(sp)
            # Previous reading per contract, already split as in legacy data
            previous = Reading.objects.create(
                meter=meter,
                contract=contract,
                supply_point=sp,
                batch=self.old_batch,
                reading_date=date(2026, 6, 16),
                reading_value=967,
                calculated_value=23,
            )
            pairs.append((sp, contract, previous))
        return meter, pairs

    def _payload(self, meter, supply_point, value, reading_date, previous_reading):
        return {
            'id': meter.id,
            'code': meter.code,
            'supply_token': supply_point.token,
            'contract_token': None,
            'previous_reading_id': previous_reading.id,
            'last_reading': float(previous_reading.reading_value),
            'new_reading': value,
            'new_reading_date': reading_date,
            'changes_to_save': 'new_reading,new_reading_date',
        }

    def _sync(self, payload):
        return process_sync_reading_row(payload, self.batch, self.operator, 'ACTIVE')

    def test_general_meter_creates_one_linked_reading_per_supply_point(self):
        meter, pairs = self._create_meter('GEN-SHARED', is_general=True)
        (sp1, c1, prev1), (sp2, c2, prev2) = pairs

        action, _, _ = self._sync(self._payload(meter, sp1, 1031, '2026-09-16', prev1))

        self.assertEqual(action, 'created')
        readings = Reading.objects.filter(batch=self.batch, meter=meter)
        self.assertEqual(readings.count(), 2)
        original = readings.get(contract=c1)
        copy = readings.get(contract=c2)
        self.assertIsNone(original.copied_from_id)
        self.assertEqual(copy.copied_from_id, original.id)
        self.assertEqual(copy.supply_point_id, sp2.id)
        # Each contract keeps its own previous reading and the full meter consumption
        self.assertEqual(original.previous_reading_id, prev1.id)
        self.assertEqual(copy.previous_reading_id, prev2.id)
        self.assertEqual(float(original.calculated_value), 64)
        self.assertEqual(float(copy.calculated_value), 64)

    def test_resync_updates_copies(self):
        meter, pairs = self._create_meter('GEN-RESYNC', is_general=True)
        (sp1, c1, prev1), (sp2, c2, prev2) = pairs
        self._sync(self._payload(meter, sp1, 1031, '2026-09-16', prev1))

        action, _, _ = self._sync(self._payload(meter, sp1, 1035, '2026-09-18', prev1))

        self.assertEqual(action, 'updated')
        readings = Reading.objects.filter(batch=self.batch, meter=meter)
        self.assertEqual(readings.count(), 2)
        for reading in readings:
            self.assertEqual(reading.reading_date, date(2026, 9, 18))
            self.assertEqual(float(reading.reading_value), 1035)
            self.assertEqual(float(reading.calculated_value), 68)
        self.assertEqual(readings.get(contract=c2).previous_reading_id, prev2.id)

    def test_billing_fanout_reuses_synced_readings_and_splits_consumption(self):
        meter, pairs = self._create_meter('GEN-FANOUT', is_general=True)
        (sp1, c1, prev1), _ = pairs
        self._sync(self._payload(meter, sp1, 1031, '2026-09-16', prev1))
        # Reader corrects one date afterwards: must not create a duplicate at billing
        copy = Reading.objects.get(batch=self.batch, meter=meter, copied_from__isnull=False)
        copy.reading_date = date(2026, 9, 17)
        copy.save()

        billing = Billing.objects.create(token='billing-shared', name='Billing', biller=self.biller)
        Reading.objects.filter(batch=self.batch, meter=meter).update(billing=billing)

        created = fanout_general_meter_readings(billing)

        self.assertEqual(created, [])
        readings = Reading.objects.filter(billing=billing, meter=meter)
        self.assertEqual(readings.count(), 2)
        consumptions = [recalc_consumption_gen_meter(r, r.calculated_value, r.supply_point)[0] for r in readings]
        self.assertEqual(sorted(consumptions), [32, 32])

    def test_non_general_shared_meter_keeps_single_reading(self):
        meter, pairs = self._create_meter('NON-GEN-SHARED', is_general=False)
        (sp1, c1, prev1), _ = pairs

        self._sync(self._payload(meter, sp1, 1031, '2026-09-16', prev1))

        readings = Reading.objects.filter(batch=self.batch, meter=meter)
        self.assertEqual(readings.count(), 1)
        self.assertEqual(readings.get().contract_id, c1.id)

import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from billing.models import Invoice, Reading
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, SupplyPoint
from service.services.meter_change_service import (
    LEGACY_ORDER_CHANGE_METER_ORIGIN,
    METER_CHANGE_ORIGIN,
    MeterChangeService,
)


class MeterChangeConsumptionBase(TestCase):
    PREV_DATE = datetime.date(2026, 10, 6)
    CHANGE_DATE = datetime.date(2026, 11, 10)

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('meter_status_active_token', '1'),
            ('meter_status_inactive_token', '-1'),
            ('contract_terminated_status', '99'),
            ('invoice_status_cancelled_token', 'cancelled'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.status_active, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'A'})
        MeterStatus.objects.get_or_create(token='-1', defaults={'name': 'I'})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'A'})
        cls.user = get_user_model().objects.create_user(username='meter-change-consumption', password='x')

    def setUp(self):
        self.old_meter = Meter.objects.create(code='OLD-C', status=self.status_active)
        self.new_meter = Meter.objects.create(code='NEW-C', status=self.status_active)
        self.sp = SupplyPoint.objects.create(token='SP-C', meter=self.old_meter)
        self.contract = Contract.objects.create(status=self.contract_status)
        self.contract.supply_points.add(self.sp)
        older = Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.old_meter,
            reading_date=datetime.date(2026, 6, 26), reading_value=178, calculated_value=0,
        )
        self.prev = Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.old_meter,
            reading_date=self.PREV_DATE, reading_value=223, calculated_value=45,
            previous_reading=older,
        )
        # La lectura anterior ja està facturada: no s'ha de fusionar.
        Invoice.objects.create(contract=self.contract).readings.add(self.prev)

    def _readings(self):
        close = Reading.objects.get(meter=self.old_meter, is_close=True)
        initial = Reading.objects.get(meter=self.new_meter, reading_date=self.CHANGE_DATE)
        return close, initial


class MeterChangeServiceConsumptionTest(MeterChangeConsumptionBase):

    def _apply(self, old_value, new_value, old_calc=None, new_calc=None):
        MeterChangeService(user=self.user).apply(
            supply_point_id=self.sp.id,
            prev_meter_id=self.old_meter.id,
            new_meter_id=self.new_meter.id,
            origin=METER_CHANGE_ORIGIN,
            change_date=self.CHANGE_DATE,
            previous_reading_data={'reading_value': old_value, 'calculated_value': old_calc,
                                   'is_close': True, 'leak_value': 0},
            new_reading_data={'reading_value': new_value, 'calculated_value': new_calc,
                              'is_close': False, 'leak_value': 0},
        )
        return self._readings()

    def test_close_reading_consumption_against_same_meter(self):
        close, initial = self._apply('226', None)

        self.assertEqual(close.calculated_value, Decimal(3))
        self.assertEqual(close.real_consumption, Decimal(3))
        self.assertEqual(close.previous_reading, self.prev)
        self.assertEqual(initial.reading_value, Decimal(0))
        self.assertEqual(initial.calculated_value, Decimal(0))
        self.assertEqual(initial.real_consumption, Decimal(0))
        self.assertEqual(initial.previous_reading, close)

    def test_new_meter_non_zero_initial_reading(self):
        _, initial = self._apply(226, 15)

        self.assertEqual(initial.reading_value, Decimal(15))
        self.assertEqual(initial.calculated_value, Decimal(0))

    def test_reused_new_meter_consumption_against_its_own_history(self):
        Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.new_meter,
            reading_date=datetime.date(2025, 1, 1), reading_value=10, calculated_value=0,
        )
        _, initial = self._apply(226, 12)

        self.assertEqual(initial.calculated_value, Decimal(2))
        self.assertEqual(initial.real_consumption, Decimal(2))

    def test_explicit_calculated_value_is_respected(self):
        close, initial = self._apply(226, 0, old_calc=7, new_calc=0)

        self.assertEqual(close.calculated_value, Decimal(7))
        self.assertEqual(initial.calculated_value, Decimal(0))

    def test_merge_with_uninvoiced_previous_reading(self):
        # Lectura no facturada entre la facturada i el canvi: es fusiona.
        pending = Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.old_meter,
            reading_date=datetime.date(2026, 10, 20), reading_value=224, calculated_value=1,
            previous_reading=self.prev,
        )
        close, _ = self._apply(226, 0)

        pending.refresh_from_db()
        self.assertTrue(pending.is_control)
        self.assertEqual(close.previous_reading, self.prev)
        self.assertEqual(close.calculated_value, Decimal(3))
        self.assertEqual(close.real_consumption, Decimal(3))


class FixOrderChangeMeterReadingsCommandTest(MeterChangeConsumptionBase):

    def setUp(self):
        super().setUp()
        # Lectures com les desava el flux antic: calculated_value = valor de lectura.
        self.close = Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.old_meter,
            reading_date=self.CHANGE_DATE, reading_value=226, calculated_value=226,
            real_consumption=226, is_close=True, origin=LEGACY_ORDER_CHANGE_METER_ORIGIN,
            previous_reading=self.prev,
        )
        self.initial = Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.new_meter,
            reading_date=self.CHANGE_DATE, reading_value=0, calculated_value=0,
            real_consumption=0, origin=LEGACY_ORDER_CHANGE_METER_ORIGIN,
            previous_reading=self.close,
        )

    def _run(self, *args):
        out = StringIO()
        call_command('fix_order_change_meter_readings', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self._run()

        self.close.refresh_from_db()
        self.assertEqual(self.close.calculated_value, Decimal(226))
        self.assertEqual(self.close.origin, LEGACY_ORDER_CHANGE_METER_ORIGIN)
        self.assertIn(f'Reading #{self.close.id}', output)
        self.assertIn('DRY-RUN', output)

    def test_apply_fixes_values_and_origin(self):
        output = self._run('--apply')

        self.close.refresh_from_db()
        self.initial.refresh_from_db()
        self.assertEqual(self.close.calculated_value, Decimal(3))
        self.assertEqual(self.close.real_consumption, Decimal(3))
        self.assertEqual(self.initial.calculated_value, Decimal(0))
        self.assertEqual(self.close.origin, METER_CHANGE_ORIGIN)
        self.assertEqual(self.initial.origin, METER_CHANGE_ORIGIN)
        self.assertIn('calculated_value: 226.00 -> 3.00', output)

    def test_warns_when_reading_is_invoiced(self):
        invoice = Invoice.objects.create(contract=self.contract)
        invoice.readings.add(self.close)

        output = self._run()

        self.assertIn(f'reading #{self.close.id} has related invoice(s)', output)
        self.assertIn(f'#{invoice.id}', output)

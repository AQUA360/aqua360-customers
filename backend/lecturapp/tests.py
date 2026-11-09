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


class TestLecturappExcludesInactiveMeters(TestCase):
    """La lecturapp no ha de rebre comptadors en aforament ni inactius (estat -1)."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.update_or_create(token='token_meter_status_no_meter', defaults={'value': '0'})
        statuses = {
            token: MeterStatus.objects.get_or_create(token=token, defaults={'name': token})[0]
            for token in ('1', '-1', '0')
        }
        route = Route.objects.create(token='route-inactive-meters')
        cls.position = RoutePosition.objects.create(route=route, position=1)
        cls.property = Property.objects.create(token='property-inactive-meters', route_position=cls.position)
        cls.meters = {}
        for token, status in statuses.items():
            meter = Meter.objects.create(code=f'METER-STATUS-{token}', status=status)
            SupplyPoint.objects.create(token=f'sp-status-{token}', meter=meter, property=cls.property)
            cls.meters[token] = meter

        # Posició on només hi ha un comptador inactiu: no s'ha d'enviar.
        cls.inactive_position = RoutePosition.objects.create(route=route, position=2)
        inactive_property = Property.objects.create(token='property-only-inactive', route_position=cls.inactive_position)
        SupplyPoint.objects.create(
            token='sp-only-inactive',
            meter=Meter.objects.create(code='METER-ONLY-INACTIVE', status=statuses['-1']),
            property=inactive_property,
        )
        cls.route = route
        cls.context = {'include_telecontrol': True}

    def test_property_meters_only_active_are_readable(self):
        from unittest.mock import MagicMock, patch
        from lecturapp.serializers import PropertyAppDetailedSerializer

        def fake_serializer(meters, **kwargs):
            return MagicMock(data=[{'id': meter.id} for meter in meters])

        context = {**self.context, 'route_position': self.position, 'include_disabled_meters': True}
        with patch('lecturapp.serializers.MeterAppSerializer', side_effect=fake_serializer) as meter_serializer:
            data = PropertyAppDetailedSerializer(context=context).get_meters(self.property)
        self.assertEqual(meter_serializer.call_args.args[0], [self.meters['1']])
        # Els inactius i en aforament s'envien deshabilitats perquè l'app els mostri.
        reasons = {item['id']: (item['is_readable'], item['disabled_reason']) for item in data}
        self.assertEqual(reasons, {
            self.meters['1'].id: (True, None),
            self.meters['-1'].id: (False, 'meter_inactive'),
            self.meters['0'].id: (False, 'no_meter'),
        })

    def test_property_counts_only_active(self):
        from lecturapp.serializers import PropertyAppSerializer

        data = PropertyAppSerializer(self.property, context=self.context).data
        self.assertEqual(data['num_meters'], 1)

    def test_route_skips_positions_with_only_inactive_meters(self):
        from unittest.mock import patch
        from lecturapp.serializers import RouteAppDetailSerializer

        with patch('lecturapp.serializers.RoutePositionAppDetailedSerializer') as position_serializer:
            RouteAppDetailSerializer(context=self.context).get_positions(self.route)
        sent_positions = position_serializer.call_args.args[0]
        self.assertEqual(sent_positions, [self.position])


class TestLecturappPropertySplitAcrossRoutes(TestCase):
    """Finca amb un punt a la ruta trimestral (la de la finca), un altre amb ruta
    pròpia mensual i un de baixa: a cada ruta s'envien tots els comptadors i
    només es poden llegir els de la ruta."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.update_or_create(token='token_meter_status_no_meter', defaults={'value': '0'})
        ConfigProject.objects.update_or_create(token='supply_point_status_activate_token', defaults={'value': 'SP_OK'})
        active = SupplyPointStatus.objects.get_or_create(token='SP_OK', defaults={'name': 'Actiu'})[0]
        removed = SupplyPointStatus.objects.get_or_create(token='SP_BAIXA', defaults={'name': 'Baixa'})[0]
        meter_status = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})[0]
        cls.quarterly = Route.objects.create(token='SPLIT-T')
        cls.monthly = Route.objects.create(token='SPLIT-M')
        cls.quarterly_position = RoutePosition.objects.create(route=cls.quarterly, position=1, token='SPLIT-T_1')
        cls.monthly_position = RoutePosition.objects.create(route=cls.monthly, position=1, token='SPLIT-M_1')
        cls.property = Property.objects.create(token='split-property', route_position=cls.quarterly_position)

        def supply_point(token, status, route_position=None):
            meter = Meter.objects.create(code=f'M-{token}', status=meter_status)
            SupplyPoint.objects.create(token=token, meter=meter, property=cls.property, status=status,
                                       route_position=route_position)
            return meter

        cls.meter_a = supply_point('split-a', active)
        cls.meter_b = supply_point('split-b', active, cls.monthly_position)
        cls.meter_c = supply_point('split-c', removed)

        # Posició on només hi ha un punt de baixa: no s'envia.
        cls.removed_position = RoutePosition.objects.create(route=cls.quarterly, position=2, token='SPLIT-T_2')
        removed_property = Property.objects.create(token='split-removed', route_position=cls.removed_position)
        SupplyPoint.objects.create(token='split-removed-sp', property=removed_property, status=removed,
                                   meter=Meter.objects.create(code='M-REMOVED', status=meter_status))

    def meters_at(self, position, include_disabled=True):
        from unittest.mock import MagicMock, patch
        from lecturapp.serializers import PropertyAppDetailedSerializer

        def fake_serializer(meters, **kwargs):
            return MagicMock(data=[{'id': meter.id} for meter in meters])

        context = {'include_telecontrol': True, 'route_position': position, 'include_disabled_meters': include_disabled}
        with patch('lecturapp.serializers.MeterAppSerializer', side_effect=fake_serializer):
            serializer = PropertyAppDetailedSerializer(context=context)
            data = serializer.get_meters(self.property)
        return {item['id']: item for item in data}

    def test_quarterly_route(self):
        meters = self.meters_at(self.quarterly_position)
        self.assertTrue(meters[self.meter_a.id]['is_readable'])
        self.assertEqual(meters[self.meter_b.id]['disabled_reason'], 'other_route')
        self.assertEqual(meters[self.meter_b.id]['other_route_token'], 'SPLIT-M')
        self.assertEqual(meters[self.meter_b.id]['other_position_token'], 'SPLIT-M_1')
        self.assertEqual(meters[self.meter_c.id]['disabled_reason'], 'supply_point_inactive')

    def test_monthly_route(self):
        meters = self.meters_at(self.monthly_position)
        self.assertTrue(meters[self.meter_b.id]['is_readable'])
        self.assertEqual(meters[self.meter_a.id]['disabled_reason'], 'other_route')
        self.assertEqual(meters[self.meter_a.id]['other_route_token'], 'SPLIT-T')

    def test_old_app_only_gets_readable_meters(self):
        meters = self.meters_at(self.quarterly_position, include_disabled=False)
        self.assertEqual(list(meters), [self.meter_a.id])

    def test_num_meters_counts_only_readable(self):
        from lecturapp.serializers import property_meter_entries

        context = {'include_telecontrol': True, 'route_position': self.quarterly_position}
        readable = [meter for _, meter, reason in property_meter_entries(self.property, context) if reason is None]
        self.assertEqual(readable, [self.meter_a])

    def test_route_skips_positions_with_only_removed_supply_points(self):
        from unittest.mock import patch
        from lecturapp.serializers import RouteAppDetailSerializer

        with patch('lecturapp.serializers.RoutePositionAppDetailedSerializer') as position_serializer:
            RouteAppDetailSerializer(context={'include_telecontrol': True}).get_positions(self.quarterly)
        self.assertEqual(position_serializer.call_args.args[0], [self.quarterly_position])

    def test_full_serialization(self):
        from lecturapp.serializers import PropertyAppDetailedSerializer

        ConfigProject.objects.update_or_create(token='contract_active_token', defaults={'value': 'ACTIVE'})
        context = {'include_telecontrol': True, 'route_position': self.monthly_position, 'reading_batch_id': 1,
                   'include_disabled_meters': True}
        data = PropertyAppDetailedSerializer(self.property, context=context).data
        self.assertEqual(data['num_meters'], 1)
        meters = {item['supply_token']: item for item in data['meters']}
        self.assertEqual(meters['split-b']['is_readable'], True)
        self.assertEqual(meters['split-a']['is_readable'], False)
        self.assertEqual(meters['split-a']['other_position_token'], 'SPLIT-T_1')
        self.assertEqual(set(meters['split-a']) ^ set(meters['split-b']), set())

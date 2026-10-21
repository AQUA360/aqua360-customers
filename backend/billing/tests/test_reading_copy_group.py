from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Reading
from billing.utils.reading_service import get_reading_copy_group, modify_existing_readings
from billing.views.reading_view import ReadingViewSet
from contract.models import Contract, ContractStatus, ContractTerminationRequest
from coredata.models import ConfigProject
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TestReadingCopyGroup(TestCase):
    """
    Readings linked via copied_from (one physical reading copied to several
    contracts) must be modified together when one of them is updated.
    """

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(token='contract_active_token', defaults={'value': 'ACTIVE'})
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': 'TERMINATED'})
        ConfigProject.objects.get_or_create(token='invoice_status_pending_token', defaults={'value': 'PENDING'})
        ConfigProject.objects.get_or_create(token='invoice_status_cancelled_token', defaults={'value': 'CANCELLED'})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.company = Company.objects.create(name='Company copy group')
        cls.user = get_user_model().objects.create_superuser(username='copy-group', password='x', email='')

    def setUp(self):
        self.meter = Meter.objects.create(code='GEN-COPY', status=self.meter_status, is_general=True)
        self.pairs = []
        for i, previous_value in enumerate([100, 90], start=1):
            sp = SupplyPoint.objects.create(token=f'GEN-COPY-SP{i}', meter=self.meter, status=self.sp_status)
            contract = Contract.objects.create(
                company=self.company,
                token=f'GEN-COPY-C{i}',
                status=self.contract_status,
                is_active=True,
                supply_point_default=sp,
            )
            contract.supply_points.add(sp)
            previous = Reading.objects.create(
                meter=self.meter, contract=contract, supply_point=sp,
                reading_date=date(2026, 1, 1), reading_value=previous_value, calculated_value=0,
            )
            self.pairs.append((sp, contract, previous))

        (sp1, c1, prev1), (sp2, c2, prev2) = self.pairs
        self.original = Reading.objects.create(
            meter=self.meter, contract=c1, supply_point=sp1, previous_reading=prev1,
            reading_date=date(2026, 4, 1), reading_value=150, calculated_value=50, consumption_days=90,
        )
        self.copy = Reading.objects.create(
            meter=self.meter, contract=c2, supply_point=sp2, previous_reading=prev2,
            reading_date=date(2026, 4, 1), reading_value=150, calculated_value=60, consumption_days=90,
            copied_from=self.original,
        )

    def test_group_from_original_and_from_copy(self):
        self.assertEqual(list(get_reading_copy_group(self.original)), [self.copy])
        self.assertEqual(list(get_reading_copy_group(self.copy)), [self.original])

    def test_group_excludes_control_readings(self):
        self.copy.is_control = True
        self.copy.save()
        self.assertEqual(get_reading_copy_group(self.original).count(), 0)

    def test_direct_update_syncs_copies(self):
        view = ReadingViewSet.as_view({'patch': 'partial_update'})
        request = APIRequestFactory().patch(
            f'/billing/reading/{self.copy.id}/',
            {'reading_value': 170, 'calculated_value': 80, 'leak_value': 5},
            format='json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.copy.id)
        self.assertEqual(response.status_code, 200, response.data)

        self.original.refresh_from_db()
        self.assertEqual(self.original.reading_value, Decimal('170'))
        self.assertEqual(self.original.leak_value, Decimal('5'))
        # Own previous reading (100) and same manual adjustment (+0)
        self.assertEqual(self.original.calculated_value, Decimal('70'))

    def test_direct_update_without_value_changes_leaves_copies(self):
        view = ReadingViewSet.as_view({'patch': 'partial_update'})
        request = APIRequestFactory().patch(
            f'/billing/reading/{self.copy.id}/',
            {'reading_value': 150, 'calculated_value': 60, 'alert_notes': 'nota'},
            format='json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.copy.id)
        self.assertEqual(response.status_code, 200, response.data)

        self.original.refresh_from_db()
        self.assertEqual(self.original.calculated_value, Decimal('50'))
        self.assertIsNone(self.original.alert_notes)

    def test_modify_existing_readings_replaces_whole_group(self):
        sp2, c2, _ = self.pairs[1]
        modify_existing_readings(
            readings_data=[{
                'supply_point_id': sp2.id,
                'contract_id': c2.id,
                'bag_to_maintain': 0,
                'readings': [{
                    'id': self.copy.id,
                    'reading_date': '2026-04-01',
                    'reading_value': 170,
                    'leak_value': 0,
                    'calculated_value': 80,
                    'consumption_days': 90,
                    'meter_id': self.meter.id,
                    'previous_reading_option_key': '2026-01-01',
                    'origin': 'Modificació',
                }],
            }],
            readings_to_update=[self.copy.id],
        )

        self.original.refresh_from_db()
        self.copy.refresh_from_db()
        self.assertTrue(self.original.is_control)
        self.assertTrue(self.copy.is_control)

        new_original = Reading.objects.get(contract=self.pairs[0][1], reading_date=date(2026, 4, 1), is_control=False)
        new_copy = Reading.objects.get(contract=c2, reading_date=date(2026, 4, 1), is_control=False)
        self.assertEqual(new_original.reading_value, Decimal('170'))
        self.assertEqual(new_original.calculated_value, Decimal('70'))
        self.assertEqual(new_original.previous_reading_id, self.pairs[0][2].id)
        self.assertIsNone(new_original.copied_from_id)
        self.assertEqual(new_copy.copied_from_id, new_original.id)
        self.assertIn(new_original, self.original.modified_readings.all())

    # --- Side effects -------------------------------------------------------

    def _patch(self, reading, data):
        view = ReadingViewSet.as_view({'patch': 'partial_update'})
        request = APIRequestFactory().patch(f'/billing/reading/{reading.id}/', data, format='json')
        force_authenticate(request, user=self.user)
        response = view(request, pk=reading.id)
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def _modify(self, reading, pair_index, **overrides):
        sp, contract, _ = self.pairs[pair_index]
        item = {
            'id': reading.id,
            'reading_date': str(reading.reading_date),
            'reading_value': float(reading.reading_value),
            'leak_value': float(reading.leak_value or 0),
            'calculated_value': float(reading.calculated_value),
            'consumption_days': reading.consumption_days,
            'meter_id': self.meter.id,
            'previous_reading_option_key': '2026-01-01',
            'origin': 'Modificació',
        }
        item.update(overrides)
        modify_existing_readings(
            readings_data=[{'supply_point_id': sp.id, 'contract_id': contract.id, 'bag_to_maintain': 0, 'readings': [item]}],
            readings_to_update=[reading.id],
        )

    def test_direct_update_does_not_touch_copies_already_equal(self):
        # The original already has the leak: saving it on the copy must not
        # re-save the original (that would clear its estimated flag)
        Reading.objects.filter(id=self.original.id).update(leak_value=5, is_estimated=True)
        self._patch(self.copy, {'leak_value': 5})

        self.original.refresh_from_db()
        self.assertTrue(self.original.is_estimated)
        self.assertEqual(self.original.calculated_value, Decimal('50'))

    def test_direct_update_leak_zero_equals_no_leak(self):
        Reading.objects.filter(id=self.original.id).update(is_estimated=True)
        self._patch(self.copy, {'leak_value': 0})

        self.original.refresh_from_db()
        self.assertTrue(self.original.is_estimated)
        self.assertIsNone(self.original.leak_value)

    def test_direct_update_manual_adjustment_applies_to_copies(self):
        # Copy: 150 - 90 = 60 -> set to 65 (manual +5). Original: 150 - 100 + 5
        self._patch(self.copy, {'calculated_value': 65})

        self.original.refresh_from_db()
        self.assertEqual(self.original.calculated_value, Decimal('55'))
        self.assertEqual(self.original.reading_value, Decimal('150'))

    def test_direct_update_reading_without_copies(self):
        _, c1, prev1 = self.pairs[0]
        lonely = Reading.objects.create(
            meter=self.meter, contract=c1, supply_point=self.pairs[0][0], previous_reading=prev1,
            reading_date=date(2026, 7, 1), reading_value=200, calculated_value=50,
        )
        before = {r.id: (r.reading_value, r.calculated_value) for r in Reading.objects.exclude(id=lonely.id)}
        self._patch(lonely, {'reading_value': 210, 'calculated_value': 60})

        lonely.refresh_from_db()
        self.assertEqual(lonely.reading_value, Decimal('210'))
        after = {r.id: (r.reading_value, r.calculated_value) for r in Reading.objects.exclude(id=lonely.id)}
        self.assertEqual(before, after)

    def test_modify_reading_without_copies_creates_single_replacement(self):
        self.copy.copied_from = None
        self.copy.save()
        total = Reading.objects.count()

        self._modify(self.copy, 1, reading_value=170, calculated_value=80)

        self.assertEqual(Reading.objects.count(), total + 1)
        self.original.refresh_from_db()
        self.assertFalse(self.original.is_control)
        self.assertEqual(self.original.reading_value, Decimal('150'))

    def test_modify_contract_only_change_keeps_copies(self):
        # Only the estimated correction (per contract) changes: the original keeps
        # its values, so it is not replaced, only the edited copy is
        total = Reading.objects.count()

        self._modify(self.copy, 1, estimated_used=10)

        self.assertEqual(Reading.objects.count(), total + 1)
        self.original.refresh_from_db()
        self.assertFalse(self.original.is_control)
        new_copy = Reading.objects.get(contract=self.pairs[1][1], reading_date=date(2026, 4, 1), is_control=False)
        self.assertEqual(new_copy.copied_from_id, self.original.id)
        self.assertEqual(get_reading_copy_group(self.original).count(), 1)

    def test_modify_moves_termination_of_linked_reading(self):
        termination = ContractTerminationRequest.objects.create(contract=self.pairs[0][1])
        termination.readings.add(self.original)

        self._modify(self.copy, 1, reading_value=170, calculated_value=80)

        new_original = Reading.objects.get(contract=self.pairs[0][1], reading_date=date(2026, 4, 1), is_control=False)
        self.assertEqual(list(termination.readings.all()), [new_original])

    def test_modify_logs_change_on_linked_contract(self):
        from logger.models import LogReadingChange
        self._modify(self.copy, 1, reading_value=170, calculated_value=80)
        self.assertTrue(LogReadingChange.objects.filter(contract=self.pairs[0][1]).exists())

    def test_copies_count_query_cost(self):
        with self.assertNumQueries(1):
            get_reading_copy_group(self.original).count()
        copy = Reading.objects.get(id=self.copy.id)
        with self.assertNumQueries(2):
            get_reading_copy_group(copy).count()


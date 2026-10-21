from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Invoice, Reading
from billing.views.reading_view import ReadingViewSet
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TestReadingSavePreviousReading(TestCase):
    """
    Creating a reading must only reuse the previous reading when it has no
    value yet. A previous reading with value 0 or already billed must be kept
    untouched and a new reading created instead.
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
        cls.company = Company.objects.create(name='Company save reading')
        cls.user = get_user_model().objects.create_superuser(username='save-reading', password='x', email='')

    def setUp(self):
        self.meter = Meter.objects.create(code='SAVE-READING', status=self.meter_status)
        self.sp = SupplyPoint.objects.create(token='SAVE-READING-SP', meter=self.meter, status=self.sp_status)
        self.contract = Contract.objects.create(
            company=self.company, token='SAVE-READING-C', status=self.contract_status,
            is_active=True, supply_point_default=self.sp,
        )
        self.contract.supply_points.add(self.sp)
        self.first = Reading.objects.create(
            meter=self.meter, contract=self.contract, supply_point=self.sp,
            reading_date=date(2026, 4, 1), reading_value=0, calculated_value=0,
        )

    def _add_previous(self, reading_value):
        return Reading.objects.create(
            meter=self.meter, contract=self.contract, supply_point=self.sp, previous_reading=self.first,
            reading_date=date(2026, 6, 30), reading_value=reading_value, calculated_value=0, consumption_days=90,
        )

    def _create_reading(self, reading_value):
        view = ReadingViewSet.as_view({'post': 'create'})
        request = APIRequestFactory().post('/billing/reading/', {
            'meter': self.meter.id,
            'supply_point': self.sp.id,
            'contract': self.contract.id,
            'reading_date': '2026-09-30',
            'reading_value': reading_value,
            'is_control': False,
            'origin': 'manual',
        }, format='json')
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 201, response.data)
        return Reading.objects.get(id=response.data['id'])

    def test_zero_value_previous_reading_is_kept(self):
        previous = self._add_previous(0)

        new_reading = self._create_reading(0)

        self.assertNotEqual(new_reading.id, previous.id)
        previous.refresh_from_db()
        self.assertEqual(previous.reading_date, date(2026, 6, 30))
        self.assertEqual(new_reading.previous_reading_id, previous.id)
        self.assertEqual(new_reading.consumption_days, 92)

    def test_billed_previous_reading_without_value_is_kept(self):
        previous = self._add_previous(None)
        invoice = Invoice.objects.create(contract=self.contract, type_final='F')
        invoice.readings.add(previous)

        new_reading = self._create_reading(10)

        self.assertNotEqual(new_reading.id, previous.id)
        previous.refresh_from_db()
        self.assertEqual(previous.reading_date, date(2026, 6, 30))
        self.assertIsNone(previous.reading_value)

    def test_previous_reading_without_value_is_reused(self):
        previous = self._add_previous(None)

        new_reading = self._create_reading(10)

        self.assertEqual(new_reading.id, previous.id)
        self.assertEqual(new_reading.reading_date, date(2026, 9, 30))
        self.assertEqual(new_reading.reading_value, Decimal('10'))
        self.assertEqual(Reading.objects.filter(contract=self.contract).count(), 2)

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from billing.models import Reading
from billing.utils.reading_service import (
    get_estimated_reading_minimal_object,
    get_period_start_reading,
)
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject, Person
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TestEstimateAfterMeterChange(TestCase):
    """Estimació d'una lectura poc després d'un canvi de comptador.

    Lectures: real del comptador antic (D-100), tancament del comptador antic i
    inicial del nou (D-16) i lectura del lot sense valor (D-6). El període és de 90 dies.
    """

    @classmethod
    def setUpTestData(cls):
        """Crea el contracte, els dos comptadors i la configuració mínima per estimar."""
        for token, value in [
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('token_meter_status_no_meter', 'NO_METER'),
            ('reading_estimate_limit_percentage', '33'),
        ]:
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})

        company = Company.objects.create(name="Test Company EMC")
        holder = Person.objects.create(name="Holder", surname="EMC", token="holder-emc")
        contract_status, _ = ContractStatus.objects.get_or_create(
            token='ACTIVE', defaults={'name': 'Actiu'}
        )
        sp_status, _ = SupplyPointStatus.objects.get_or_create(
            token='SP_ACTIVE', defaults={'name': 'Actiu'}
        )
        meter_status, _ = MeterStatus.objects.get_or_create(token="1", defaults={'name': "Actiu"})

        cls.old_meter = Meter.objects.create(code="METER-EMC-OLD", status=meter_status)
        cls.new_meter = Meter.objects.create(code="METER-EMC-NEW", status=meter_status)
        cls.supply_point = SupplyPoint.objects.create(
            name="Supply Point EMC", token="SP-EMC", meter=cls.new_meter, status=sp_status
        )
        cls.today = timezone.now().date()
        cls.contract = Contract.objects.create(
            company=company,
            token="CON-EMC",
            total_persons=3,
            registration_date=cls.today - timedelta(days=400),
            status=contract_status,
            is_active=True,
            supply_point_default=cls.supply_point,
            holder=holder,
        )
        cls.contract.supply_points.add(cls.supply_point)
        Contract.objects.filter(id=cls.contract.id).update(
            created_at=timezone.now() - timedelta(days=400)
        )
        cls.contract.refresh_from_db()

    def _reading(self, meter, days_ago, reading_value, **kwargs):
        """Crea una lectura del contracte `days_ago` dies enrere."""
        return Reading.objects.create(
            supply_point=self.supply_point,
            contract=self.contract,
            meter=meter,
            reading_date=self.today - timedelta(days=days_ago),
            reading_value=reading_value,
            calculated_value=0,
            **kwargs,
        )

    def _meter_change(self, days_ago):
        """Crea les dues lectures d'un canvi de comptador i retorna (tancament, inicial)."""
        close = self._reading(self.old_meter, days_ago, 7947, is_close=True)
        initial = self._reading(self.new_meter, days_ago, 0)
        return close, initial

    def test_period_start_skips_meter_change_readings(self):
        """L'inici del període d'una lectura de canvi és l'última lectura real anterior."""
        real = self._reading(self.old_meter, 100, 7918)
        close, initial = self._meter_change(16)

        self.assertEqual(get_period_start_reading(close), real)
        self.assertEqual(get_period_start_reading(initial), real)
        self.assertEqual(get_period_start_reading(real), real)

    def test_estimates_after_recent_meter_change(self):
        """Un canvi recent no bloqueja l'estimació, que parteix del comptador nou."""
        self._reading(self.old_meter, 100, 7918)
        _, initial = self._meter_change(16)
        pending = self._reading(self.new_meter, 6, None)

        reading = get_estimated_reading_minimal_object(
            self.supply_point, self.contract, self.today - timedelta(days=6), None,
            offset_days=90, max_day_limit=self.today,
        )

        self.assertIsNotNone(reading)
        self.assertEqual(reading.id, pending.id)
        self.assertTrue(reading.is_estimated)
        self.assertEqual(reading.previous_reading_id, initial.id)
        self.assertEqual(reading.reading_value, 0)
        # Data nominal: 90 dies des de la lectura real anterior al canvi (D-10).
        self.assertEqual(reading.reading_date, self.today - timedelta(days=10))
        self.assertEqual(reading.consumption_days, 6)

    def test_meter_change_after_nominal_date_uses_requested_date(self):
        """Si el canvi és posterior a la data nominal, s'estima a la data demanada."""
        self._reading(self.old_meter, 100, 7918)
        _, initial = self._meter_change(6)

        reading = get_estimated_reading_minimal_object(
            self.supply_point, self.contract, self.today - timedelta(days=3), None,
            offset_days=90, max_day_limit=self.today,
        )

        self.assertIsNotNone(reading)
        self.assertEqual(reading.previous_reading_id, initial.id)
        self.assertEqual(reading.reading_date, self.today - timedelta(days=3))
        self.assertEqual(reading.consumption_days, 3)

    def test_recent_real_reading_still_blocks_estimate(self):
        """Sense canvi de comptador, una lectura real recent continua bloquejant l'estimació."""
        self._reading(self.old_meter, 100, 7918)
        self._reading(self.new_meter, 16, 7947)

        reading = get_estimated_reading_minimal_object(
            self.supply_point, self.contract, self.today - timedelta(days=6), None,
            offset_days=90, max_day_limit=self.today,
        )

        self.assertIsNone(reading)

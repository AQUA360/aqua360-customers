from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from billing.models import Reading
from billing.serializers.reading_serializer import ReadingSaveSerializer
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject, Person
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TestReadingSaveAlertNotes(TestCase):
    """El comentari (alert_notes) enviat en desar una lectura manual del lot es conserva."""

    @classmethod
    def setUpTestData(cls):
        """Crea un punt de subministrament amb comptador i una lectura prèvia."""
        for token, value in [
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('token_meter_status_no_meter', 'NO_METER'),
        ]:
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        sp_status, _ = SupplyPointStatus.objects.get_or_create(
            token='SP_ACTIVE', defaults={'name': 'Actiu'}
        )
        meter_status, _ = MeterStatus.objects.get_or_create(token="1", defaults={'name': "Actiu"})
        cls.meter = Meter.objects.create(code="METER-NOTES", status=meter_status)
        cls.supply_point = SupplyPoint.objects.create(
            name="Supply Point Notes", token="SP-NOTES", meter=cls.meter, status=sp_status
        )
        cls.today = timezone.now().date()
        contract_status, _ = ContractStatus.objects.get_or_create(
            token='ACTIVE', defaults={'name': 'Actiu'}
        )
        cls.contract = Contract.objects.create(
            company=Company.objects.create(name="Test Company Notes"),
            token="CON-NOTES",
            total_persons=1,
            registration_date=cls.today - timedelta(days=400),
            status=contract_status,
            is_active=True,
            supply_point_default=cls.supply_point,
            holder=Person.objects.create(name="Holder", surname="Notes", token="holder-notes"),
        )
        cls.contract.supply_points.add(cls.supply_point)
        Reading.objects.create(
            supply_point=cls.supply_point,
            contract=cls.contract,
            meter=cls.meter,
            reading_date=cls.today - timedelta(days=90),
            reading_value=100,
            calculated_value=0,
        )

    def _save(self, **extra):
        """Desa una lectura manual pel serializer de desat i retorna la lectura creada."""
        data = {
            'supply_point': self.supply_point.id,
            'meter': self.meter.id,
            'contract': self.contract.id,
            'reading_value': 150,
            'reading_date': self.today.isoformat(),
            'origin': 'manual',
            'is_control': False,
            'is_estimated': False,
            **extra,
        }
        serializer = ReadingSaveSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        return Reading.objects.filter(
            supply_point=self.supply_point, reading_date=self.today
        ).first()

    def test_save_keeps_alert_notes(self):
        """Desar amb comentari el deixa a la lectura."""
        reading = self._save(alert_notes="Comentari de prova")
        self.assertEqual(reading.alert_notes, "Comentari de prova")

    def test_save_without_alert_notes(self):
        """Desar sense comentari no en genera cap."""
        reading = self._save()
        self.assertFalse(reading.alert_notes)

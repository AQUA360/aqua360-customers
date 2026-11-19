from datetime import date

from django.test import TestCase

from billing.models import Reading, ReadingAlert
from contract.models import ContractRequest
from contract.serializers.contract_request_base_serializer import ContractRequestSerializer
from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, Property, Route, RoutePosition, SupplyPoint, SupplyPointStatus


class ContractRequestInitialReadingTest(TestCase):
    """La lectura inicial (inactiva fins a finalitzar l'alta) surt al punt de la sol·licitud,
    perquè en tornar d'un pas anterior no torni a quedar com a pendent."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('reading_alert_unusual_consumption', 'unusual_consumption'),
            ('reading_alert_negative', 'negative'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        for token in ('unusual_consumption', 'negative'):
            ReadingAlert.objects.get_or_create(token=token, defaults={'name': token})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})

    def setUp(self):
        position = RoutePosition.objects.create(route=Route.objects.create())
        prop = Property.objects.create(route_position=position)
        self.meter = Meter.objects.create(code='M-INI', status=self.meter_status)
        self.sp = SupplyPoint.objects.create(token='SP-INI', meter=self.meter, status=self.sp_status, property=prop)
        self.request = ContractRequest.objects.create(supply_point_default=self.sp)
        # Lectura activa més recent del comptador (p. ex. del contracte anterior)
        Reading.objects.create(
            meter=self.meter, supply_point=self.sp, reading_value=50,
            reading_date=date(2026, 10, 1), is_active=True,
        )

    def _representation(self):
        last_active = {'id': 0, 'is_initial': False, 'contract_request_id': None, 'reading_value': 50}
        return {
            'supply_points': [{'id': self.sp.id, 'meter_id': self.meter.id, 'last_meter_reading': dict(last_active)}],
            'supply_point_default': {'id': self.sp.id, 'meter_id': self.meter.id, 'last_meter_reading': dict(last_active)},
        }

    def _initial_reading(self, meter=None, **kwargs):
        return Reading.objects.create(
            contract_request=self.request, meter=meter or self.meter, supply_point=self.sp,
            reading_value=42, is_initial=True, is_active=False, consumption_days=0, **kwargs,
        )

    def test_initial_reading_replaces_last_active_reading(self):
        reading = self._initial_reading(reading_date=date(2026, 9, 1))
        representation = self._representation()

        ContractRequestSerializer()._set_initial_readings(self.request, representation)

        for sp in (representation['supply_points'][0], representation['supply_point_default']):
            self.assertEqual(sp['last_meter_reading']['id'], reading.id)
            self.assertTrue(sp['last_meter_reading']['is_initial'])
            self.assertEqual(sp['last_meter_reading']['contract_request_id'], self.request.id)
            self.assertEqual(sp['last_meter_reading']['reading_value'], 42)

    def test_without_initial_reading_keeps_last_active_reading(self):
        representation = self._representation()

        ContractRequestSerializer()._set_initial_readings(self.request, representation)

        self.assertEqual(representation['supply_points'][0]['last_meter_reading']['id'], 0)

    def test_initial_reading_of_another_meter_is_ignored(self):
        other_meter = Meter.objects.create(code='M-OTHER', status=self.meter_status)
        self._initial_reading(meter=other_meter)
        representation = self._representation()

        ContractRequestSerializer()._set_initial_readings(self.request, representation)

        self.assertEqual(representation['supply_points'][0]['last_meter_reading']['id'], 0)

    def test_initial_reading_of_another_request_is_ignored(self):
        other_request = ContractRequest.objects.create(supply_point_default=self.sp)
        Reading.objects.create(
            contract_request=other_request, meter=self.meter, supply_point=self.sp,
            reading_value=7, is_initial=True, is_active=False, consumption_days=0,
        )
        representation = self._representation()

        ContractRequestSerializer()._set_initial_readings(self.request, representation)

        self.assertEqual(representation['supply_points'][0]['last_meter_reading']['id'], 0)

from datetime import date, datetime

from django.utils import timezone

from django.test import TestCase

from billing.models import Reading
from contract.models import Contract, ContractStatus, ContractTerminationRequest
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from contract.serializers.contract_termination_request_serializer import (
    ContractTerminationRequestSaveSerializer, ContractTerminationRequestSerializer,
)
from coredata.models import ConfigProject
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TerminationLastReadingsTest(TestCase):
    """El valor proposat per a la lectura de tall no pot ser una lectura de control, inactiva ni sense valor."""

    @classmethod
    def setUpTestData(cls):
        # Els senyals de la baixa la necessiten
        ConfigProject.objects.update_or_create(token='contract_terminated_status', defaults={'value': 'LR_TERMINATED'})
        status = ContractStatus.objects.create(token='LR_ACTIVE', name='Actiu')
        sp_status = SupplyPointStatus.objects.create(token='LR_SP', name='Actiu')
        meter = Meter.objects.create(code='METER-LR', status=MeterStatus.objects.create(name='Actiu'))
        cls.sp = SupplyPoint.objects.create(token='SP-LR', status=sp_status, meter=meter)
        cls.contract = Contract.objects.create(
            company=Company.objects.create(name='Company LR'), token='CON-LR', status=status,
            is_active=True, supply_point_default=cls.sp,
        )
        cls.contract.supply_points.add(cls.sp)
        cls.meter = meter
        cls.termination = ContractTerminationRequest.objects.create(contract=cls.contract)

        def reading(day, value, **kwargs):
            return Reading.objects.create(
                contract=cls.contract, supply_point=cls.sp, meter=meter,
                reading_date=date(2026, 9, day), reading_value=value, **kwargs,
            )

        cls.valid = reading(1, 100)
        reading(10, 120, is_control=True)
        reading(20, 130, is_active=False)
        reading(25, None)

    def test_termination_proposes_last_non_control_reading(self):
        readings = ContractTerminationRequestSerializer().get_contract_last_readings(self.termination)

        self.assertEqual([r['id'] for r in readings], [self.valid.id])

    def test_contract_last_readings_skip_control_readings(self):
        readings = ContractMinimalSerializer().get_last_readings(self.contract)

        self.assertEqual([r['id'] for r in readings], [self.valid.id])

    def test_termination_proposal_without_meter(self):
        self.valid.meter = None
        self.valid.save()

        readings = ContractTerminationRequestSerializer().get_contract_last_readings(self.termination)

        self.assertEqual([(r['id'], r['meter']) for r in readings], [(self.valid.id, None)])

    def test_termination_proposal_keeps_supply_point_without_billable_reading(self):
        Reading.objects.filter(id=self.valid.id).update(is_control=True)

        readings = ContractTerminationRequestSerializer().get_contract_last_readings(self.termination)

        # El punt hi és perquè el formulari de la lectura de tall es mostri, amb el valor buit
        self.assertEqual(
            [(r['id'], r['reading_value'], r['supply_point'], r['meter']) for r in readings],
            [(None, None, self.sp.id, self.meter.id)],
        )

    def test_cut_reading_skips_chain_of_readings_without_value(self):
        first_empty = Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.meter,
            reading_date=date(2026, 9, 26), reading_value=None, previous_reading=self.valid,
        )
        second_empty = Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.meter,
            reading_date=date(2026, 9, 27), reading_value=None, previous_reading=first_empty,
        )

        ContractTerminationRequestSaveSerializer().update(self.termination, {
            'last_reading': 150,
            'last_reading_at': timezone.make_aware(datetime(2026, 9, 30)),
            'supply_point_id': self.sp.id,
        })

        cut_reading = self.termination.readings.get()
        self.assertEqual(cut_reading.previous_reading, self.valid)
        self.assertEqual(float(cut_reading.calculated_value), 50)
        first_empty.refresh_from_db()
        second_empty.refresh_from_db()
        self.assertTrue(first_empty.is_control)
        self.assertTrue(second_empty.is_control)

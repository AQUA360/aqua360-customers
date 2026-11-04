from datetime import date

from django.test import TestCase

from billing.models import Reading
from contract.models import Contract, ContractStatus, ContractTerminationRequest
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from contract.serializers.contract_termination_request_serializer import ContractTerminationRequestSerializer
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

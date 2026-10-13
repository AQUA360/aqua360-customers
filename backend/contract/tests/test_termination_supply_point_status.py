from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from contract.models import Contract, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from contract.utils.contract_request_service import check_and_deactivate_supply_point_and_meter
from contract.views.close_contract_termination_request_view import CloseContractTerminationRequestViewSet
from coredata.models import ConfigProject, Person
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TerminationSupplyPointStatusTest(TestCase):
    """En donar de baixa un contracte, el punt sense contractes actius no ha de quedar «Actiu»."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('meter_status_inactive_token', '-1'),
            ('supply_point_status_deactivate_token', 'SP_INACTIVE'),
            ('supply_point_status_not_contractable_token', 'SP_NOT_CONTRACTABLE'),
            ('supply_point_pending_contract', 'SP_PENDING'),
            ('contract_termination_pending_token', 'CT_PENDING'),
            ('contract_termination_completed_token', 'CT_COMPLETED'),
            ('order_status_completed_token', 'OS_COMPLETED'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.active, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Actiu'})
        cls.terminated, _ = ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        cls.meter_active, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.meter_inactive, _ = MeterStatus.objects.get_or_create(token='-1', defaults={'name': 'Inactiu'})
        SupplyPointStatus.objects.update(is_default=False)
        cls.sp_active = SupplyPointStatus.objects.create(token='SP_ACTIVE', name='Actiu')
        cls.sp_pending = SupplyPointStatus.objects.create(token='SP_PENDING', name='Pendent', is_default=True)
        SupplyPointStatus.objects.get_or_create(token='SP_INACTIVE', defaults={'name': 'Desactivat'})
        cls.sp_not_contractable = SupplyPointStatus.objects.create(token='SP_NOT_CONTRACTABLE', name='No contractable')
        ContractTerminationStatus.objects.get_or_create(token='CT_PENDING', defaults={'name': 'Pendent'})
        ContractTerminationStatus.objects.get_or_create(token='CT_COMPLETED', defaults={'name': 'Finalitzada'})
        cls.user = get_user_model().objects.create_superuser('termination-admin', 'termination-admin@example.com', 'x')
        cls.company = Company.objects.create(name='Company termination')
        cls.holder = Person.objects.create(name='Holder', surname='Termination', token='holder-termination')

    def _contract(self, token, supply_point, status):
        contract = Contract.objects.create(
            company=self.company, token=token, status=self.active, is_active=True,
            holder=self.holder, supply_point_default=supply_point,
        )
        contract.supply_points.add(supply_point)
        # update() per no disparar els senyals de baixa (fiances), que aquí no es proven.
        Contract.objects.filter(id=contract.id).update(status=status)
        return contract

    def _terminate(self, contract, supply_point_status=None):
        termination = ContractTerminationRequest.objects.create(contract=contract)
        check_and_deactivate_supply_point_and_meter(termination, supply_point_status)

    def _close(self, contract, supply_point_status):
        termination = ContractTerminationRequest.objects.create(contract=contract)
        request = APIRequestFactory().put(
            f'/contract/contract-termination-request/close/{termination.id}',
            {'status': supply_point_status.id}, format='json',
        )
        force_authenticate(request, user=self.user)
        # La serialització de la resposta (factures, etc.) no és el que es prova aquí.
        with patch('contract.views.close_contract_termination_request_view.ContractTerminationRequestSerializer') as serializer:
            serializer.return_value.data = {}
            response = CloseContractTerminationRequestViewSet.as_view()(request, id=termination.id)
        self.assertEqual(response.status_code, 202)

    def test_without_readings_and_without_meter(self):
        sp = SupplyPoint.objects.create(token='SP-TERM-1', status=self.sp_active)
        contract = self._contract('CON-TERM-1', sp, self.terminated)

        self._terminate(contract)

        sp.refresh_from_db()
        self.assertEqual(sp.status, self.sp_pending)
        self.assertIsNone(sp.removal_at)

    def test_without_readings_with_meter(self):
        meter = Meter.objects.create(code='M-TERM-2', status=self.meter_active)
        sp = SupplyPoint.objects.create(token='SP-TERM-2', status=self.sp_active, meter=meter)
        contract = self._contract('CON-TERM-2', sp, self.terminated)

        self._terminate(contract)

        sp.refresh_from_db()
        meter.refresh_from_db()
        self.assertEqual(sp.status, self.sp_pending)
        self.assertEqual(meter.status, self.meter_inactive)
        self.assertIsNone(meter.uninstallation_at)

    def test_supply_point_with_other_active_contract_stays_active(self):
        sp = SupplyPoint.objects.create(token='SP-TERM-3', status=self.sp_active)
        contract = self._contract('CON-TERM-3', sp, self.terminated)
        self._contract('CON-TERM-3B', sp, self.active)

        self._terminate(contract)

        sp.refresh_from_db()
        self.assertEqual(sp.status, self.sp_active)

    def test_shared_meter_is_not_deactivated(self):
        meter = Meter.objects.create(code='M-TERM-4', status=self.meter_active, is_general=True)
        sp = SupplyPoint.objects.create(token='SP-TERM-4', status=self.sp_active, meter=meter)
        SupplyPoint.objects.create(token='SP-TERM-4B', status=self.sp_active, meter=meter)
        contract = self._contract('CON-TERM-4', sp, self.terminated)

        self._terminate(contract)

        sp.refresh_from_db()
        meter.refresh_from_db()
        self.assertEqual(sp.status, self.sp_pending)
        self.assertEqual(meter.status, self.meter_active)

    def test_selected_status_is_kept(self):
        sp = SupplyPoint.objects.create(token='SP-TERM-5', status=self.sp_active)
        contract = self._contract('CON-TERM-5', sp, self.terminated)

        self._terminate(contract, self.sp_not_contractable)

        sp.refresh_from_db()
        self.assertEqual(sp.status, self.sp_not_contractable)

    def test_without_selected_status_keeps_terminated_status(self):
        # Quan la baixa es completa en tancar les ordres no arriba cap estat: no es trepitja el triat abans.
        sp = SupplyPoint.objects.create(token='SP-TERM-6', status=self.sp_not_contractable)
        contract = self._contract('CON-TERM-6', sp, self.terminated)

        self._terminate(contract)

        sp.refresh_from_db()
        self.assertEqual(sp.status, self.sp_not_contractable)

    def test_close_view_applies_selected_status(self):
        sp = SupplyPoint.objects.create(token='SP-TERM-7', status=self.sp_active)
        contract = self._contract('CON-TERM-7', sp, self.active)

        self._close(contract, self.sp_not_contractable)

        sp.refresh_from_db()
        self.assertEqual(sp.status, self.sp_not_contractable)

    def test_close_view_keeps_status_of_shared_supply_point(self):
        sp = SupplyPoint.objects.create(token='SP-TERM-8', status=self.sp_active)
        contract = self._contract('CON-TERM-8', sp, self.active)
        self._contract('CON-TERM-8B', sp, self.active)

        self._close(contract, self.sp_not_contractable)

        sp.refresh_from_db()
        self.assertEqual(sp.status, self.sp_active)

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Invoice
from contract.models import Contract, ContractRequest, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from contract.utils.contract_service import _rename_old_contract_and_get_reused_token, check_contract_terminations
from contract.views.close_contract_termination_request_view import CloseContractTerminationRequestViewSet
from coredata.models import ConfigProject, Person
from order.models import Order, OrderStatus
from service.models import Company, SupplyPoint, SupplyPointStatus


class FinalizeTerminationFromRequestTest(TestCase):
    """La baixa feta des de l'alta es pot finalitzar directament i queda «sense factura»."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('meter_status_inactive_token', '-1'),
            ('contract_termination_pending_token', 'CT_PENDING'),
            ('contract_termination_completed_token', 'CT_COMPLETED'),
            ('order_status_completed_token', 'OS_COMPLETED'),
            ('contract_termination_pending_status', 'CT_PENDING'),
            ('contract_termination_draft', 'CT_DRAFT'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.active, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Actiu'})
        cls.terminated, _ = ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        cls.sp_status = SupplyPointStatus.objects.create(token='SP_ACTIVE', name='Actiu')
        SupplyPointStatus.objects.get_or_create(is_default=True, defaults={'token': 'SP_DEFAULT', 'name': 'Pendent'})
        cls.ct_pending, _ = ContractTerminationStatus.objects.get_or_create(token='CT_PENDING', defaults={'name': 'Pendent'})
        cls.ct_completed, _ = ContractTerminationStatus.objects.get_or_create(token='CT_COMPLETED', defaults={'name': 'Finalitzada'})
        cls.ct_draft, _ = ContractTerminationStatus.objects.get_or_create(token='CT_DRAFT', defaults={'name': 'Esborrany'})
        cls.os_pending, _ = OrderStatus.objects.get_or_create(token='OS_PENDING', defaults={'name': 'Pendent'})
        # update_termination_status reobre les ordres de les baixes pendents amb aquest estat
        OrderStatus.objects.get_or_create(token='1', defaults={'name': 'Oberta'})
        cls.user = get_user_model().objects.create_superuser('finalize-admin', 'finalize-admin@example.com', 'x')
        cls.company = Company.objects.create(name='Company finalize')
        cls.holder = Person.objects.create(name='Holder', surname='Finalize', token='holder-finalize')

    def _termination(self, token, **kwargs):
        sp = SupplyPoint.objects.create(token=f'SP-{token}', status=self.sp_status)
        contract = Contract.objects.create(
            company=self.company, token=f'CON-{token}', status=self.active, is_active=True,
            holder=self.holder, supply_point_default=sp,
        )
        contract.supply_points.add(sp)
        termination = ContractTerminationRequest.objects.create(contract=contract, status=self.ct_pending, **kwargs)
        # L'alta encara oberta del mateix punt
        contract_request = ContractRequest.objects.create(token=f'CR-{token}', is_active=True)
        contract_request.supply_points.add(sp)
        contract_request.contract_termination_requests.add(termination)
        return contract_request, termination, sp

    def _close(self, termination, data):
        request = APIRequestFactory().put(
            f'/contract/contract-termination-request/close/{termination.id}', data, format='multipart',
        )
        force_authenticate(request, user=self.user)
        with patch('contract.views.close_contract_termination_request_view.ContractTerminationRequestSerializer') as serializer:
            serializer.return_value.data = {}
            response = CloseContractTerminationRequestViewSet.as_view()(request, id=termination.id)
        self.assertEqual(response.status_code, 202)
        termination.refresh_from_db()

    def test_finalized_without_invoice(self):
        _, termination, sp = self._termination('1')

        self._close(termination, {'ignore_invoice': 'true'})

        termination.contract.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual(termination.status, self.ct_completed)
        self.assertTrue(termination.ignore_invoice)
        self.assertEqual(termination.contract.status, self.terminated)
        # L'alta del punt encara és oberta: el punt no es toca
        self.assertEqual(sp.status, self.sp_status)

    def test_close_without_flag_keeps_invoice(self):
        _, termination, _ = self._termination('2')

        self._close(termination, {})

        self.assertEqual(termination.status, self.ct_completed)
        self.assertFalse(termination.ignore_invoice)

    def test_billed_cut_reading_is_not_marked_without_invoice(self):
        _, termination, _ = self._termination('3', bill_cut_reading=True)

        self._close(termination, {'ignore_invoice': 'true'})

        self.assertEqual(termination.status, self.ct_completed)
        self.assertFalse(termination.ignore_invoice)

    def test_existing_invoice_is_not_marked_without_invoice(self):
        _, termination, _ = self._termination('4')
        # bulk_create per no disparar els senyals de factures, que aquí no es proven
        Invoice.objects.bulk_create([Invoice(contract_termination=termination)])

        self._close(termination, {'ignore_invoice': 'true'})

        self.assertFalse(termination.ignore_invoice)

    def test_open_orders_keep_termination_pending(self):
        _, termination, _ = self._termination('5')
        Order.objects.bulk_create([Order(token='ORD-5', status=self.os_pending, contract_termination_request=termination)])

        self._close(termination, {'ignore_invoice': 'true'})

        self.assertEqual(termination.status, self.ct_pending)
        self.assertTrue(termination.ignore_invoice)

    def test_keep_same_code_marks_without_invoice(self):
        # Mantenint el número, la lectura de tall passa al contracte nou: la baixa ja no es factura
        contract_request, termination, _ = self._termination('6', bill_cut_reading=True)

        _rename_old_contract_and_get_reused_token(contract_request)

        termination.refresh_from_db()
        self.assertFalse(termination.bill_cut_reading)
        self.assertTrue(termination.ignore_invoice)

    def _finalize_registration(self, contract_request, sp):
        # En finalitzar l'alta es crea el contracte nou al mateix punt
        new_contract = Contract.objects.create(
            company=self.company, token=f'NEW-{contract_request.token}', status=self.active, is_active=True,
        )
        new_contract.supply_points.add(sp)
        check_contract_terminations(new_contract, contract_request)

    @patch('contract.signals.pending_bail_contract_termination')
    def test_contract_terminated_on_termination_finalize_not_on_registration(self, bail_mock):
        # La fiança es traspassa a saldo quan el contracte passa a baixa: ha de ser en finalitzar la baixa
        for status in (self.ct_draft, self.ct_pending):
            with self.subTest(termination_status=status.token):
                bail_mock.reset_mock()
                contract_request, termination, sp = self._termination(f'7-{status.token}')
                termination.status = status
                termination.save()

                self._finalize_registration(contract_request, sp)

                termination.refresh_from_db()
                termination.contract.refresh_from_db()
                self.assertEqual(termination.status, self.ct_pending)
                self.assertEqual(termination.contract.status, self.active)
                bail_mock.assert_not_called()

                self._close(termination, {})

                termination.contract.refresh_from_db()
                self.assertEqual(termination.contract.status, self.terminated)
                bail_mock.assert_called_once()

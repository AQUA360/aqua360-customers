from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Biller, Billing
from billing.views.billing_view import BillingViewSet
from contract.models import Contract, ContractStatus, ContractTerminationStatus
from coredata.models import ConfigProject, Person
from service.models import Company, Property, Route, RoutePosition, SupplyPoint


class TestCheckMissingBlockBilling(TestCase):
    """Els contractes no facturables no han de sortir a «Possibles contractes no facturats»."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_completed_token', 'COMPLETED'),
            ('invoice_status_pending_token', 'PENDING'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        active, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Actiu'})
        ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        ContractTerminationStatus.objects.get_or_create(token='COMPLETED', defaults={'name': 'Finalitzada'})

        company = Company.objects.create(name='Company check missing')
        holder = Person.objects.create(name='Holder', surname='Check', token='holder-check-missing')
        cls.biller = Biller.objects.create(token='biller-check-missing', name='Biller', period_type='mensual')
        route = Route.objects.create(token='route-check-missing', biller=cls.biller)
        position = RoutePosition.objects.create(route=route, position=1)
        prop = Property.objects.create(token='property-check-missing', route_position=position)

        cls.contracts = {}
        for key, block_billing in (('billable', False), ('blocked', True)):
            sp = SupplyPoint.objects.create(token=f'sp-check-missing-{key}', property=prop)
            contract = Contract.objects.create(
                company=company,
                token=f'CON-CHECK-MISSING-{key}',
                status=active,
                is_active=True,
                holder=holder,
                supply_point_default=sp,
                block_billing=block_billing,
            )
            contract.supply_points.add(sp)
            cls.contracts[key] = contract

        today = timezone.now().date()
        cls.billing = Billing.objects.create(
            token=f'FACT-CHECK-{today.month}{today.year}', biller=cls.biller
        )
        cls.user = get_user_model().objects.create_superuser(
            username='check-missing', password='x', email=''
        )

    def _check_missing(self, params=None):
        request = APIRequestFactory().get(f'/billing/billing/{self.billing.id}/check-missing/', params or {})
        force_authenticate(request, user=self.user)
        view = BillingViewSet.as_view({'get': 'check_missing'})
        response = view(request, pk=self.billing.id)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_block_billing_contracts_are_counted_apart(self):
        data = self._check_missing()

        listed_ids = {c['contract_id'] for c in data['missing_contracts_with_reason']}
        self.assertEqual(listed_ids, {self.contracts['billable'].id})
        self.assertEqual(data['missing_contracts'], 1)
        self.assertEqual(data['missing_by_route'], 1)
        self.assertEqual(data['block_billing'], 1)

    def test_block_billing_contracts_not_in_filtered_list(self):
        data = self._check_missing({'type': 'missing_by_route'})

        listed_ids = {c['contract_id'] for c in data['results']}
        self.assertNotIn(self.contracts['blocked'].id, listed_ids)
        self.assertIn(self.contracts['billable'].id, listed_ids)

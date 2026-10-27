from django.contrib.auth.models import User
from django.db.models import Q
from django.test import TestCase
from rest_framework.test import APIClient

from billing.models import InvoiceStatus, ReadingBatchTemplate
from claimrequest.tasks import _build_claim_request_filters
from claimrequest.utils.claim_request_service import contract_from_finished_request
from contract.models import Contract, ContractRequest, ContractRequestStatus
from coredata.models import ConfigProject, Person
from service.models import Route, RouteZone, SupplyPoint


def q_lookups(q):
    """Totes les condicions (lookup, valor) d'un Q, incloses les dels Q niats."""
    lookups = []
    for child in q.children:
        if isinstance(child, Q):
            lookups.extend(q_lookups(child))
        else:
            lookups.append(child)
    return lookups


class ClaimRequestReadingBatchTemplateFilterTests(TestCase):
    """El filtre de reclamació d'impagats per plantilla de lot de lectura
    restringeix els contractes per la ruta del punt de subministrament."""

    def setUp(self):
        for token in (
            'payment_status_expired_token',
            'payment_status_returned_token',
            'payment_status_endowment_token',
            'payment_status_irrecoverable_token',
            'claim_request_status_accepted_token',
            'claim_request_status_pending_token',
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': token.upper()})
        expired = ConfigProject.objects.get_or_create(
            token='invoice_status_expired_token', defaults={'value': 'EXPIRED'}
        )[0].value
        InvoiceStatus.objects.get_or_create(token=expired, defaults={'name': expired})

    def test_filter_by_reading_batch_template(self):
        filters, *_ = _build_claim_request_filters({'selectedReadingBatchTemplatesIds': [3, 5]})
        self.assertIn(
            ('supply_point_default__property__route_position__route__reading_batch_template__id__in', [3, 5]),
            q_lookups(filters),
        )

    def test_no_filter_without_reading_batch_template(self):
        filters, *_ = _build_claim_request_filters({})
        self.assertFalse(any('reading_batch_template' in lookup for lookup, _ in q_lookups(filters)))


class ContractFromFinishedRequestIdentityTests(TestCase):
    """El codi compartit no n'hi ha prou: el titular i el punt també han de coincidir."""

    def setUp(self):
        ConfigProject.objects.update_or_create(
            token='contract_request_finalize_token', defaults={'value': 'finalitzada'}
        )
        ConfigProject.objects.update_or_create(
            token='contract_terminated_status', defaults={'value': 'baixa'}
        )
        self.finalized = ContractRequestStatus.objects.create(token='finalitzada', name='Finalitzada')
        self.holder = Person.objects.create(token='H1', name='Titular')
        self.other_holder = Person.objects.create(token='H2', name='Altre')
        self.supply_point = SupplyPoint.objects.create(token='SP1')
        self.other_point = SupplyPoint.objects.create(token='SP2')

    def request(self, **kwargs):
        return ContractRequest.objects.create(
            status=self.finalized,
            holder=self.holder,
            supply_point_default=self.supply_point,
            **kwargs,
        )

    def test_accepts_token_when_holder_and_supply_point_match(self):
        request = self.request(token='C-1')
        contract = Contract.objects.create(
            token='C-1', holder=self.holder, supply_point_default=self.supply_point, is_active=True,
        )
        self.assertEqual(contract_from_finished_request(request).id, contract.id)

    def test_rejects_token_when_holder_differs_and_uses_the_matching_contract(self):
        request = self.request(token='C-1')
        Contract.objects.create(
            token='C-1', holder=self.other_holder, supply_point_default=self.supply_point, is_active=True,
        )
        matching = Contract.objects.create(
            token='C-ALT', holder=self.holder, supply_point_default=self.supply_point, is_active=True,
        )
        self.assertEqual(contract_from_finished_request(request).id, matching.id)

    def test_rejects_token_when_supply_point_differs(self):
        request = self.request(token='C-1')
        Contract.objects.create(
            token='C-1', holder=self.holder, supply_point_default=self.other_point, is_active=True,
        )
        self.assertIsNone(contract_from_finished_request(request))


class ReadingBatchTemplateSelectorFilterTests(TestCase):
    """Filtres `route_zone` i `has_routes` del llistat de plantilles de lot de lectura."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_superuser('admin-test', 'admin@test.local', 'x'))

        self.zone_a = RouteZone.objects.create(name='Zona A')
        self.zone_b = RouteZone.objects.create(name='Zona B')
        self.template_a1 = ReadingBatchTemplate.objects.create(name='A/1')
        self.template_a2 = ReadingBatchTemplate.objects.create(name='A/2')
        self.template_b1 = ReadingBatchTemplate.objects.create(name='B/1')
        self.template_empty = ReadingBatchTemplate.objects.create(name='Sense rutes')

        Route.objects.create(name='R1', route_zone=self.zone_a, reading_batch_template=self.template_a1)
        Route.objects.create(name='R2', route_zone=self.zone_a, reading_batch_template=self.template_a1)
        Route.objects.create(name='R3', route_zone=self.zone_a, reading_batch_template=self.template_a2)
        Route.objects.create(name='R4', route_zone=self.zone_b, reading_batch_template=self.template_b1)

    def get_ids(self, query=''):
        response = self.client.get(f'/billing/reading-batch-template/?{query}')
        self.assertEqual(response.status_code, 200)
        return [item['id'] for item in response.json()['results']]

    def test_has_routes_excludes_templates_without_routes(self):
        ids = self.get_ids('has_routes=true')
        self.assertCountEqual(ids, [self.template_a1.id, self.template_a2.id, self.template_b1.id])

    def test_route_zone_filter_without_duplicates(self):
        ids = self.get_ids(f'has_routes=true&route_zone={self.zone_a.id}')
        self.assertCountEqual(ids, [self.template_a1.id, self.template_a2.id])

    def test_without_params_returns_all(self):
        self.assertEqual(len(self.get_ids()), 4)

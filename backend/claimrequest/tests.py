from django.contrib.auth.models import User
from django.db.models import Q
from django.test import TestCase
from rest_framework.test import APIClient

from billing.models import InvoiceStatus, ReadingBatchTemplate
from claimrequest.tasks import _build_claim_request_filters
from coredata.models import ConfigProject
from service.models import Route, RouteZone


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


class ClaimContractsExportTests(TestCase):
    """Columnes calculades de l'exportació de contractes dels llistats de reclamació."""

    def setUp(self):
        from billing.models import Invoice, InvoiceLineItem, Payment, PaymentStatus
        from contract.models import Contract
        from pricing.models import PriceRate
        from service.models import SupplyPoint

        # Els signals de contracte, factura i pagament llegeixen aquests valors en desar.
        for token, value in (
            ('contract_terminated_status', '99'),
            ('payment_status_paid_token', '0'),
            ('payment_status_expired_token', '-1'),
            ('payment_status_returned_token', '-2'),
            ('payment_status_cancelled_token', '-4'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})

        self.supply_point = SupplyPoint.objects.create(token='SP-TEST')
        self.contract = Contract.objects.create(token='C-TEST', supply_point_default=self.supply_point)
        expired = PaymentStatus.objects.get_or_create(token='-1', defaults={'name': 'Vençut'})[0]
        paid = PaymentStatus.objects.get_or_create(token='0', defaults={'name': 'Pagat'})[0]

        return_fee_rate = PriceRate.objects.create(token='RETURN-FEE')
        ConfigProject.objects.update_or_create(
            token='invoice_return_price_rate_token', defaults={'value': return_fee_rate.token}
        )

        def invoice_with_payments(*payments, return_fee=False):
            invoice = Invoice.objects.create(contract=self.contract)
            for payment_status, amount in payments:
                Payment.objects.create(invoice=invoice, status=payment_status, amount=amount)
            if return_fee:
                InvoiceLineItem.objects.create(invoice=invoice, price_rate=return_fee_rate)
            return invoice

        # Dues factures impagades (una amb dos pagaments), una de pagada i una de recàrrec per devolució.
        invoice_with_payments((expired, 10), (expired, 5))
        invoice_with_payments((expired, 20))
        invoice_with_payments((paid, 30))
        invoice_with_payments((expired, 3), return_fee=True)

    def test_unpaid_invoices_exclude_paid_and_return_fee_invoices(self):
        from claimrequest.utils.claim_contract_export_service import unpaid_invoices_count_by_contract_id

        self.assertEqual(unpaid_invoices_count_by_contract_id([self.contract.id]), {self.contract.id: 2})

    def test_supply_cut_date_only_for_open_cuts(self):
        import datetime
        from django.utils import timezone
        from claimrequest.utils.claim_contract_export_service import claim_contracts_export_queryset, _supply_cut_date
        from service.models import SupplyCut, SupplyCutStatus

        # Catàlegs sembrats per migracions: reutilitzar, no duplicar.
        finished = SupplyCutStatus.objects.get_or_create(token='2', defaults={'name': 'Acabat'})[0]
        planned = SupplyCutStatus.objects.get_or_create(token='0', defaults={'name': 'Planificat'})[0]
        closed_cut = SupplyCut.objects.create(
            status=finished, date_start=timezone.make_aware(datetime.datetime(2026, 1, 10, 9)),
        )
        closed_cut.supply_points.add(self.supply_point)

        contract = claim_contracts_export_queryset().get(id=self.contract.id)
        self.assertEqual(_supply_cut_date(contract), '')

        planned_cut = SupplyCut.objects.create(
            status=planned, date_start=timezone.make_aware(datetime.datetime(2026, 11, 5, 9)),
        )
        planned_cut.supply_points.add(self.supply_point)

        contract = claim_contracts_export_queryset().get(id=self.contract.id)
        self.assertEqual(_supply_cut_date(contract), '05/11/2026')

    def test_export_endpoint_queues_download_job(self):
        from documentmanager.models import ExportJob

        client = APIClient()
        client.force_authenticate(User.objects.create_user('no-perms', 'no-perms@test.local', 'x'))
        url = '/claimrequest/claim-request-manage/contracts-export/'
        self.assertEqual(client.post(url, {'contract_ids': [self.contract.id]}, format='json').status_code, 403)

        client.force_authenticate(User.objects.create_superuser('admin-export', 'admin-export@test.local', 'x'))
        self.assertEqual(client.post(url, {'contract_ids': []}, format='json').status_code, 400)
        response = client.post(url, {'contract_ids': [self.contract.id, self.contract.id]}, format='json')
        self.assertEqual(response.status_code, 202)
        job = ExportJob.objects.get(id=response.data['export_job_id'])
        self.assertEqual(job.kind, 'claim_contracts')
        self.assertEqual(job.params, {'total': 1})

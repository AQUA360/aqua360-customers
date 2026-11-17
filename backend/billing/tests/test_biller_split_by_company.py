"""Facturadors separats per empresa (`Biller.split_by_company`) i facturadors normals.

Cobreix la creació de facturacions (manual i Celery), l'assignació de lectures dels
lots, el repartiment de lectures de comptador general i quan un lot passa a facturat.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Biller, Billing, BillingStatus, Reading, ReadingBatch
from billing.tasks import create_billings
from billing.utils.billing_creation_service import split_companies_for_biller
from billing.utils.reading_batch_billing_service import fully_billed_batches
from billing.views.billing_preinvoices_assign_readings_view import BillingPreInvoicesAssignReadingsViewSet
from billing.views.billing_view import BillingViewSet, StartBillingView
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import (
    Company, Connection, Exploitation, Meter, MeterStatus, Route, RoutePosition,
    SupplyPoint, SupplyPointStatus,
)

TODAY = datetime.date(2026, 11, 13)


class SplitFixtures:
    """Explotació amb dues empreses proveïdores (A vinculada, B només amb contractes),
    una empresa no proveïdora i una proveïdora inactiva."""

    @classmethod
    def build(cls):
        cls.default_status, _ = BillingStatus.objects.update_or_create(
            token='split-default', defaults={'name': 'Oberta', 'is_default': True}
        )
        ConfigProject.objects.update_or_create(token='contract_active_token', defaults={'value': 'SPLIT-ACTIVE'})
        ConfigProject.objects.update_or_create(token='supply_point_status_activate_token', defaults={'value': 'SPLIT-SP'})
        for token, value in (
            ('contract_terminated_status', 'SPLIT-TERMINATED'),
            ('contract_termination_completed_token', 'SPLIT-TERM-DONE'),
            ('billing_batch_pending', 'SPLIT-PENDING'),
            ('reading_estimate_limit_percentage', '33'),
        ):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='SPLIT-ACTIVE', defaults={'name': 'Actiu'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SPLIT-SP', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='SPLIT-METER', defaults={'name': 'Actiu'})

        cls.company_a = Company.objects.create(name='Empresa A', alias='EMP A', is_provider=True)
        cls.company_b = Company.objects.create(name='Empresa B', is_provider=True)
        cls.not_provider = Company.objects.create(name='No proveidora', is_provider=False)
        cls.inactive_provider = Company.objects.create(name='Inactiva', is_provider=True, is_active=False)

        cls.exploitation = Exploitation.objects.create(name='Explotacio', token='split-expl', company=cls.company_a)
        cls.exploitation.companies.add(cls.company_a, cls.inactive_provider)
        cls.other_exploitation = Exploitation.objects.create(name='Altra', token='split-other')
        cls.other_provider = Company.objects.create(name='Altra proveidora', is_provider=True)
        cls.other_exploitation.companies.add(cls.other_provider)

        cls.connection = Connection.objects.create(exploitation=cls.exploitation)

        cls.normal_biller = Biller.objects.create(
            token='NORMAL', name='Normal', period_type='mensual', exploitation=cls.exploitation
        )
        cls.split_biller = Biller.objects.create(
            token='SPLIT', name='Split', period_type='mensual', exploitation=cls.exploitation,
            split_by_company=True,
        )
        cls.route = Route.objects.create(name='Ruta split', biller=cls.split_biller)
        cls.position = RoutePosition.objects.create(route=cls.route)

        cls.contract_a = cls.make_contract('A', cls.company_a)
        cls.contract_b = cls.make_contract('B', cls.company_b)
        cls.contract_none = cls.make_contract('NONE', None)
        cls.contract_other_expl = cls.make_contract('OTHER', cls.not_provider)

        cls.user = get_user_model().objects.create_superuser(username='split-user', password='x', email='')

    @classmethod
    def make_contract(cls, suffix, company, meter=None):
        meter = meter or Meter.objects.create(code=f'SPLIT-M-{suffix}', status=cls.meter_status)
        sp = SupplyPoint.objects.create(
            token=f'SPLIT-SP-{suffix}', meter=meter, status=cls.sp_status,
            connection=cls.connection, route_position=cls.position,
        )
        contract = Contract.objects.create(
            token=f'SPLIT-C-{suffix}', company=company, status=cls.contract_status,
            is_active=True, supply_point_default=sp, language='ca',
            registration_date=TODAY - datetime.timedelta(days=400),
        )
        contract.supply_points.add(sp)
        return contract

    def start(self, biller, params=None):
        request = APIRequestFactory().get('/billing/start/', {'biller_id': biller.id, **(params or {})})
        force_authenticate(request, user=self.user)
        with mock.patch('billing.views.billing_view.timezone.localdate', return_value=TODAY):
            return StartBillingView.as_view(http_method_names=['get'])(request)


class TestBillingCreation(SplitFixtures, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.build()

    def test_split_companies_are_exploitation_providers(self):
        companies = split_companies_for_biller(self.split_biller)
        # A per vincle, B per contractes; no la no proveïdora, ni la inactiva, ni la d'una altra explotació.
        self.assertEqual(companies, [self.company_a, self.company_b])

    def test_split_companies_without_exploitation_uses_all_active_providers(self):
        biller = Biller.objects.create(token='NOEXPL', name='Sense', split_by_company=True)
        self.assertEqual(
            set(split_companies_for_biller(biller)),
            {self.company_a, self.company_b, self.other_provider},
        )

    def test_normal_biller_creates_one_billing_without_company(self):
        response = self.start(self.normal_biller)

        self.assertEqual(response.status_code, 200, response.data)
        billings = Billing.objects.filter(biller=self.normal_biller)
        self.assertEqual(billings.count(), 1)
        billing = billings.get()
        self.assertIsNone(billing.company)
        self.assertEqual(response.data['ids'], [billing.id])
        now = timezone.now().date()
        self.assertEqual(billing.token, f'NORMAL-{now.month}{now.year}')

    def test_split_biller_creates_one_billing_per_company(self):
        response = self.start(self.split_biller)

        self.assertEqual(response.status_code, 200, response.data)
        billings = list(Billing.objects.filter(biller=self.split_biller).order_by('company_id'))
        self.assertEqual([b.company for b in billings], [self.company_a, self.company_b])
        self.assertEqual(sorted(response.data['ids']), sorted(b.id for b in billings))
        self.assertTrue(billings[0].token.endswith('-EMP_A'))
        self.assertTrue(billings[1].token.endswith(f'-{self.company_b.id}'))
        self.assertTrue(billings[0].name.endswith(' - EMP A'))
        for billing in billings:
            self.assertEqual(list(billing.routes.all()), [self.route])
            self.assertEqual(billing.period_start, datetime.date(2026, 10, 1))

    def test_split_biller_with_custom_code(self):
        response = self.start(self.split_biller, {'token': 'T3', 'name': 'Fact T3'})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            sorted(Billing.objects.filter(biller=self.split_biller).values_list('token', flat=True)),
            sorted(['T3-EMP_A', f'T3-{self.company_b.id}']),
        )

    def test_split_custom_code_in_use_creates_nothing(self):
        Billing.objects.create(token=f'T3-{self.company_b.id}', name='Existent', is_active=True)

        response = self.start(self.split_biller, {'token': 'T3', 'name': 'Fact T3'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Billing.objects.filter(biller=self.split_biller).exists())

    def test_split_auto_code_is_deduplicated(self):
        self.start(self.split_biller)
        response = self.start(self.split_biller)

        self.assertEqual(response.status_code, 200, response.data)
        tokens = list(Billing.objects.filter(biller=self.split_biller).values_list('token', flat=True))
        self.assertEqual(len(tokens), 4)
        self.assertEqual(len(set(tokens)), 4)

    def test_split_without_providers_is_rejected(self):
        exploitation = Exploitation.objects.create(name='Buida', token='split-empty')
        biller = Biller.objects.create(token='EMPTY', name='Buit', period_type='mensual',
                                       exploitation=exploitation, split_by_company=True)

        response = self.start(biller)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Billing.objects.filter(biller=biller).exists())

    def test_celery_create_billings_splits_and_keeps_normal(self):
        Biller.objects.exclude(id__in=[self.normal_biller.id, self.split_biller.id]).update(is_active=False)

        create_billings()

        self.assertEqual(
            list(Billing.objects.filter(biller=self.normal_biller).values_list('company_id', flat=True)),
            [None],
        )
        self.assertEqual(
            sorted(Billing.objects.filter(biller=self.split_biller).values_list('company_id', flat=True)),
            sorted([self.company_a.id, self.company_b.id]),
        )


class TestReadingAssignment(SplitFixtures, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.build()
        cls.batch = ReadingBatch.objects.create(token='SPLIT-BATCH', name='Lot')
        cls.batch.routes.add(cls.route)

    def setUp(self):
        self.readings = {
            key: Reading.objects.create(
                batch=self.batch, contract=contract, supply_point=contract.supply_point_default,
                meter=contract.supply_point_default.meter, reading_date=TODAY, reading_value=10,
            )
            for key, contract in (('a', self.contract_a), ('b', self.contract_b), ('none', self.contract_none))
        }

    def make_billing(self, company=None, biller=None):
        billing = Billing.objects.create(
            token=f'BILL-{company.id if company else "ALL"}', name='Billing',
            biller=biller or self.split_biller, company=company, status=self.default_status,
        )
        billing.routes.set([self.route])
        return billing

    def assign(self, billing):
        request = APIRequestFactory().post(
            f'/billing/billing/pre-invoices/{billing.id}/assign-readings',
            {'reading_batch_ids': [self.batch.id]}, format='json',
        )
        force_authenticate(request, user=self.user)
        return BillingPreInvoicesAssignReadingsViewSet.as_view()(request, id=billing.id)

    def billing_of(self, key):
        return Reading.objects.get(id=self.readings[key].id).billing_id

    def test_normal_billing_takes_all_readings(self):
        billing = self.make_billing(biller=self.normal_biller)

        response = self.assign(billing)

        self.assertEqual(response.data['num_assigned_readings'], 3)
        self.assertEqual({self.billing_of(k) for k in self.readings}, {billing.id})

    def test_company_billings_only_take_their_contracts(self):
        billing_a = self.make_billing(self.company_a)
        billing_b = self.make_billing(self.company_b)

        self.assertEqual(self.assign(billing_a).data['num_assigned_readings'], 1)
        self.assertEqual(self.assign(billing_b).data['num_assigned_readings'], 1)

        self.assertEqual(self.billing_of('a'), billing_a.id)
        self.assertEqual(self.billing_of('b'), billing_b.id)
        self.assertIsNone(self.billing_of('none'))

    def test_reassigning_does_not_steal_other_company_readings(self):
        billing_a = self.make_billing(self.company_a)
        billing_b = self.make_billing(self.company_b)
        self.assign(billing_a)
        self.assign(billing_b)

        self.assign(billing_a)

        self.assertEqual(self.billing_of('b'), billing_b.id)

    def test_add_to_batch_rejects_other_company_contract(self):
        billing_a = self.make_billing(self.company_a)
        request = APIRequestFactory().post(
            f'/billing/billing/{billing_a.id}/add-to-batch/', {'contract_id': self.contract_b.id}, format='json',
        )
        force_authenticate(request, user=self.user)

        response = BillingViewSet.as_view({'post': 'add_to_batch'})(request, pk=billing_a.id)

        self.assertEqual(response.status_code, 400)


class TestGeneralMeterSplit(SplitFixtures, TestCase):
    """Un comptador general compartit per contractes de dues empreses."""

    @classmethod
    def setUpTestData(cls):
        cls.build()
        cls.general = Meter.objects.create(code='SPLIT-GEN', status=cls.meter_status, is_general=True)
        cls.gen_a = cls.make_contract('GA', cls.company_a, meter=cls.general)
        cls.gen_b = cls.make_contract('GB', cls.company_b, meter=cls.general)
        cls.batch = ReadingBatch.objects.create(token='SPLIT-GEN-BATCH', name='Lot general')

    def setUp(self):
        self.canonical = Reading.objects.create(
            batch=self.batch, meter=self.general, reading_date=TODAY,
            reading_value=300, calculated_value=300,
        )
        self.billing_a = Billing.objects.create(token='GEN-A', name='A', biller=self.split_biller,
                                                company=self.company_a, status=self.default_status)
        self.billing_b = Billing.objects.create(token='GEN-B', name='B', biller=self.split_biller,
                                                company=self.company_b, status=self.default_status)
        for billing in (self.billing_a, self.billing_b):
            billing.routes.set([self.route])

    def assign(self, billing):
        request = APIRequestFactory().post('/x', {'reading_batch_ids': [self.batch.id]}, format='json')
        force_authenticate(request, user=self.user)
        return BillingPreInvoicesAssignReadingsViewSet.as_view()(request, id=billing.id)

    def contract_billing(self, contract):
        return set(Reading.objects.filter(meter=self.general, contract=contract).values_list('billing_id', flat=True))

    @mock.patch('billing.utils.reading_service.check_billing_period', return_value=True)
    def test_each_company_billing_gets_its_own_contract_reading(self, _check):
        self.assign(self.billing_a)
        self.assign(self.billing_b)

        self.canonical.refresh_from_db()
        self.assertEqual(self.canonical.billing_id, self.billing_a.id)  # la primera se la queda
        self.assertEqual(self.contract_billing(self.gen_a), {self.billing_a.id})
        self.assertEqual(self.contract_billing(self.gen_b), {self.billing_b.id})
        for reading in Reading.objects.filter(meter=self.general, contract__isnull=False):
            self.assertEqual(reading.batch_id, self.batch.id)
            self.assertEqual(reading.copied_from_id, self.canonical.id)

    @mock.patch('billing.utils.reading_service.check_billing_period', return_value=True)
    def test_fanout_is_idempotent_and_never_steals_the_canonical(self, _check):
        from billing.utils.reading_service import fanout_general_meter_readings
        self.assign(self.billing_a)
        self.assign(self.billing_b)

        fanout_general_meter_readings(self.billing_a)
        fanout_general_meter_readings(self.billing_b)
        self.assign(self.billing_b)

        self.canonical.refresh_from_db()
        self.assertEqual(self.canonical.billing_id, self.billing_a.id)
        self.assertEqual(Reading.objects.filter(meter=self.general, contract=self.gen_a).count(), 1)
        self.assertEqual(Reading.objects.filter(meter=self.general, contract=self.gen_b).count(), 1)

    @mock.patch('billing.utils.reading_service.check_billing_period', return_value=True)
    def test_normal_billing_fans_out_to_every_contract(self, _check):
        billing = Billing.objects.create(token='GEN-ALL', name='Tots', biller=self.normal_biller,
                                         status=self.default_status)
        billing.routes.set([self.route])
        self.assign(billing)
        from billing.utils.reading_service import fanout_general_meter_readings
        fanout_general_meter_readings(billing)

        self.assertEqual(self.contract_billing(self.gen_a), {billing.id})
        self.assertEqual(self.contract_billing(self.gen_b), {billing.id})


class TestBatchBilledRule(TestCase):
    """Un lot només passa a facturat quan totes les seves facturacions estan processades."""

    @classmethod
    def setUpTestData(cls):
        cls.processed = BillingStatus.objects.create(token='SPLIT-PROCESSED', name='Processada')
        cls.pending = BillingStatus.objects.create(token='SPLIT-PENDING', name='Pendent')
        cls.cancelled = BillingStatus.objects.create(token='-1', name='Cancel·lada')

    def setUp(self):
        self.batch = ReadingBatch.objects.create(token='RULE', name='Lot')
        self.billing_a = Billing.objects.create(token='RULE-A', status=self.processed)
        self.billing_b = Billing.objects.create(token='RULE-B', status=self.pending)

    def add_reading(self, billing):
        Reading.objects.create(batch=self.batch, billing=billing, reading_date=TODAY)

    def is_billed(self):
        batches = ReadingBatch.objects.filter(id=self.batch.id)
        return fully_billed_batches(batches, self.processed.token).exists()

    def test_single_billing_processed(self):
        self.add_reading(self.billing_a)
        self.assertTrue(self.is_billed())

    def test_waits_for_every_billing(self):
        self.add_reading(self.billing_a)
        self.add_reading(self.billing_b)
        self.assertFalse(self.is_billed())

        self.billing_b.status = self.processed
        self.billing_b.save()
        self.assertTrue(self.is_billed())

    def test_billing_without_status_blocks(self):
        self.add_reading(self.billing_a)
        self.add_reading(Billing.objects.create(token='RULE-NULL'))
        self.assertFalse(self.is_billed())

    def test_cancelled_inactive_and_excluded_billings_do_not_block(self):
        self.add_reading(self.billing_a)
        self.add_reading(Billing.objects.create(token='RULE-C', status=self.cancelled))
        self.add_reading(Billing.objects.create(token='RULE-I', status=self.pending, is_active=False))
        self.add_reading(Billing.objects.create(token='RULE-X', status=self.pending, is_excluded=True))
        self.assertTrue(self.is_billed())

    def test_inactive_reading_does_not_block(self):
        self.add_reading(self.billing_a)
        Reading.objects.create(batch=self.batch, billing=self.billing_b, reading_date=TODAY, is_active=False)
        self.assertTrue(self.is_billed())

    def test_configured_cancelled_token_does_not_block(self):
        ConfigProject.objects.update_or_create(token='billing_batch_cancelled', defaults={'value': 'SPLIT-CANC'})
        cancelled = BillingStatus.objects.create(token='SPLIT-CANC', name='Cancel·lada')
        self.add_reading(self.billing_a)
        self.add_reading(Billing.objects.create(token='RULE-CC', status=cancelled))
        self.assertTrue(self.is_billed())

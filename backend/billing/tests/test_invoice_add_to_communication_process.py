from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Invoice, InvoiceStatus, Reading
from billing.views.invoice_view import InvoiceViewSet
from communication.models import CommunicationProcess, CommunicationProcessStatus, CommunicationUseType
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Company, Connection, Exploitation, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TestInvoiceAddToCommunicationProcess(TestCase):
    """Afegir a la comunicació de fuita les lectures no de control d'una factura."""

    @classmethod
    def setUpTestData(cls):
        for token, value in {
            'communication_process_status_draft_token': 'DRAFT',
            'communication_process_status_cancelled_token': 'CANCELLED',
            'communication_use_type_reading': 'READING',
            'contract_active_token': 'ACTIVE',
            'contract_terminated_status': 'TERMINATED',
            'invoice_status_pending_token': 'PENDING',
            'invoice_status_paid_token': 'PAID',
            'invoice_status_cancelled_token': 'CANCELLED',
        }.items():
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        cfg = lambda token: ConfigProject.objects.get(token=token).value
        cls.draft, _ = CommunicationProcessStatus.objects.get_or_create(
            token=cfg('communication_process_status_draft_token'), defaults={'name': 'Esborrany'})
        cls.cancelled, _ = CommunicationProcessStatus.objects.get_or_create(
            token=cfg('communication_process_status_cancelled_token'), defaults={'name': 'Anul·lat'})
        cls.use_type, _ = CommunicationUseType.objects.get_or_create(
            token=cfg('communication_use_type_reading'), defaults={'name': 'Lectura'})
        cls.user = get_user_model().objects.create_superuser(username='inv-comm', password='x', email='')
        cls.status = InvoiceStatus.objects.create(token='PENDING', name='Pendent', position=1)
        meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        company = Company.objects.create(name='Company inv comm')
        exploitation = Exploitation.objects.create(name='EXP-INV-COMM')
        connection = Connection.objects.create(exploitation=exploitation)
        cls.meter = Meter.objects.create(code='INV-COMM', status=meter_status)
        cls.sp = SupplyPoint.objects.create(token='INV-COMM-SP', meter=cls.meter, status=sp_status, connection=connection)
        cls.contract = Contract.objects.create(
            company=company, token='INV-COMM-C', status=contract_status, is_active=True, supply_point_default=cls.sp,
        )

    def make_reading(self, **extra):
        return Reading.objects.create(
            contract=self.contract, supply_point=self.sp, meter=self.meter,
            reading_date=date(2026, 4, 1), reading_value=0, calculated_value=10, consumption_days=30, **extra,
        )

    def make_invoice(self, *readings):
        invoice = Invoice.objects.create(token='INV-COMM', status=self.status)
        invoice.readings.add(*readings)
        return invoice

    def post(self, invoice, user=None):
        view = InvoiceViewSet.as_view({'post': 'add_to_communication_process'}, **InvoiceViewSet.add_to_communication_process.kwargs)
        request = APIRequestFactory().post(f'/billing/invoice/{invoice.id}/add-to-communication-process/')
        force_authenticate(request, user=user or self.user)
        return view(request, pk=invoice.id)

    def test_adds_readings_and_ignores_control(self):
        normal, other, control = self.make_reading(), self.make_reading(), self.make_reading(is_control=True)
        invoice = self.make_invoice(normal, other, control)
        response = self.post(invoice)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_possible_leak_comm'])
        self.assertEqual(response.data['added_count'], 2)
        process = CommunicationProcess.objects.get()
        self.assertEqual(set(process.readings.all()), {normal, other})

    def test_idempotent(self):
        invoice = self.make_invoice(self.make_reading())
        self.post(invoice)
        response = self.post(invoice)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['added_count'], 0)
        self.assertEqual(CommunicationProcess.objects.count(), 1)
        self.assertEqual(CommunicationProcess.objects.get().readings.count(), 1)

    def test_does_not_duplicate_reading_already_in_process(self):
        already, new = self.make_reading(), self.make_reading()
        process = CommunicationProcess.objects.create(status=self.draft, use_type=self.use_type)
        process.readings.add(already)
        response = self.post(self.make_invoice(already, new))
        self.assertEqual(response.data['added_count'], 1)
        self.assertEqual(CommunicationProcess.objects.count(), 1)
        self.assertEqual(set(process.readings.all()), {already, new})

    def test_reading_only_in_cancelled_process_is_added_again(self):
        reading = self.make_reading()
        cancelled = CommunicationProcess.objects.create(status=self.cancelled, use_type=self.use_type)
        cancelled.readings.add(reading)
        response = self.post(self.make_invoice(reading))
        self.assertEqual(response.data['added_count'], 1)
        self.assertEqual(reading.communication_processes.exclude(status=self.cancelled).count(), 1)

    def test_invoice_without_readings(self):
        self.assertEqual(self.post(self.make_invoice()).status_code, 400)
        self.assertEqual(CommunicationProcess.objects.count(), 0)

    def test_user_without_permission_is_forbidden(self):
        invoice = self.make_invoice(self.make_reading())
        user = get_user_model().objects.create_user(username='inv-comm-noperm', password='x', email='')
        self.assertEqual(self.post(invoice, user=user).status_code, 403)
        self.assertEqual(CommunicationProcess.objects.count(), 0)

    def test_user_with_change_permission_is_allowed(self):
        invoice = self.make_invoice(self.make_reading())
        user = get_user_model().objects.create_user(username='inv-comm-perm', password='x', email='')
        user.user_permissions.add(Permission.objects.get(codename='change_communicationprocess'))
        response = self.post(invoice, user=user)
        self.assertEqual(response.status_code, 200)

    def test_skips_readings_without_supply_point_or_connection(self):
        ok = self.make_reading()
        no_supply_point = Reading.objects.create(
            contract=self.contract, meter=self.meter, reading_date=date(2026, 4, 1),
            reading_value=0, calculated_value=10, consumption_days=30,
        )
        no_connection_sp = SupplyPoint.objects.create(token='INV-COMM-SP-NC', status=self.sp.status)
        no_connection = self.make_reading()
        Reading.objects.filter(pk=no_connection.pk).update(supply_point=no_connection_sp)
        response = self.post(self.make_invoice(ok, no_supply_point, no_connection))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['added_count'], 1)
        self.assertEqual(response.data['skipped_count'], 2)
        self.assertEqual(set(CommunicationProcess.objects.get().readings.all()), {ok})

    def test_nothing_to_add_returns_zero_counts(self):
        control = self.make_reading(is_control=True)
        response = self.post(self.make_invoice(self.make_reading(), control))
        self.assertEqual(response.data['added_count'], 1)
        only_skipped = Reading.objects.create(
            contract=self.contract, meter=self.meter, reading_date=date(2026, 4, 1),
            reading_value=0, calculated_value=10, consumption_days=30,
        )
        invoice = Invoice.objects.create(token='INV-COMM-2', status=self.status)
        invoice.readings.add(only_skipped)
        response = self.post(invoice)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['added_count'], 0)
        self.assertEqual(response.data['skipped_count'], 1)
        self.assertFalse(response.data['has_possible_leak_comm'])

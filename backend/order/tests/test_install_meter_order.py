from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import Reading
from contract.models import Contract, ContractRequest, ContractStatus
from contract.utils.contract_service import _create_meter_installation_order
from coredata.models import ConfigProject
from order.models import Order, OrderStatus, OrderType
from order.services.change_meter import OrderChangeMeterValidationService
from service.models import Meter, MeterStatus, SupplyPoint

MAPPING = [
    {'customers_field': 'meter_old', 'form_field': 'old'},
    {'customers_field': 'reading_old', 'form_field': 'r_old'},
    {'customers_field': 'meter_new', 'form_field': 'new'},
    {'customers_field': 'reading_new', 'form_field': 'r_new'},
]


class InstallMeterOrderTest(TestCase):
    """Alta sense comptador: ordre d'instal·lació i aplicació del comptador des de l'ordre."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('meter_status_active_token', '1'),
            ('meter_status_inactive_token', '-1'),
            ('token_meter_status_no_meter', 'NO_METER'),
            ('order_status_pending_token', 'PENDING'),
            ('order_status_completed_token', 'COMPLETED'),
            ('contract_terminated_status', '99'),
            ('invoice_status_cancelled_token', 'cancelled'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        ConfigProject.objects.filter(token='order_type_install_meter_token').delete()
        cls.status_active, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.status_inactive, _ = MeterStatus.objects.get_or_create(token='-1', defaults={'name': 'Inactiu'})
        cls.status_no_meter, _ = MeterStatus.objects.get_or_create(token='NO_METER', defaults={'name': 'Sense comptador'})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Actiu'})
        cls.pending, _ = OrderStatus.objects.get_or_create(token='PENDING', defaults={'name': 'Pendent'})
        cls.install_type, _ = OrderType.objects.get_or_create(token='install_meter', defaults={'name': 'Instal·lació'})
        cls.change_type, _ = OrderType.objects.get_or_create(token='change_meter', defaults={'name': 'Canvi'})
        cls.user = get_user_model().objects.create_user(username='install-meter-order', password='x')

    def setUp(self):
        self.fictitious = Meter.objects.create(code='SC-1', token='SC-1', status=self.status_no_meter)
        self.new_meter = Meter.objects.create(code='NEW-1', status=self.status_inactive)
        self.sp = SupplyPoint.objects.create(token='SP-INSTALL', meter=self.fictitious)
        self.request = ContractRequest.objects.create(supply_point_default=self.sp, meter_mode='none')
        self.contract = Contract.objects.create(status=self.contract_status, contract_request=self.request)
        self.contract.supply_points.add(self.sp)

    def _service(self, order, answers):
        service = OrderChangeMeterValidationService(order)
        service._field_mapping = lambda: MAPPING
        service._all_answers = lambda: answers
        return service

    def test_creates_installation_order_linked_to_contract(self):
        order = _create_meter_installation_order(self.user, self.contract, self.request, self.sp)

        self.assertEqual(order.type, self.install_type)
        self.assertEqual(order.status, self.pending)
        self.assertEqual(order.contract, self.contract)
        self.assertEqual(order.contract_request, self.request)
        self.assertEqual(order.supply_point, self.sp)

    def test_reuses_installation_order_of_the_request(self):
        existing = Order.objects.create(token='CR-EXISTING', type=self.install_type, contract_request=self.request)

        order = _create_meter_installation_order(self.user, self.contract, self.request, self.sp)

        self.assertEqual(order.id, existing.id)
        self.assertEqual(Order.objects.filter(contract_request=self.request).count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.contract, self.contract)
        self.assertEqual(existing.supply_point, self.sp)

    def test_without_installation_order_type_creates_nothing(self):
        ConfigProject.objects.create(token='order_type_install_meter_token', value='missing_type')

        self.assertIsNone(_create_meter_installation_order(self.user, self.contract, self.request, self.sp))
        self.assertFalse(Order.objects.filter(contract_request=self.request).exists())

    def test_installation_does_not_require_outgoing_meter(self):
        order = Order.objects.create(token='INST-1', type=self.install_type, supply_point=self.sp)
        service = self._service(order, {'new': 'NEW-1', 'r_new': ''})

        self.assertEqual(service.validate(), {'can_apply': True, 'missing_fields': []})
        preview = service.preview()
        self.assertTrue(preview['is_installation'])
        self.assertTrue(preview['meter_old']['matches'])

    def test_change_meter_still_requires_outgoing_meter(self):
        order = Order.objects.create(token='CHG-1', type=self.change_type, supply_point=self.sp)
        service = self._service(order, {'new': 'NEW-1', 'r_new': ''})

        self.assertEqual(service.validate()['missing_fields'], ['old', 'r_old'])
        self.assertFalse(service.preview()['meter_old']['matches'])

    def test_installation_with_real_meter_does_not_match(self):
        real = Meter.objects.create(code='REAL-1', status=self.status_active)
        self.sp.meter = real
        self.sp.save()
        order = Order.objects.create(token='INST-2', type=self.install_type, supply_point=self.sp)

        self.assertFalse(self._service(order, {'new': 'NEW-1'}).preview()['meter_old']['matches'])

    def test_apply_installation_replaces_fictitious_meter_without_close_reading(self):
        order = Order.objects.create(token='INST-3', type=self.install_type, supply_point=self.sp)

        self._service(order, {'new': 'NEW-1', 'r_new': '12'}).apply(self.user)

        self.sp.refresh_from_db()
        self.new_meter.refresh_from_db()
        self.fictitious.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.sp.meter, self.new_meter)
        self.assertEqual(self.new_meter.status, self.status_active)
        self.assertIsNotNone(self.new_meter.installation_at)
        self.assertEqual(self.fictitious.status, self.status_inactive)
        self.assertFalse(Reading.objects.filter(meter=self.fictitious).exists())
        initial = Reading.objects.get(meter=self.new_meter, contract=self.contract)
        self.assertEqual(initial.reading_value, 12)
        self.assertIsNotNone(order.change_meter_applied_at)

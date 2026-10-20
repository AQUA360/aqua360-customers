from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from billing.models import Invoice, InvoiceClass, InvoiceSerie, InvoiceStatus, InvoiceType, Reading
from billing.utils.invoice_service import generate_consumption_invoice_multiple
from contract.models import Contract, ContractPriceRate, ContractStatus
from coredata.models import ConfigProject, Person
from pricing.models import (
    BillingPeriod,
    BillingRange,
    LineItemType,
    PriceRate,
    Product,
    ProductOrigin,
    Tax,
    VariableCalculation,
)
from service.models import Company, Exploitation, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TestMeterChangeBillingRange(TestCase):
    """Canvi de comptador amb un canvi de tarifa (dos rangs de facturació) pel mig.

    Lectures: comptador antic (D-183), tancament del comptador antic i inicial del nou (D-111)
    i lectura actual (D, 42 m3 en 111 dies). El canvi de tarifa és a D-152.
    """

    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name="Test Company MC")
        exploitation = Exploitation.objects.create(
            name="Test Exploitation MC", company=company, token="expl-mc"
        )

        for token, value in [
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('supply_point_status_activate_token', 'SP_ACTIVE'),
            ('token_pre_invoice_serie', 'PRE'),
            ('invoice_type_budget_token', 'BUDGET'),
            ('reading_estimated', 'false'),
            ('origin_reading_token', 'aigua'),
            ('invoice_type_invoice_token', '1'),
            ('invoice_status_pending_token', '1'),
            ('invoice_class_token', 'OO'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
        ]:
            ConfigProject.objects.get_or_create(token=token, defaults={'value': value})
        InvoiceStatus.objects.get_or_create(token='PAID', defaults={'name': 'Pagada'})
        cls.issued_status, _ = InvoiceStatus.objects.get_or_create(token='ISSUED', defaults={'name': 'Emesa'})
        InvoiceStatus.objects.get_or_create(token='CANCELLED', defaults={'name': 'Cancel·lada'})
        ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        origin, _ = ProductOrigin.objects.get_or_create(token='aigua', defaults={'name': 'Aigua'})
        holder = Person.objects.create(name="Holder", surname="MC", token="holder-mc")

        contract_status, _ = ContractStatus.objects.get_or_create(
            token='ACTIVE', defaults={'name': 'Actiu'}
        )
        sp_status, _ = SupplyPointStatus.objects.get_or_create(
            token='SP_ACTIVE', defaults={'name': 'Actiu'}
        )
        meter_status, _ = MeterStatus.objects.get_or_create(token="1", defaults={'name': "Actiu"})

        InvoiceType.objects.get_or_create(token="1", defaults={'name': "Factura"})
        InvoiceStatus.objects.get_or_create(token="1", defaults={'name': "Pendent"})
        InvoiceClass.objects.get_or_create(token="OO", defaults={'name': "Ordinària"})
        InvoiceSerie.objects.get_or_create(
            token="PRE", defaults={'name': "Pre-factura", 'is_default': True}
        )
        InvoiceSerie.objects.filter(token="PRE").update(is_default=True)

        cls.old_meter = Meter.objects.create(code="METER-MC-OLD", status=meter_status)
        cls.new_meter = Meter.objects.create(code="METER-MC-NEW", status=meter_status)
        cls.supply_point = SupplyPoint.objects.create(
            name="Supply Point MC", token="SP-MC", meter=cls.new_meter, status=sp_status
        )
        cls.today = timezone.now().date()
        cls.contract = Contract.objects.create(
            company=company,
            token="CON-MC",
            total_persons=3,
            registration_date=cls.today - timedelta(days=400),
            status=contract_status,
            is_active=True,
            supply_point_default=cls.supply_point,
            holder=holder,
        )
        cls.contract.supply_points.add(cls.supply_point)

        product = Product.objects.create(
            name="Cànon", token="canon_mc", exploitation=exploitation, origin=origin
        )
        price_rate = PriceRate.objects.create(name="Tarifa Cànon", product=product, is_active=True)
        cls.contract.price_rates.add(
            ContractPriceRate.objects.create(price_rate=price_rate, supply_point=cls.supply_point)
        )
        change_date = cls.today - timedelta(days=152)
        cls.old_range = BillingRange.objects.create(
            price_rate=price_rate, start=cls.today - timedelta(days=400), end=change_date
        )
        cls.new_range = BillingRange.objects.create(price_rate=price_rate, start=change_date)
        quantity, _ = VariableCalculation.objects.get_or_create(
            token='consum', defaults={'name': 'Consum'}
        )
        billing_period = BillingPeriod.objects.create(token="trimestral", name="Trimestral", days=90)
        tax = Tax.objects.create(name="IVA 0%", percent=0.0)
        for billing_range in (cls.old_range, cls.new_range):
            LineItemType.objects.create(
                name="Part variable",
                billing_range=billing_range,
                billing_period=billing_period,
                tax=tax,
                quantity=quantity,
                proportional_price=0.5,
                is_positive=True,
                is_prorated=True,
                is_active=True,
            )

    def setUp(self):
        # El servei de factures guarda algunes configuracions en memòria entre proves.
        import billing.utils.invoice_service as invoice_service_mod
        for name in ('_active_supply_point_status', 'origin_reading', 'invoice_type_invoice',
                     'invoice_pending_status', 'invoice_cancelled_status', 'invoice_class',
                     'default_serie'):
            setattr(invoice_service_mod, name, None)
        try:
            del invoice_service_mod._reading_estimated_cached
        except AttributeError:
            pass
        patcher = patch('billing.utils.invoice_service.confirm_invoice', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

        old_reading = Reading.objects.create(
            supply_point=self.supply_point, meter=self.old_meter, contract=self.contract,
            reading_date=self.today - timedelta(days=183), reading_value=100, calculated_value=0,
        )
        close_reading = Reading.objects.create(
            supply_point=self.supply_point, meter=self.old_meter, contract=self.contract,
            reading_date=self.today - timedelta(days=111), reading_value=103, calculated_value=3,
            real_consumption=3, previous_reading=old_reading, is_close=True,
        )
        self.new_meter_reading = Reading.objects.create(
            supply_point=self.supply_point, meter=self.new_meter, contract=self.contract,
            reading_date=self.today - timedelta(days=111), reading_value=0, calculated_value=0,
            real_consumption=0, previous_reading=close_reading, consumption_days=72,
        )
        self.reading = Reading.objects.create(
            supply_point=self.supply_point, meter=self.new_meter, contract=self.contract,
            reading_date=self.today, reading_value=42, calculated_value=42, real_consumption=42,
            previous_reading=self.new_meter_reading, consumption_days=111,
        )

    def _generate(self):
        return generate_consumption_invoice_multiple(
            contract=self.contract,
            readings=[self.reading],
            title='Canvi de comptador',
            period_months=3,
        )

    def test_already_billed_meter_change_does_not_rebill_previous_range(self):
        # La lectura del canvi de comptador ja es va facturar: el període comença en ella
        # i queda tot dins del rang nou.
        billed = Invoice.objects.create(contract=self.contract, status=self.issued_status)
        billed.readings.add(self.new_meter_reading)

        invoice = self._generate()

        self.assertIsNotNone(invoice)
        line_items = invoice.line_items.filter(is_active=True)
        self.assertEqual(
            list(line_items.values_list('line_item_type__billing_range', flat=True)),
            [self.new_range.id],
        )
        self.assertEqual(sum(item.units for item in line_items), 42.0)

    def test_unbilled_meter_change_starts_at_old_meter_reading(self):
        # Sense facturar el canvi de comptador, el període comença a l'última lectura del
        # comptador antic i travessa el canvi de tarifa.
        invoice = self._generate()

        self.assertIsNotNone(invoice)
        self.assertEqual(
            set(invoice.line_items.filter(is_active=True)
                .values_list('line_item_type__billing_range', flat=True)),
            {self.old_range.id, self.new_range.id},
        )

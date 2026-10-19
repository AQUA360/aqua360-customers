from django.test import TestCase
from django.utils import timezone

from unittest.mock import patch

from billing.models import (
    Billing,
    Biller,
    InvoiceClass,
    InvoiceSerie,
    InvoiceStatus,
    InvoiceType,
    Reading,
    ReadingBatch,
)
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


class TestGeneralMeterWithSubMeters(TestCase):
    """Comptador general amb un subcomptador: es factura el general menys el subcomptador.

    Fixa com factura avui aquest cas (cap altra prova no hi passava), també quan el comptador
    general té una lectura de tancament per un canvi de comptador. El muntatge segueix el de
    `test_general_meter_fanout.py`.
    """

    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name="Test Company SM")
        exploitation = Exploitation.objects.create(
            name="Test Exploitation SM", company=company, token="expl-sm"
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
        InvoiceStatus.objects.get_or_create(token='CANCELLED', defaults={'name': 'Cancel·lada'})
        ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        origin, _ = ProductOrigin.objects.get_or_create(token='aigua', defaults={'name': 'Aigua'})
        holder = Person.objects.create(name="Holder", surname="SM", token="holder-sm")
        contract_status, _ = ContractStatus.objects.get_or_create(
            token='ACTIVE', defaults={'name': 'Actiu'}
        )
        sp_status, _ = SupplyPointStatus.objects.get_or_create(
            token='SP_ACTIVE', defaults={'name': 'Actiu'}
        )
        meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        InvoiceType.objects.get_or_create(token="1", defaults={'name': "Factura"})
        InvoiceStatus.objects.get_or_create(token="1", defaults={'name': "Pendent"})
        InvoiceClass.objects.get_or_create(token="OO", defaults={'name': "Ordinària"})
        InvoiceSerie.objects.get_or_create(
            token="PRE", defaults={'name': "Pre-factura", 'is_default': True}
        )
        InvoiceSerie.objects.filter(token="PRE").update(is_default=True)

        cls.general = Meter.objects.create(code="GEN-SM", status=meter_status, is_general=True)
        cls.sub = Meter.objects.create(code="SUB-SM", status=meter_status, meter_general=cls.general)

        product = Product.objects.create(
            name="Aigua", token="water_sm", exploitation=exploitation, origin=origin
        )
        price_rate = PriceRate.objects.create(name="Tarifa Aigua", product=product, is_active=True)

        cls.supply_points, cls.contracts = {}, {}
        for key, meter in (('general', cls.general), ('sub', cls.sub)):
            sp = SupplyPoint.objects.create(
                name=f"SP {key}", token=f"SP-SM-{key}", meter=meter, status=sp_status
            )
            contract = Contract.objects.create(
                company=company,
                token=f"CON-SM-{key}",
                total_persons=3,
                registration_date=timezone.now().date() - timezone.timedelta(days=400),
                status=contract_status,
                is_active=True,
                supply_point_default=sp,
                holder=holder,
            )
            contract.supply_points.add(sp)
            contract.price_rates.add(
                ContractPriceRate.objects.create(price_rate=price_rate, supply_point=sp)
            )
            cls.supply_points[key], cls.contracts[key] = sp, contract

        billing_range = BillingRange.objects.create(
            price_rate=price_rate, start=timezone.now().date() - timezone.timedelta(days=400)
        )
        quantity, _ = VariableCalculation.objects.get_or_create(
            token='consum', defaults={'name': 'Consum'}
        )
        LineItemType.objects.create(
            name="Consum Aigua",
            billing_range=billing_range,
            billing_period=BillingPeriod.objects.create(
                token="trimestral", name="Trimestral", days=90
            ),
            tax=Tax.objects.create(name="IVA 10%", percent=10.0),
            quantity=quantity,
            proportional_price=1.5,
            is_positive=True,
            is_active=True,
        )
        biller = Biller.objects.create(token="biller-sm", name="Biller SM", period_type="trimestral")
        cls.billing = Billing.objects.create(token="billing-sm", name="Billing SM", biller=biller)
        cls.batch = ReadingBatch.objects.create(token="batch-sm", name="Batch SM")

    def setUp(self):
        # El servei de factures guarda algunes configuracions en memòria entre proves.
        import billing.utils.invoice_service as invoice_service_mod
        for name in ('_active_supply_point_status', 'origin_reading', 'invoice_type_invoice',
                     'invoice_pending_status', 'invoice_class', 'default_serie'):
            setattr(invoice_service_mod, name, None)
        try:
            del invoice_service_mod._reading_estimated_cached
        except AttributeError:
            pass
        patcher = patch('billing.utils.invoice_service.confirm_invoice', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.today = timezone.now().date()

    def reading(self, key, value, calculated, days_ago=0, previous=None, **extra):
        defaults = {
            'meter': self.general if key == 'general' else self.sub,
            'supply_point': self.supply_points[key],
            'contract': self.contracts[key],
            'reading_value': value,
            'reading_date': self.today - timezone.timedelta(days=days_ago),
            'calculated_value': calculated,
            'real_consumption': calculated,
            'previous_reading': previous,
        }
        defaults.update(extra)
        return Reading.objects.create(**defaults)

    def sub_meter_reading(self, consumption=100):
        """Lectura del subcomptador al mateix lot i facturació que la del general."""
        previous = self.reading('sub', 500, 0, days_ago=90)
        return self.reading(
            'sub', 500 + consumption, consumption, previous=previous, consumption_days=90,
            batch=self.batch, billing=self.billing,
        )

    def invoice_for(self, general_reading):
        return generate_consumption_invoice_multiple(
            contract=self.contracts['general'],
            readings=[general_reading],
            title="Factura comptador general",
            billing=self.billing,
            period_months=3,
        )

    def billed_units(self, invoice):
        return sorted(float(item.units) for item in invoice.line_items.filter(is_active=True))

    def test_general_minus_sub_meter(self):
        # General: 300 m3. Subcomptador: 100 m3. Es factura 200.
        self.sub_meter_reading(100)
        previous = self.reading('general', 1000, 0, days_ago=90)
        general = self.reading(
            'general', 1300, 300, previous=previous, consumption_days=90,
            batch=self.batch, billing=self.billing,
        )
        invoice = self.invoice_for(general)
        self.assertIsNotNone(invoice)
        self.assertEqual(self.billed_units(invoice), [200.0])
        self.assertEqual(float(invoice.consumption), 200.0)

    def test_general_meter_change_counts_the_close_reading_once(self):
        # Canvi del comptador general: 50 m3 a la lectura de tancament (sense facturar) i 250 m3
        # després. Subcomptador: 100 m3. Es factura 50 + 250 - 100 = 200.
        self.sub_meter_reading(100)
        start = self.reading('general', 1000, 0, days_ago=120)
        close = self.reading('general', 1050, 50, days_ago=90, previous=start, is_close=True)
        general = self.reading(
            'general', 250, 250, previous=close, consumption_days=90,
            batch=self.batch, billing=self.billing,
        )
        invoice = self.invoice_for(general)
        self.assertIsNotNone(invoice)
        self.assertEqual(self.billed_units(invoice), [200.0])

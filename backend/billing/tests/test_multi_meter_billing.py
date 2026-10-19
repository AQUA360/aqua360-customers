from django.test import TestCase
from django.utils import timezone

from unittest.mock import patch

from billing.models import InvoiceClass, InvoiceSerie, InvoiceStatus, InvoiceType, Reading
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


class TestMultiMeterBilling(TestCase):
    """Un contracte amb dos punts de subministrament, cadascun amb el seu comptador.

    El muntatge segueix el de `test_general_meter_fanout.py`, amb els models d'ara: el punt de
    subministrament porta el comptador i l'estat, i el contracte, l'estat, el titular i el punt
    per defecte.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Company MM")
        cls.exploitation = Exploitation.objects.create(
            name="Test Exploitation MM", company=cls.company, token="expl-mm"
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
        holder = Person.objects.create(name="Holder", surname="MM", token="holder-mm")

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

        cls.meter1 = Meter.objects.create(code="METER-0001", status=meter_status)
        cls.meter2 = Meter.objects.create(code="METER-0002", status=meter_status)
        cls.supply_point1 = SupplyPoint.objects.create(
            name="Supply Point 1", token="SP-0001", meter=cls.meter1, status=sp_status
        )
        cls.supply_point2 = SupplyPoint.objects.create(
            name="Supply Point 2", token="SP-0002", meter=cls.meter2, status=sp_status
        )
        cls.contract = Contract.objects.create(
            company=cls.company,
            token="CON-0001",
            total_persons=3,
            registration_date=timezone.now().date() - timezone.timedelta(days=400),
            status=contract_status,
            is_active=True,
            supply_point_default=cls.supply_point1,
            holder=holder,
        )
        cls.contract.supply_points.add(cls.supply_point1, cls.supply_point2)

        product = Product.objects.create(
            name="Aigua", token="water_mm", exploitation=cls.exploitation, origin=origin
        )
        price_rate = PriceRate.objects.create(name="Tarifa Aigua", product=product, is_active=True)
        for sp in (cls.supply_point1, cls.supply_point2):
            cls.contract.price_rates.add(
                ContractPriceRate.objects.create(price_rate=price_rate, supply_point=sp)
            )
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
            proportional_price=1.5,  # 1.5 € per m3
            is_positive=True,
            is_active=True,
        )

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

    def test_combined_consumption_calculation_multiple_meters(self):
        # Create readings for both meters
        reading_date = timezone.now().date()
        prev_reading_date = reading_date - timezone.timedelta(days=90)

        # Reading 1: 10 m3 consumption (from 100 to 110)
        prev_reading1 = Reading.objects.create(
            supply_point=self.supply_point1,
            meter=self.meter1,
            reading_value=100,
            reading_date=prev_reading_date,
            calculated_value=0,
            contract=self.contract
        )
        reading1 = Reading.objects.create(
            supply_point=self.supply_point1,
            meter=self.meter1,
            reading_value=110,
            reading_date=reading_date,
            calculated_value=10,
            previous_reading=prev_reading1,
            contract=self.contract,
            consumption_days=90
        )

        # Reading 2: 15 m3 consumption (from 200 to 215)
        prev_reading2 = Reading.objects.create(
            supply_point=self.supply_point2,
            meter=self.meter2,
            reading_value=200,
            reading_date=prev_reading_date,
            calculated_value=0,
            contract=self.contract
        )
        reading2 = Reading.objects.create(
            supply_point=self.supply_point2,
            meter=self.meter2,
            reading_value=215,
            reading_date=reading_date,
            calculated_value=15,
            previous_reading=prev_reading2,
            contract=self.contract,
            consumption_days=90
        )

        # Generate invoice
        readings_list = [reading1, reading2]
        invoice = generate_consumption_invoice_multiple(
            contract=self.contract,
            readings=readings_list,
            title="Factura Multi-comptador",
            period_months=3
        )

        self.assertIsNotNone(invoice)

        # Verify that separate line items were generated for each reading/meter.
        line_items = invoice.line_items.filter(is_active=True)
        self.assertEqual(line_items.count(), 2)
        
        # Verify the individual meter consumption values
        units = sorted([item.units for item in line_items])
        self.assertEqual(units, [10.0, 15.0])
        
        # Verify that both readings are linked to the invoice (so they display in the upper table)
        invoice_readings = invoice.readings.all()
        self.assertIn(reading1, invoice_readings)
        self.assertIn(reading2, invoice_readings)
        self.assertEqual(invoice_readings.count(), 2)

    def test_combined_consumption_with_control_reading_modification(self):
        # Create a control reading and a modified active reading to simulate UI editing of close reading
        reading_date = timezone.now().date()
        prev_reading_date = reading_date - timezone.timedelta(days=90)

        # Old meter close reading (modified/control)
        prev_reading1 = Reading.objects.create(
            supply_point=self.supply_point1,
            meter=self.meter1,
            reading_value=100,
            reading_date=prev_reading_date,
            calculated_value=0,
            real_consumption=0,
            contract=self.contract
        )
        # Original close reading: 4 m3, but marked as control (obsolete)
        reading_control = Reading.objects.create(
            supply_point=self.supply_point1,
            meter=self.meter1,
            reading_value=104,
            reading_date=reading_date,
            calculated_value=4,
            real_consumption=4,
            previous_reading=prev_reading1,
            contract=self.contract,
            consumption_days=90,
            is_control=True,
            is_close=True
        )
        # Active modified close reading: updated to 8 m3
        reading_modified = Reading.objects.create(
            supply_point=self.supply_point1,
            meter=self.meter1,
            reading_value=108,
            reading_date=reading_date,
            calculated_value=8,
            real_consumption=8,
            previous_reading=prev_reading1,
            contract=self.contract,
            consumption_days=90,
            is_control=False,
            is_close=True
        )
        # Establish the M2M modified readings link
        reading_control.modified_readings.add(reading_modified)

        # New meter readings: 10 m3
        # The initial reading of new meter links to the obsolete close reading (to simulate typical flow before modification)
        reading_new_init = Reading.objects.create(
            supply_point=self.supply_point2,
            meter=self.meter2,
            reading_value=0,
            reading_date=reading_date,
            calculated_value=0,
            real_consumption=0,
            previous_reading=reading_control,
            contract=self.contract,
            is_control=False
        )
        reading_new_act = Reading.objects.create(
            supply_point=self.supply_point2,
            meter=self.meter2,
            reading_value=10,
            reading_date=reading_date + timezone.timedelta(days=2),
            calculated_value=10,
            real_consumption=10,
            previous_reading=reading_new_init,
            contract=self.contract,
            consumption_days=2,
            is_control=False
        )

        # Generate invoice passing the original selected list of readings (which contains control/unresolved ones)
        readings_list = [reading_control, reading_new_act]
        invoice = generate_consumption_invoice_multiple(
            contract=self.contract,
            readings=readings_list,
            title="Factura Control Modificacio",
            period_months=3
        )

        self.assertIsNotNone(invoice)
        # The consumption must sum the active modified reading (8 m3) + the new active reading (10 m3) = 18 m3
        self.assertEqual(invoice.consumption, 18.0)
        
        line_items = invoice.line_items.filter(is_active=True)
        self.assertEqual(line_items.count(), 2)
        
        # Verify the individual resolved consumption values
        units = sorted([item.units for item in line_items])
        self.assertEqual(units, [8.0, 10.0])

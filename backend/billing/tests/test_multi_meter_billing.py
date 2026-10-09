from django.test import TestCase
from django.utils import timezone
from coredata.models import ConfigProject
from service.models import SupplyPoint, Meter, MeterStatus, Exploitation, Company
from contract.models import Contract, ContractPriceRate
from pricing.models import PriceRate, Product, BillingRange, LineItemType, Tax, BillingPeriod
from billing.models import Reading, Invoice, InvoiceSerie, InvoiceType, InvoiceStatus, InvoiceClass
from billing.utils.invoice_service import generate_consumption_invoice_multiple

class TestMultiMeterBilling(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create general setup objects
        cls.company = Company.objects.create(name="Test Company", token="test_company")
        cls.exploitation = Exploitation.objects.create(name="Test Exploitation", company=cls.company)
        
        # Setup config project variables if needed
        ConfigProject.objects.get_or_create(token='token_pre_invoice_serie', defaults={'value': 'PRE'})
        ConfigProject.objects.get_or_create(token='invoice_type_budget_token', defaults={'value': 'BUDGET'})
        
        # Create standard status/types for billing
        cls.invoice_type, _ = InvoiceType.objects.get_or_create(token="1", name="Factura")
        cls.invoice_status_pending, _ = InvoiceStatus.objects.get_or_create(token="1", name="Pendent")
        cls.invoice_class_oo, _ = InvoiceClass.objects.get_or_create(token="OO", name="Ordinària")
        cls.invoice_serie_pre, _ = InvoiceSerie.objects.get_or_create(token="PRE", name="Pre-factura")

        # Create meter status
        cls.meter_status_active, _ = MeterStatus.objects.get_or_create(token="1", name="Actiu")

        # Create Contract
        cls.contract = Contract.objects.create(
            company=cls.company,
            token="CON-0001",
            total_persons=3,
            registration_date=timezone.now().date()
        )

        # Create 2 Supply Points with active meters
        cls.supply_point1 = SupplyPoint.objects.create(
            name="Supply Point 1",
            token="SP-0001",
            exploitation=cls.exploitation
        )
        cls.meter1 = Meter.objects.create(
            code="METER-0001",
            status=cls.meter_status_active
        )
        cls.supply_point1.meter = cls.meter1
        cls.supply_point1.save()

        cls.supply_point2 = SupplyPoint.objects.create(
            name="Supply Point 2",
            token="SP-0002",
            exploitation=cls.exploitation
        )
        cls.meter2 = Meter.objects.create(
            code="METER-0002",
            status=cls.meter_status_active
        )
        cls.supply_point2.meter = cls.meter2
        cls.supply_point2.save()

        # Link supply points to contract
        cls.contract.supply_points.add(cls.supply_point1, cls.supply_point2)

        # Create common Product and Price Rate
        cls.product = Product.objects.create(name="Aigua", token="water", exploitation=cls.exploitation)
        cls.price_rate = PriceRate.objects.create(name="Tarifa Aigua", product=cls.product, is_active=True)
        
        # Link Price Rate to Contract for both supply points
        ContractPriceRate.objects.create(contract=cls.contract, price_rate=cls.price_rate, supply_point=cls.supply_point1)
        ContractPriceRate.objects.create(contract=cls.contract, price_rate=cls.price_rate, supply_point=cls.supply_point2)

        # Create Billing Range & Line Item Type
        cls.billing_range = BillingRange.objects.create(
            price_rate=cls.price_rate,
            start=timezone.now().date() - timezone.timedelta(days=100)
        )
        cls.tax = Tax.objects.create(name="IVA 10%", percent=10.0)
        cls.billing_period = BillingPeriod.objects.create(token="trimestral", name="Trimestral", days=90)
        cls.line_item_type = LineItemType.objects.create(
            name="Consum Aigua",
            billing_range=cls.billing_range,
            billing_period=cls.billing_period,
            tax=cls.tax,
            proportional_price=1.5,  # 1.5€ per m3
            is_positive=True,
            is_active=True
        )

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
            contract=self.contract
        )
        # Original close reading: 4 m3, but marked as control (obsolete)
        reading_control = Reading.objects.create(
            supply_point=self.supply_point1,
            meter=self.meter1,
            reading_value=104,
            reading_date=reading_date,
            calculated_value=4,
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

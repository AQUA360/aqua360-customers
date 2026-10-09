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
from billing.utils.invoice_service import (
    generate_consumption_invoice_multiple,
    recalc_consumption_gen_meter,
)
from billing.utils.reading_service import fanout_general_meter_readings
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


class TestGeneralMeterFanout(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Company GM")
        cls.exploitation = Exploitation.objects.create(
            name="Test Exploitation GM", company=cls.company, token="expl-gm"
        )

        ConfigProject.objects.get_or_create(
            token='contract_active_token', defaults={'value': 'ACTIVE'}
        )
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': 'TERMINATED'}
        )
        ConfigProject.objects.get_or_create(
            token='supply_point_status_activate_token', defaults={'value': 'SP_ACTIVE'}
        )
        ConfigProject.objects.get_or_create(
            token='token_pre_invoice_serie', defaults={'value': 'PRE'}
        )
        ConfigProject.objects.get_or_create(
            token='invoice_type_budget_token', defaults={'value': 'BUDGET'}
        )
        ConfigProject.objects.get_or_create(
            token='reading_estimated', defaults={'value': 'false'}
        )
        ConfigProject.objects.get_or_create(
            token='origin_reading_token', defaults={'value': 'aigua'}
        )
        ConfigProject.objects.get_or_create(
            token='invoice_type_invoice_token', defaults={'value': '1'}
        )
        ConfigProject.objects.get_or_create(
            token='invoice_status_pending_token', defaults={'value': '1'}
        )
        ConfigProject.objects.get_or_create(
            token='invoice_class_token', defaults={'value': 'OO'}
        )
        ConfigProject.objects.get_or_create(
            token='invoice_status_paid_token', defaults={'value': 'PAID'}
        )
        ConfigProject.objects.get_or_create(
            token='invoice_status_cancelled_token', defaults={'value': 'CANCELLED'}
        )
        InvoiceStatus.objects.get_or_create(token='PAID', defaults={'name': 'Pagada'})
        InvoiceStatus.objects.get_or_create(token='CANCELLED', defaults={'name': 'Cancel·lada'})
        ContractStatus.objects.get_or_create(token='TERMINATED', defaults={'name': 'Baixa'})
        ProductOrigin.objects.get_or_create(token='aigua', defaults={'name': 'Aigua'})
        cls.holder = Person.objects.create(name="Holder", surname="GM", token="holder-gm")

        cls.contract_status_active, _ = ContractStatus.objects.get_or_create(
            token='ACTIVE', defaults={'name': 'Actiu'}
        )
        cls.sp_status_active, _ = SupplyPointStatus.objects.get_or_create(
            token='SP_ACTIVE', defaults={'name': 'Actiu'}
        )
        cls.meter_status_active, _ = MeterStatus.objects.get_or_create(
            token='1', defaults={'name': 'Actiu'}
        )

        InvoiceType.objects.get_or_create(token="1", defaults={'name': "Factura"})
        InvoiceStatus.objects.get_or_create(token="1", defaults={'name': "Pendent"})
        InvoiceClass.objects.get_or_create(token="OO", defaults={'name': "Ordinària"})
        InvoiceSerie.objects.get_or_create(
            token="PRE", defaults={'name': "Pre-factura", 'is_default': True}
        )
        InvoiceSerie.objects.filter(token="PRE").update(is_default=True)

        cls.meter = Meter.objects.create(
            code="GEN-METER-001",
            status=cls.meter_status_active,
            is_general=True,
        )

        cls.supply_points = []
        cls.contracts = []
        for i in range(1, 4):
            sp = SupplyPoint.objects.create(
                name=f"SP General {i}",
                token=f"SP-GEN-{i}",
                meter=cls.meter,
                status=cls.sp_status_active,
            )
            contract = Contract.objects.create(
                company=cls.company,
                token=f"CON-GEN-{i}",
                total_persons=3,
                registration_date=timezone.now().date() - timezone.timedelta(days=400),
                status=cls.contract_status_active,
                is_active=True,
                supply_point_default=sp,
                holder=cls.holder,
            )
            contract.supply_points.add(sp)
            cls.supply_points.append(sp)
            cls.contracts.append(contract)

        origin = ProductOrigin.objects.get(token='aigua')
        cls.product = Product.objects.create(
            name="Aigua",
            token="water_gm",
            exploitation=cls.exploitation,
            origin=origin,
        )
        cls.price_rate = PriceRate.objects.create(
            name="Tarifa Aigua", product=cls.product, is_active=True
        )
        for contract, sp in zip(cls.contracts, cls.supply_points):
            cpr = ContractPriceRate.objects.create(
                price_rate=cls.price_rate, supply_point=sp
            )
            contract.price_rates.add(cpr)

        cls.billing_range = BillingRange.objects.create(
            price_rate=cls.price_rate,
            start=timezone.now().date() - timezone.timedelta(days=400),
        )
        cls.tax = Tax.objects.create(name="IVA 10%", percent=10.0)
        cls.billing_period = BillingPeriod.objects.create(
            token="trimestral", name="Trimestral", days=90
        )
        quantity, _ = VariableCalculation.objects.get_or_create(
            token='consum', defaults={'name': 'Consum'}
        )
        LineItemType.objects.create(
            name="Consum Aigua",
            billing_range=cls.billing_range,
            billing_period=cls.billing_period,
            tax=cls.tax,
            quantity=quantity,
            proportional_price=1.5,
            is_positive=True,
            is_active=True,
        )

        cls.biller = Biller.objects.create(
            token="biller-gm", name="Biller GM", period_type="trimestral"
        )
        cls.billing = Billing.objects.create(
            token="billing-gm", name="Billing GM", biller=cls.biller
        )
        cls.reading_batch = ReadingBatch.objects.create(
            token="batch-gm", name="Batch GM"
        )

    def _create_canonical_reading(self, calculated_value=300):
        reading_date = timezone.now().date()
        prev_date = reading_date - timezone.timedelta(days=90)
        prev = Reading.objects.create(
            meter=self.meter,
            reading_value=1000,
            reading_date=prev_date,
            calculated_value=0,
            batch=self.reading_batch,
            billing=self.billing,
        )
        canonical = Reading.objects.create(
            meter=self.meter,
            reading_value=1000 + calculated_value,
            reading_date=reading_date,
            calculated_value=calculated_value,
            previous_reading=prev,
            consumption_days=90,
            batch=self.reading_batch,
            billing=self.billing,
            contract=None,
            supply_point=None,
        )
        return canonical

    def test_fanout_creates_one_copy_per_contract(self):
        canonical = self._create_canonical_reading(300)
        created = fanout_general_meter_readings(self.billing)

        self.assertEqual(len(created), 3)
        copies = Reading.objects.filter(copied_from=canonical)
        self.assertEqual(copies.count(), 3)

        contract_ids = set(copies.values_list('contract_id', flat=True))
        self.assertEqual(contract_ids, {c.id for c in self.contracts})

        for copy in copies:
            self.assertEqual(copy.calculated_value, 300)
            self.assertEqual(copy.meter_id, self.meter.id)
            self.assertEqual(copy.billing_id, self.billing.id)
            self.assertIsNotNone(copy.supply_point_id)
            self.assertEqual(copy.supply_point.meter_id, self.meter.id)

    def test_fanout_skips_block_billing_contracts(self):
        """Non-billable contracts (block_billing=True) are excluded from fan-out and divisor."""
        blocked = self.contracts[0]
        blocked.block_billing = True
        blocked.save(update_fields=['block_billing'])

        import billing.utils.invoice_service as invoice_service_mod
        invoice_service_mod._active_supply_point_status = None

        canonical = self._create_canonical_reading(300)
        created = fanout_general_meter_readings(self.billing)

        self.assertEqual(len(created), 2)
        contract_ids = set(c.contract_id for c in created)
        self.assertNotIn(blocked.id, contract_ids)
        self.assertEqual(contract_ids, {self.contracts[1].id, self.contracts[2].id})

        for copy in created:
            divided, _ = recalc_consumption_gen_meter(
                copy, float(copy.calculated_value), copy.supply_point
            )
            # 300 / 2 billable targets (not / 3 SPs)
            self.assertEqual(divided, 150.0)

    def test_fanout_is_idempotent(self):
        canonical = self._create_canonical_reading(300)
        first = fanout_general_meter_readings(self.billing)
        second = fanout_general_meter_readings(self.billing)

        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 0)
        self.assertEqual(Reading.objects.filter(copied_from=canonical).count(), 3)

    def test_batch_counters_ignore_copies(self):
        canonical = self._create_canonical_reading(300)
        fanout_general_meter_readings(self.billing)

        total_physical = self.reading_batch.readings.filter(copied_from__isnull=True).count()
        total_all = self.reading_batch.readings.count()

        # previous + canonical are physical; copies share the same batch
        self.assertEqual(total_physical, 2)
        self.assertEqual(total_all, 2 + 3)
        self.assertTrue(
            self.reading_batch.readings.filter(copied_from__isnull=True, id=canonical.id).exists()
        )

    def test_divided_consumption_and_invoices(self):
        # Reset cached lookups used by invoice_service
        import billing.utils.invoice_service as invoice_service_mod
        invoice_service_mod._active_supply_point_status = None
        invoice_service_mod.origin_reading = None
        invoice_service_mod.invoice_type_invoice = None
        invoice_service_mod.invoice_pending_status = None
        invoice_service_mod.invoice_class = None
        invoice_service_mod.default_serie = None
        try:
            del invoice_service_mod._reading_estimated_cached
        except AttributeError:
            pass

        canonical = self._create_canonical_reading(300)
        created = fanout_general_meter_readings(self.billing)
        self.assertEqual(len(created), 3)

        invoices = []
        with patch('billing.utils.invoice_service.confirm_invoice', return_value=None):
            for copy in created:
                divided, _ = recalc_consumption_gen_meter(
                    copy, float(copy.calculated_value), copy.supply_point
                )
                self.assertEqual(divided, 100.0)

                invoice = generate_consumption_invoice_multiple(
                    contract=copy.contract,
                    readings=[copy],
                    title="Factura comptador general",
                    billing=self.billing,
                    period_months=3,
                )
                self.assertIsNotNone(invoice)
                invoices.append(invoice)
                self.assertEqual(float(invoice.consumption), 100.0)

        self.assertEqual(len(invoices), 3)
        self.assertEqual(
            Reading.objects.filter(
                billing=self.billing,
                meter=self.meter,
                copied_from__isnull=True,
                contract__isnull=True,
                id=canonical.id,
            ).count(),
            1,
        )

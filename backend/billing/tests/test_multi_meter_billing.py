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

    def test_close_reading_consumption_is_added_once_per_meter(self):
        reading_date = timezone.now().date()
        for close_depth in (1, 2):
            with self.subTest(close_depth=close_depth):
                close = Reading.objects.create(
                    supply_point=self.supply_point1,
                    meter=self.meter1,
                    contract=self.contract,
                    reading_date=reading_date - timezone.timedelta(days=2),
                    reading_value=4,
                    calculated_value=4,
                    real_consumption=4,
                    is_close=True,
                )
                previous = close
                if close_depth == 2:
                    previous = Reading.objects.create(
                        supply_point=self.supply_point1,
                        meter=self.meter1,
                        contract=self.contract,
                        reading_date=reading_date - timezone.timedelta(days=1),
                        reading_value=0,
                        calculated_value=0,
                        previous_reading=close,
                    )
                reading = Reading.objects.create(
                    supply_point=self.supply_point1,
                    meter=self.meter1,
                    contract=self.contract,
                    reading_date=reading_date,
                    reading_value=previous.reading_value + 10,
                    calculated_value=10,
                    previous_reading=previous,
                    consumption_days=90,
                )
                invoice = generate_consumption_invoice_multiple(
                    contract=self.contract,
                    readings=[reading],
                    title='Close reading consumption',
                    period_months=3,
                )

                self.assertIsNotNone(invoice)
                self.assertEqual(invoice.consumption, 14.0)
                self.assertEqual(invoice.line_items.get(is_active=True).units, 14.0)

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

        # La facturació passa les lectures que no són de control (filtra is_control=False): la
        # modificada, no la de control que substitueix.
        readings_list = [reading_modified, reading_new_act]
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

    def _create_persons_invoice(self):
        """Create an invoice whose occupants and rate can later differ from the contract."""
        quantity, _ = VariableCalculation.objects.get_or_create(token='total_persons')
        LineItemType.objects.update(quantity=quantity)
        self.contract.total_persons = 4
        self.contract.save(update_fields=['total_persons'])
        previous = Reading.objects.create(
            contract=self.contract, meter=self.meter1, supply_point=self.supply_point1,
            reading_date=timezone.now().date() - timezone.timedelta(days=90),
            reading_value=100, calculated_value=0,
        )
        reading = Reading.objects.create(
            contract=self.contract, meter=self.meter1, supply_point=self.supply_point1,
            reading_date=timezone.now().date(), previous_reading=previous,
            reading_value=110, calculated_value=10, consumption_days=90,
        )
        invoice = generate_consumption_invoice_multiple(
            self.contract, [reading], 'Historical occupants', period_months=3,
        )
        self.assertIsNotNone(invoice)
        return invoice, reading

    def test_generation_persists_configured_persons_fallback(self):
        _, reading = self._create_persons_invoice()
        ConfigProject.objects.update_or_create(
            token='contract_min_persons', defaults={'value': '5'},
        )
        for persons, expected in ((0, 5), (-1, 5), (2, 2)):
            with self.subTest(persons=persons):
                self.contract.total_persons = persons
                invoice = generate_consumption_invoice_multiple(
                    self.contract, [reading], 'Occupants fallback', period_months=3,
                )
                self.assertIsNotNone(invoice)
                self.assertEqual(invoice.persons_final, expected)
                self.assertEqual(invoice.line_items.get().units, expected)

    def test_recalculation_rejects_multiple_contracts_before_deleting_invoice(self):
        from billing.models import Invoice
        from billing.utils.recalculate_invoice_service import delete_and_recalculate_invoice

        invoice, reading = self._create_persons_invoice()
        other_contract = Contract.objects.create(token='OTHER-CONTRACT')
        other_reading = Reading.objects.create(contract=other_contract)
        invoice.readings.add(other_reading)
        original_line_ids = list(invoice.line_items.values_list('pk', flat=True))

        with patch.object(Invoice, 'delete') as delete_invoice, patch(
            'billing.utils.recalculate_invoice_service.generate_consumption_invoice_multiple'
        ) as generate_invoice:
            with self.assertRaisesMessage(ValueError, 'multiple contracts'):
                delete_and_recalculate_invoice(invoice.pk)

        delete_invoice.assert_not_called()
        generate_invoice.assert_not_called()
        self.assertTrue(Invoice.objects.filter(pk=invoice.pk).exists())
        self.assertCountEqual(invoice.readings.all(), [reading, other_reading])
        self.assertEqual(list(invoice.line_items.values_list('pk', flat=True)), original_line_ids)

    def test_recalculation_preserves_persons_and_removed_historical_rate(self):
        from billing.models import Invoice
        from billing.utils.recalculate_invoice_service import (
            delete_and_recalculate_invoice, recalculate_invoice_smart,
        )

        for recalculate in (delete_and_recalculate_invoice, recalculate_invoice_smart):
            with self.subTest(recalculate=recalculate.__name__):
                original, reading = self._create_persons_invoice()
                original_id = original.pk
                historical_rate = original.line_items.get().price_rate
                self.contract.total_persons = 2
                self.contract.save(update_fields=['total_persons'])
                historical_links = list(self.contract.price_rates.all())
                self.contract.price_rates.clear()
                historical_rate.is_active = False
                historical_rate.save(update_fields=['is_active'])
                current_rate = PriceRate.objects.create(
                    name='Current rate', product=historical_rate.product,
                )
                current_link = ContractPriceRate.objects.create(
                    price_rate=current_rate, supply_point=self.supply_point1,
                )
                self.contract.price_rates.add(current_link)

                with patch('billing.utils.recalculate_invoice_service._get_invoice_warning', return_value=None):
                    regenerated = recalculate(original_id)

                self.assertFalse(Invoice.objects.filter(pk=original_id).exists())
                self.assertEqual(regenerated.persons_final, 4)
                line = regenerated.line_items.get()
                self.assertEqual(line.price_rate_id, historical_rate.pk)
                self.assertEqual(line.units, 4)
                self.assertEqual(list(regenerated.readings.all()), [reading])
                self.contract.price_rates.clear()
                self.contract.price_rates.add(*historical_links)
                historical_rate.is_active = True
                historical_rate.save(update_fields=['is_active'])

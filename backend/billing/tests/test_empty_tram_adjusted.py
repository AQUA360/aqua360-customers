from django.test import TestCase

from billing.utils.invoice_line_item_service import create_from_lineitemtype
from contract.models import Contract
from coredata.models import ConfigProject
from coredata.utils.invoice_tram_config import SHOW_ALL_CONSUMPTION_TRAMS_TOKEN
from pricing.models import (
    Adjustment, AdjustmentIntervalStretch, AdjustmentOperation, BillingRange, LineItemType,
    PriceInterval, PriceIntervalStretch,
)
from service.models import ConnectionDiameter


class TestEmptyTramAdjusted(TestCase):
    """Els trams sense consum es mostren amb el límit i el preu corregits (ampliació, percentatge), no els de la tarifa."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': 'terminated'},
        )
        ConfigProject.objects.update_or_create(
            token=SHOW_ALL_CONSUMPTION_TRAMS_TOKEN, defaults={'value': 'true'},
        )
        ConnectionDiameter.objects.create(name='63', is_default=True)
        cls.contract = Contract.objects.create(total_persons=5)

        interval = PriceInterval.objects.create(token='TRAMS', units='m3')
        base = ((1, '1R TRAM', 27, 1.0), (2, '2N TRAM', 45, 2.0), (3, '3R TRAM', 54, 3.0), (4, '4T TRAM', 999999, 4.0))
        stretches = {
            num: PriceIntervalStretch.objects.create(
                price_interval=interval, stretch=num, name_stretch=name, end_stretch=end, proportional_price=price,
            )
            for num, name, end, price in base
        }
        cls.line_item_type = LineItemType.objects.create(
            name='PART VARIABLE', billing_range=BillingRange.objects.create(), price_interval=interval,
        )

        extension = Adjustment.objects.create(
            name='AMPLIACIÓ', position=1, line_item_type=cls.line_item_type,
            operation=AdjustmentOperation.objects.create(token='ext', name='Ampliació'),
        )
        for num, formula in ((1, '45'), (2, '75'), (3, '90')):
            AdjustmentIntervalStretch.objects.create(
                adjustment=extension, price_interval_stretch=stretches[num], formula=formula,
            )
        discount = Adjustment.objects.create(
            name='DESCOMPTE', position=2, line_item_type=cls.line_item_type,
            operation=AdjustmentOperation.objects.create(token='ptg', name='Percentatge'),
        )
        for stretch in stretches.values():
            AdjustmentIntervalStretch.objects.create(
                adjustment=discount, price_interval_stretch=stretch, formula='0.5',
            )

    def test_empty_trams_use_adjusted_limit_and_price(self):
        # Sense lectura es factura 1 unitat: cau al 1r tram i la resta queden buits
        lines = create_from_lineitemtype(self.contract, self.line_item_type, None, 0, 0)
        by_stretch = {line['interval']: line for line in lines}

        self.assertEqual(by_stretch[1]['units'], 1)
        for stretch, end, price in ((2, 75, 1.0), (3, 90, 1.5), (4, 999999, 2.0)):
            with self.subTest(stretch=stretch):
                line = by_stretch[stretch]
                self.assertEqual(line['units'], 0)
                self.assertEqual(line['end_stretch'], end)
                self.assertEqual(line['price_unit'], price)
                self.assertFalse(line['adjustments'])
        self.assertIn('Límit: 75', by_stretch[2]['name'])
        self.assertIn('Límit: 90', by_stretch[3]['name'])
        self.assertNotIn('Límit', by_stretch[4]['name'])

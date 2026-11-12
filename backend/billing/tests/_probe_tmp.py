from types import SimpleNamespace
from billing.tests.test_empty_tram_adjusted import TestEmptyTramAdjusted
from billing.utils.invoice_line_item_service import create_from_lineitemtype

class Probe(TestEmptyTramAdjusted):
    def test_probe(self):
        r = SimpleNamespace(supply_point=None, calculated_value=60, previous_reading=None, batch=None, id=None)
        for l in create_from_lineitemtype(self.contract, self.line_item_type, r, 60, 0):
            print(l['interval'], l['units'], l['end_stretch'], l['price_unit'], [(a.get('name'), a.get('total_applied')) for a in (l['adjustments'] or [])])

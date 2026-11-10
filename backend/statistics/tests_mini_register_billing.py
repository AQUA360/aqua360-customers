from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from billing.models import Billing, Invoice, InvoiceLineItem, InvoiceStatus
from contract.models import Contract, ContractUseType
from coredata.models import ConfigProject
from pricing.models import LineItemType, PriceVariableInterval, VariableCalculation
from service.models import Exploitation
from statistics.utils import report_service


class MiniRegisterBillingSummaryTests(TestCase):
    """Padró de facturació reduït: els m3 i els imports de les files han de quadrar amb les factures."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.update_or_create(token='invoice_status_payoff_token', defaults={'value': 'PAYOFF'})
        cls.payoff = InvoiceStatus.objects.create(token='PAYOFF', name='Abonament')
        cls.exploitation = Exploitation.objects.create(name='EXP')
        use_type = ContractUseType.objects.create(token='DOM', name='DOMESTIC')
        other_use_type = ContractUseType.objects.create(token='IND', name='INDUSTRIAL')
        cls.contract, cls.other_contract = Contract.objects.bulk_create([
            Contract(token='MR-1', use_type=use_type, is_active=True),
            Contract(token='MR-2', use_type=other_use_type, is_active=True),
        ])
        cls.billing = Billing.objects.create(name='Lot')

        consum = VariableCalculation.objects.create(token='consum', name='Consum')
        calibre = PriceVariableInterval.objects.create(token='CALIBRE', units='dm_met')
        cls.lt_consum = LineItemType.objects.create(name='CONSUM', quantity=consum)
        cls.lt_fixa = LineItemType.objects.create(name='QUOTA FIXA DE SERVEI', price_variable=calibre)
        cls.lt_aca_specific = LineItemType.objects.create(name="CANON D'ÚS ESPECÍFIC", quantity=consum)
        cls.lt_aca_general = LineItemType.objects.create(name="CANON D'ÚS GENERAL", quantity=consum)
        cls.lt_aca_fixed = LineItemType.objects.create(name='PART FIXA', price=3)

        invoice, refund = Invoice.objects.bulk_create([
            Invoice(contract=cls.contract, exploitation=cls.exploitation, billing=cls.billing,
                    consumption=50, subtotal_final=Decimal('70'), total_final=Decimal('77')),
            # Abonament: consum en positiu i línies en negatiu
            Invoice(contract=cls.contract, exploitation=cls.exploitation, billing=cls.billing, status=cls.payoff,
                    consumption=10, subtotal_final=Decimal('-12'), total_final=Decimal('-13.2')),
        ])

        def line(inv, lt, product, interval, units, price, contract=cls.contract):
            return InvoiceLineItem(
                invoice=inv, contract=contract, line_item_type=lt, product_name=product, interval=interval,
                units=units, price=price, total=Decimal(str(price)),
            )

        InvoiceLineItem.objects.bulk_create([
            line(invoice, cls.lt_consum, 'AIGUA', 1, 30, 15),
            line(invoice, cls.lt_consum, 'AIGUA', 2, 20, 20),
            # Quota fixa de calibre 6: l'interval és el calibre, no un tram
            line(invoice, cls.lt_fixa, 'AIGUA', 6, 1, 20),
            line(invoice, cls.lt_aca_specific, 'CANON AIGUA (ACA)', 0, 50, 10),
            line(invoice, cls.lt_aca_general, 'CANON AIGUA (ACA)', 0, 50, 2),
            # Línia amb un contracte d'un altre tipus d'ús: ha d'anar a la columna de la factura
            line(invoice, cls.lt_aca_fixed, 'CANON AIGUA (ACA)', 0, 1, 3, contract=cls.other_contract),
            # Línies de l'abonament sense contracte ni interval
            line(refund, cls.lt_consum, 'AIGUA', None, -10, -12, contract=None),
        ])

    def _sheet_rows(self):
        captured = {}

        def fake_save_report(content, **kwargs):
            captured['wb'] = content

        request = SimpleNamespace(data={'billing_ids': str(self.billing.id), 'include_preinvoices': True})
        with mock.patch.object(report_service, 'save_report', side_effect=fake_save_report):
            report_service.generate_mini_register_billing_summary(request, None, None)
        return [list(values) for values in captured['wb'].active.iter_rows(values_only=True)]

    def _rows(self):
        # Etiqueta -> valor de la columna TOTAL (una sola explotació: la darrera columna amb valor)
        rows = {}
        for values in self._sheet_rows():
            numbers = [v for v in values[1:] if isinstance(v, (int, float))]
            if values[0] and numbers:
                rows[values[0].strip()] = numbers[-1]
        return rows

    def test_m3_and_amounts_add_up(self):
        rows = self._rows()

        # Consum brut amb l'abonament restat: 50 - 10
        self.assertEqual(rows['TOTAL M3 (Consum Brut)'], 40)
        # La quota fixa no compta com a m3 de tram
        self.assertEqual(rows['TOTAL M3 FACTURAT ALS TRAMS (AIGUA)'], 50)
        self.assertEqual(rows['-> M3 AIGUA FACTURADA SENSE TRAM (Interval 0)'], -10)
        self.assertEqual(rows['-> M3 DESVIAMENTS / ARRODONIMENTS'], 0)

        self.assertEqual(rows['AIGUA - CONSUM TRAM 1 M3'], 30)
        self.assertEqual(rows['AIGUA - CONSUM TRAM 2 M3'], 20)
        self.assertEqual(rows['AIGUA - QUOTA FIXA DE SERVEI CALIBRE 6 QUOTES/UNITATS'], 1)
        self.assertNotIn('AIGUA TRAM 6 M3', rows)

        # Cada concepte de l'ACA en una fila pròpia: els m3 no es dupliquen
        self.assertEqual(rows["CANON AIGUA (ACA) - CANON D'ÚS ESPECÍFIC M3"], 50)
        self.assertEqual(rows["CANON AIGUA (ACA) - CANON D'ÚS GENERAL M3"], 50)
        self.assertEqual(rows['CANON AIGUA (ACA) - PART FIXA QUOTES/UNITATS'], 1)

        # Les línies de l'abonament (sense contracte) també surten a les columnes per tipus d'ús
        self.assertEqual(rows['AIGUA - CONSUM M3'], -10)
        product_amounts = sum(v for label, v in rows.items() if label.endswith(' TOTAL SENSE IVA') and label != 'TOTAL SENSE IVA')
        self.assertAlmostEqual(product_amounts, rows['TOTAL SENSE IVA'])
        self.assertAlmostEqual(rows['TOTAL SENSE IVA'], 58)

    def test_negative_deviation_is_shown(self):
        Invoice.objects.filter(billing=self.billing, status__isnull=True).update(consumption=45)

        rows = self._rows()

        self.assertEqual(rows['-> M3 DESVIAMENTS / ARRODONIMENTS'], -5)

    def test_product_rows_add_up_per_use_type_column(self):
        sheet_rows = self._sheet_rows()
        total = next(r for r in sheet_rows if r[0] == 'TOTAL SENSE IVA')
        products = [r for r in sheet_rows if isinstance(r[0], str) and r[0].endswith(' TOTAL SENSE IVA')
                    and r[0] != 'TOTAL SENSE IVA']
        header = next(r for r in sheet_rows if 'TOTAL' in r[1:] and r[0] in ('', None))
        # Només hi ha la columna del tipus d'ús de les factures
        self.assertNotIn('INDUSTRIAL', header)
        for col, value in enumerate(total[1:], start=1):
            if isinstance(value, (int, float)):
                column_sum = sum(r[col] for r in products if isinstance(r[col], (int, float)))
                self.assertAlmostEqual(column_sum, value, msg=header[col])

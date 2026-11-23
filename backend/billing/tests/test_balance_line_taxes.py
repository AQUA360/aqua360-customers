from decimal import Decimal, ROUND_HALF_UP

from django.test import TestCase

from billing.models import Invoice, InvoiceLineItem
from billing.utils.invoice_service import balance_line_taxes, get_totals
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals


class BalanceLineTaxesTest(TestCase):
    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)
        self.invoice = Invoice.objects.create(token='TAX-TEST', number='TAX-TEST')

    def add_line(self, price, percent, tax_price=None, is_active=True):
        if tax_price is None:
            tax_price = float(
                (Decimal(str(price)) * Decimal(percent) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            )
        return InvoiceLineItem.objects.create(
            invoice=self.invoice, price=price, tax_percent=Decimal(percent),
            tax_price=tax_price, is_active=is_active,
        )

    def line_taxes(self):
        return [
            round(li.tax_price, 2)
            for li in self.invoice.line_items.filter(is_active=True).order_by('id')
        ]

    def test_vat_is_calculated_on_the_base_of_each_rate(self):
        # 0,50 x 21% = 0,105 -> 0,11 per línia (0,22), però sobre 1,00 € de base és 0,21.
        self.add_line(0.50, 21)
        self.add_line(0.50, 21)

        balance_line_taxes(self.invoice)
        subtotal, taxes, taxes_base, total = get_totals(self.invoice)

        self.assertEqual(sorted(self.line_taxes()), [0.10, 0.11])
        self.assertAlmostEqual(taxes['21.00'], 0.21)
        self.assertAlmostEqual(total, 1.21)

    def test_line_total_follows_the_adjusted_vat(self):
        self.add_line(0.50, 21)
        self.add_line(0.50, 21)

        balance_line_taxes(self.invoice)

        totals = sorted(float(li.total) for li in self.invoice.line_items.all())
        self.assertEqual(totals, [0.60, 0.61])

    def test_each_rate_is_balanced_separately(self):
        self.add_line(0.50, 21)
        self.add_line(0.50, 21)
        untouched = [self.add_line(0.15, 10), self.add_line(0.20, 10)]

        balance_line_taxes(self.invoice)
        subtotal, taxes, taxes_base, total = get_totals(self.invoice)

        self.assertAlmostEqual(taxes['21.00'], 0.21)
        self.assertAlmostEqual(taxes['10.00'], 0.04)
        for li in untouched:
            before = li.tax_price
            li.refresh_from_db()
            self.assertEqual(li.tax_price, before)

    def test_already_matching_invoice_is_not_changed(self):
        lines = [self.add_line(10.05, 21) for _ in range(3)]

        balance_line_taxes(self.invoice)

        for li in lines:
            li.refresh_from_db()
            self.assertAlmostEqual(li.tax_price, 2.11)

    def test_negative_lines_are_balanced(self):
        self.add_line(-0.50, 21, tax_price=-0.11)
        self.add_line(-0.50, 21, tax_price=-0.11)

        balance_line_taxes(self.invoice)
        subtotal, taxes, taxes_base, total = get_totals(self.invoice)

        self.assertAlmostEqual(taxes['21.00'], -0.21)
        self.assertAlmostEqual(total, -1.21)

    def test_inactive_lines_are_ignored(self):
        self.add_line(0.50, 21)
        self.add_line(0.50, 21)
        inactive = self.add_line(0.50, 21, is_active=False)

        balance_line_taxes(self.invoice)

        inactive.refresh_from_db()
        self.assertAlmostEqual(inactive.tax_price, 0.11)
        self.assertAlmostEqual(sum(self.line_taxes()), 0.21)

    def test_differences_not_caused_by_rounding_are_left_alone(self):
        # IVA posat a mà: la diferència és de molts cèntims, no d'arrodoniment.
        line = self.add_line(100.00, 21, tax_price=10.00)

        balance_line_taxes(self.invoice)

        line.refresh_from_db()
        self.assertAlmostEqual(line.tax_price, 10.00)

from decimal import Decimal

from django.test import TestCase

from billing.models import Invoice, InvoiceLineItem
from coredata.models import ConfigProject
from pricing.models import (
    AccountingConcept,
    AccountingPricing,
    AccountingType,
    PriceRate,
    Product,
)
from pricing.utils.accounting_service import _group_lineitem_amounts
from service.models import Company, Exploitation


def _bucket_total(buckets, pricing_id):
    groups = buckets.get(pricing_id) or {}
    total = Decimal('0')
    for bucket in groups.values():
        total += bucket.get('total') or Decimal('0')
    return total


class LineitemRestCatchAllTests(TestCase):
    """covers_undeclared lineitem pricing claims amounts not matched by specifics."""

    def setUp(self):
        ConfigProject.objects.create(token='invoice_status_cancelled_token', value='-6')
        self.company = Company.objects.create(name='Aigües Test', vat='B00000001')
        self.exploitation = Exploitation.objects.create(token='EXP1', name='Explotació 1')
        self.other_exploitation = Exploitation.objects.create(token='EXP2', name='Explotació 2')
        self.accounting_type = AccountingType.objects.create(
            token='lineitem',
            name='Line items',
            add_taxes=False,
            add_subtotals=True,
        )
        self.concept = AccountingConcept.objects.create(
            token='700',
            name='Ingressos',
            category='lineitem',
            type=self.accounting_type,
        )
        self.product = Product.objects.create(
            token='WATER',
            name='Aigua',
            company=self.company,
            exploitation=self.exploitation,
        )
        self.rate_aa = PriceRate.objects.create(token='AA', name='AA', product=self.product)
        self.rate_bb = PriceRate.objects.create(token='BB', name='BB', product=self.product)
        self.rate_cc = PriceRate.objects.create(token='CC', name='CC', product=self.product)
        self.rate_dd = PriceRate.objects.create(token='DD', name='DD', product=self.product)

        self.invoice = Invoice.objects.create(
            serie_final='REST/1',
            token='REST/1',
            exploitation=self.exploitation,
            company=self.company,
        )
        for rate, amount in (
            (self.rate_aa, '30'),
            (self.rate_bb, '25'),
            (self.rate_cc, '15'),
            (self.rate_dd, '7'),
        ):
            InvoiceLineItem.objects.create(
                invoice=self.invoice,
                product=self.product,
                price_rate=rate,
                price=float(amount),
                total=Decimal(amount),
                tax_price=0,
                tax_percent=Decimal('0'),
                is_active=True,
            )

    def _pricing(self, *, token, name, covers_undeclared=False, exploitation=None, products=None, price_rates=None):
        pricing = AccountingPricing.objects.create(
            token=token,
            name=name,
            accounting_concept=self.concept,
            company=self.company,
            exploitation=exploitation if exploitation is not None else self.exploitation,
            covers_undeclared=covers_undeclared,
            is_active=True,
        )
        if products:
            pricing.products.set(products)
        if price_rates:
            pricing.price_rates.set(price_rates)
        return pricing

    def test_specific_aa_cc_and_rest_remainder(self):
        pricing_aa = self._pricing(
            token='AA',
            name='AA',
            products=[self.product],
            price_rates=[self.rate_aa],
        )
        pricing_cc = self._pricing(
            token='CC',
            name='CC',
            products=[self.product],
            price_rates=[self.rate_cc],
        )
        pricing_rest = self._pricing(token='REST', name='REST', covers_undeclared=True)

        pricings = AccountingPricing.objects.filter(
            id__in=[pricing_aa.id, pricing_cc.id, pricing_rest.id],
        ).select_related('accounting_concept').prefetch_related(
            'products', 'price_rates', 'line_item_types', 'price_intervals', 'price_variables',
        )
        buckets = _group_lineitem_amounts(pricings, Invoice.objects.filter(id=self.invoice.id))

        self.assertEqual(_bucket_total(buckets, pricing_aa.id), Decimal('30'))
        self.assertEqual(_bucket_total(buckets, pricing_cc.id), Decimal('15'))
        self.assertEqual(_bucket_total(buckets, pricing_rest.id), Decimal('32'))

    def test_specific_only_leaves_unmatched_undeclared(self):
        pricing_aa = self._pricing(
            token='AA',
            name='AA',
            products=[self.product],
            price_rates=[self.rate_aa],
        )
        pricing_cc = self._pricing(
            token='CC',
            name='CC',
            products=[self.product],
            price_rates=[self.rate_cc],
        )
        pricings = AccountingPricing.objects.filter(
            id__in=[pricing_aa.id, pricing_cc.id],
        ).select_related('accounting_concept').prefetch_related(
            'products', 'price_rates', 'line_item_types', 'price_intervals', 'price_variables',
        )
        buckets = _group_lineitem_amounts(pricings, Invoice.objects.filter(id=self.invoice.id))

        self.assertEqual(_bucket_total(buckets, pricing_aa.id), Decimal('30'))
        self.assertEqual(_bucket_total(buckets, pricing_cc.id), Decimal('15'))
        self.assertEqual(sum((_bucket_total(buckets, pid) for pid in buckets), Decimal('0')), Decimal('45'))

    def test_is_default_alone_does_not_catch_lineitems(self):
        orphan = self._pricing(token='ORPHAN', name='Orphan', covers_undeclared=False)
        pricing_default = AccountingPricing.objects.create(
            token='DEFAULT',
            name='Default only',
            accounting_concept=self.concept,
            company=self.company,
            exploitation=self.exploitation,
            is_default=True,
            covers_undeclared=False,
            is_active=True,
        )
        pricing_rest = self._pricing(token='REST', name='REST', covers_undeclared=True)

        pricings = AccountingPricing.objects.filter(
            id__in=[orphan.id, pricing_default.id, pricing_rest.id],
        ).select_related('accounting_concept').prefetch_related(
            'products', 'price_rates', 'line_item_types', 'price_intervals', 'price_variables',
        )
        buckets = _group_lineitem_amounts(pricings, Invoice.objects.filter(id=self.invoice.id))

        self.assertNotIn(orphan.id, buckets)
        self.assertNotIn(pricing_default.id, buckets)
        self.assertEqual(_bucket_total(buckets, pricing_rest.id), Decimal('77'))

    def test_exploitation_scoped_rest_does_not_steal_other_exploitation(self):
        other_invoice = Invoice.objects.create(
            serie_final='REST/2',
            token='REST/2',
            exploitation=self.other_exploitation,
            company=self.company,
        )
        InvoiceLineItem.objects.create(
            invoice=other_invoice,
            product=self.product,
            price_rate=self.rate_bb,
            price=40.0,
            total=Decimal('40'),
            tax_price=0,
            tax_percent=Decimal('0'),
            is_active=True,
        )

        pricing_rest_exp1 = self._pricing(
            token='REST1',
            name='REST EXP1',
            covers_undeclared=True,
            exploitation=self.exploitation,
        )
        pricing_rest_exp2 = self._pricing(
            token='REST2',
            name='REST EXP2',
            covers_undeclared=True,
            exploitation=self.other_exploitation,
        )

        pricings = AccountingPricing.objects.filter(
            id__in=[pricing_rest_exp1.id, pricing_rest_exp2.id],
        ).select_related('accounting_concept').prefetch_related(
            'products', 'price_rates', 'line_item_types', 'price_intervals', 'price_variables',
        )
        invoices = Invoice.objects.filter(id__in=[self.invoice.id, other_invoice.id])
        buckets = _group_lineitem_amounts(pricings, invoices)

        self.assertEqual(_bucket_total(buckets, pricing_rest_exp1.id), Decimal('77'))
        self.assertEqual(_bucket_total(buckets, pricing_rest_exp2.id), Decimal('40'))

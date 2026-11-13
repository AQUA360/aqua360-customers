from datetime import date

from django.test import TestCase

from pricing.models import (
    ArticleCode,
    BillingRange,
    LineItemType,
    PriceRate,
    Product,
    ProductOrigin,
    Tax,
)
from pricing.utils.accounting_catalog import accounting_catalog_rows
from service.models import Company, Exploitation


class AccountingCatalogTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Aigües Exemple', vat='B12345678')
        self.origin = ProductOrigin.objects.create(token='aigua', name='Aigua')
        self.tax = Tax.objects.create(token='IVA10', name='IVA 10%', percent=10)
        self.article = ArticleCode.objects.create(token='CONS', name='Consum')
        self.exploitation = Exploitation.objects.create(token='EXP1', name='Explotació 1')
        self.other_exploitation = Exploitation.objects.create(token='EXP2', name='Explotació 2')

    def _line(self, product, price_rate_token, line_token, *, active_range=True, line_active=True, range_end=None):
        price_rate = PriceRate.objects.create(
            token=price_rate_token,
            name=f'Tarifa {price_rate_token}',
            product=product,
            is_active=True,
        )
        billing_range = BillingRange.objects.create(
            token=f'BR-{line_token}',
            name=f'Tram {line_token}',
            price_rate=price_rate,
            end=range_end,
            is_active=True,
        )
        if active_range:
            price_rate.billing_range_active = billing_range
            price_rate.save(update_fields=['billing_range_active'])
        return LineItemType.objects.create(
            token=line_token,
            name=f'Concepte {line_token}',
            billing_range=billing_range,
            tax=self.tax,
            article=self.article,
            is_active=line_active,
        )

    def _product(self, token, exploitation=None):
        return Product.objects.create(
            token=token,
            name=f'Producte {token}',
            company=self.company,
            origin=self.origin,
            exploitation=exploitation,
            is_active=True,
        )

    def test_row_uses_the_provider_columns(self):
        product = self._product('AIGUA', self.exploitation)
        self._line(product, 'DOM', 'CONS-1')

        rows = accounting_catalog_rows()

        self.assertEqual(rows, [{
            'Product.Company': 'Aigües Exemple',
            'Product.name': 'Producte AIGUA',
            'Product.token': 'AIGUA',
            'Product.Origin': 'Aigua',
            'PriceRate.name': 'Tarifa DOM',
            'PriceRate.token': 'DOM',
            'LineItemType.token': 'CONS-1',
            'LineItemType.name': 'Concepte CONS-1',
            'LineItemType.Iva': 'IVA 10%',
            'LineItemType.tax_token': 'IVA10',
            'LineItemType.tax_percent': 10,
            'LineItemType.article.token': 'CONS',
            'LineItemType.article.name': 'Consum',
        }])

    def test_closed_and_inactive_lines_stay_out(self):
        product = self._product('AIGUA', self.exploitation)
        self._line(product, 'ANTIGA', 'TANCADA', active_range=False, range_end=date(2020, 1, 1))
        self._line(product, 'INACTIVA', 'INACTIVA', line_active=False)
        current = self._line(product, 'DOM', 'VIGENT')
        old_range = BillingRange.objects.create(
            token='BR-OLD',
            name='Tram antic',
            price_rate=current.billing_range.price_rate,
            end=date(2020, 1, 1),
            is_active=True,
        )
        LineItemType.objects.create(
            token='ANTIC',
            name='Concepte antic',
            billing_range=old_range,
            tax=self.tax,
            article=self.article,
            is_active=True,
        )

        tokens = [row['LineItemType.token'] for row in accounting_catalog_rows()]

        self.assertEqual(tokens, ['VIGENT'])

    def test_exploitation_keeps_its_products_and_the_shared_ones(self):
        own = self._product('PROPI', self.exploitation)
        shared = self._product('COMPARTIT', None)
        other = self._product('ALIENA', self.other_exploitation)
        self._line(own, 'P1', 'PROPI-1')
        self._line(shared, 'P2', 'COMPARTIT-1')
        self._line(other, 'P3', 'ALIENA-1')

        tokens = [
            row['LineItemType.token']
            for row in accounting_catalog_rows(self.exploitation.id)
        ]

        self.assertCountEqual(tokens, ['PROPI-1', 'COMPARTIT-1'])

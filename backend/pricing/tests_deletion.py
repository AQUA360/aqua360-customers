from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from billing.models import InvoiceLineItem
from coredata.models import ConfigProject
from logger.models import LogPriceRateChange, LogProductChange
from contract.models import Contract, ContractPriceRate
from pricing.models import BillingRange, LineItemType, PriceRate, Product

PRICE_RATE_URL = '/pricing/price-rate/'
PRODUCT_URL = '/pricing/product/'


class PricingDeletionApiTests(TestCase):
    """Les tarifes i productes només es poden eliminar si no s'han fet servir en contractes ni factures."""

    def setUp(self):
        # La necessita el senyal post_save de Contract
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': 'terminated'})
        user = User.objects.create_user(username='tarifes', password='x')
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='pricing', codename__in=['delete_pricerate', 'delete_product'],
        ))
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.product = Product.objects.create(token='P', name='Producte')
        self.price_rate = PriceRate.objects.create(token='T', name='Tarifa', product=self.product)

    def test_detail_says_whether_it_can_be_deleted(self):
        self.client.force_authenticate(User.objects.create_superuser(username='admin', password='x'))
        self.assertTrue(self.client.get(f'{PRICE_RATE_URL}{self.price_rate.id}/').data['is_deletable'])
        self.assertTrue(self.client.get(f'{PRODUCT_URL}{self.product.id}/').data['is_deletable'])

        InvoiceLineItem.objects.create(price_rate=self.price_rate)

        self.assertFalse(self.client.get(f'{PRICE_RATE_URL}{self.price_rate.id}/').data['is_deletable'])
        self.assertFalse(self.client.get(f'{PRODUCT_URL}{self.product.id}/').data['is_deletable'])

    def test_unused_price_rate_is_deactivated(self):
        response = self.client.delete(f'{PRICE_RATE_URL}{self.price_rate.id}/')

        self.assertEqual(response.status_code, 204)
        self.price_rate.refresh_from_db()
        self.assertFalse(self.price_rate.is_active)

    def test_price_rate_assigned_to_a_contract_is_kept(self):
        contract = Contract.objects.create()
        contract.price_rates.add(ContractPriceRate.objects.create(price_rate=self.price_rate))

        response = self.client.delete(f'{PRICE_RATE_URL}{self.price_rate.id}/')

        self.assertEqual(response.status_code, 400)
        self.price_rate.refresh_from_db()
        self.assertTrue(self.price_rate.is_active)

    def test_price_rate_used_in_an_invoice_is_kept(self):
        InvoiceLineItem.objects.create(price_rate=self.price_rate)

        response = self.client.delete(f'{PRICE_RATE_URL}{self.price_rate.id}/')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(PriceRate.objects.get(id=self.price_rate.id).is_active)

    def test_price_rate_used_through_an_invoice_concept_is_kept(self):
        billing_range = BillingRange.objects.create(price_rate=self.price_rate)
        InvoiceLineItem.objects.create(line_item_type=LineItemType.objects.create(billing_range=billing_range))

        response = self.client.delete(f'{PRICE_RATE_URL}{self.price_rate.id}/')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(PriceRate.objects.get(id=self.price_rate.id).is_active)

    def test_configured_price_rate_is_kept(self):
        ConfigProject.objects.update_or_create(token='connection_rights_price_rate_token', defaults={'value': 'T'})

        response = self.client.delete(f'{PRICE_RATE_URL}{self.price_rate.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('configurada', response.data['detail'])

        response = self.client.delete(f'{PRODUCT_URL}{self.product.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(PriceRate.objects.get(id=self.price_rate.id).is_active)

    def test_unused_product_is_deactivated_with_its_price_rates(self):
        response = self.client.delete(f'{PRODUCT_URL}{self.product.id}/')

        self.assertEqual(response.status_code, 204)
        self.product.refresh_from_db()
        self.price_rate.refresh_from_db()
        self.assertFalse(self.product.is_active)
        self.assertFalse(self.price_rate.is_active)
        self.assertTrue(LogProductChange.objects.filter(object=self.product, changed_field='is_active').exists())
        self.assertTrue(LogPriceRateChange.objects.filter(object=self.price_rate, changed_field='is_active').exists())

    def test_product_with_a_price_rate_in_use_is_kept(self):
        Contract.objects.create().registration_price_rates.add(self.price_rate)

        response = self.client.delete(f'{PRODUCT_URL}{self.product.id}/')

        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

    def test_product_used_in_an_invoice_is_kept(self):
        InvoiceLineItem.objects.create(product=self.product)

        response = self.client.delete(f'{PRODUCT_URL}{self.product.id}/')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Product.objects.get(id=self.product.id).is_active)

    def test_price_rate_without_product_is_rejected(self):
        user = User.objects.create_user(username='alta-tarifes', password='x')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='pricing', codename='add_pricerate'))
        self.client.force_authenticate(user)

        response = self.client.post(PRICE_RATE_URL, {'token': 'SENSE', 'name': 'Sense producte'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('product', response.data)
        self.assertFalse(PriceRate.objects.filter(token='SENSE').exists())

    def test_price_rate_without_product_is_listed_and_can_be_deleted(self):
        self.client.force_authenticate(User.objects.create_superuser(username='admin', password='x'))
        orphan = PriceRate.objects.create(token='ORFE', name='Sense producte')

        response = self.client.get(PRICE_RATE_URL, {'exploitation': 999})
        self.assertIn(orphan.id, [row['id'] for row in response.data['results']])

        response = self.client.delete(f'{PRICE_RATE_URL}{orphan.id}/')
        self.assertEqual(response.status_code, 204)

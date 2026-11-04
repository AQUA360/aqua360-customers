from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Invoice
from documentmanager.models import Document


class TestInvoiceSendGroupedEmailValidation(TestCase):
    """Les dades d'entrada incorrectes de l'enviament agrupat retornen 400, no 500."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='grouped-email', password='x')
        # bulk_create: els signals de la factura no intervenen en el que es prova.
        Invoice.objects.bulk_create([
            Invoice(token='F-ACTIVE', serie_final='FC/1'),
            Invoice(token='F-INACTIVE', serie_final='FC/2'),
        ])
        cls.active = Invoice.objects.get(token='F-ACTIVE')
        cls.inactive = Invoice.objects.get(token='F-INACTIVE')
        for invoice, is_active in ((cls.active, True), (cls.inactive, False)):
            document = Document.objects.create(
                entity='FACTURES', field='FACTURA', entity_id=invoice.id,
                document_name=f'FACTURA_{invoice.id}.pdf', service='hdd', is_active=is_active,
            )
            Invoice.objects.filter(id=invoice.id).update(invoice_file=document)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('invoice-send-grouped-email')

    def post(self, **data):
        payload = {'email': 'client@example.com', 'invoice_ids': [self.active.id]}
        payload.update(data)
        return self.client.post(self.url, payload, format='json')

    def test_email_not_string(self):
        response = self.post(email=['client@example.com'])
        self.assertEqual(response.status_code, 400)

    def test_email_without_addresses(self):
        response = self.post(email=';;;')
        self.assertEqual(response.status_code, 400)

    def test_invoice_ids_not_integers(self):
        for value in (float(self.active.id) + 0.9, True, 'abc'):
            response = self.post(invoice_ids=[value])
            self.assertEqual(response.status_code, 400, value)

    def test_company_config_id_not_integer(self):
        response = self.post(company_config_id='abc')
        self.assertEqual(response.status_code, 400)
        self.assertIn('company_config_id', response.data['error'])

    def test_inactive_invoice_document(self):
        response = self.post(invoice_ids=[self.active.id, self.inactive.id])
        self.assertEqual(response.status_code, 400)
        self.assertIn('FC/2', response.data['error'])
        self.assertNotIn('FC/1', response.data['error'])

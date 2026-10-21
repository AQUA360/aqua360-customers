import html
import os

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

from coredata.models import Address
from service.models import Company
from service.serializers.company_serializer import CompanySerializer


def render_repo_template(rel_path, context):
    # Es llegeix el fitxer del repo directament: el loader de Django prioritza
    # les variants `_personalized` locals de cada client.
    with open(os.path.join(settings.BASE_DIR, rel_path), encoding='utf-8') as f:
        return html.unescape(Template(f.read()).render(Context(context)))


class CompanyContactTextsTemplateTest(SimpleTestCase):
    """Les plantilles fan servir els textos de contacte i avaries configurats a l'empresa."""

    HEADER_TEMPLATES = [
        'billing/templates/invoice_template.html',
        'billing/templates/invoice_request_template.html',
        'billing/templates/payment_proof_template.html',
    ]
    LABEL_TEMPLATES = [
        'communication/templates/basic_email.html',
        'communication/templates/basic_letter.html',
        'contract/templates/contract_template.html',
        'contract/templates/contract_termination_template.html',
        'claimrequest/templates/pay_reminder_template.html',
        'claimrequest/templates/letter_suspension_template.html',
        'billing/templates/invoice_template_default.html',
        'billing/templates/payment_template.html',
    ]

    def _company(self, **kwargs):
        company = {
            'phone': '900000001',
            'phone2': '900000002',
            'customer_service_label': None,
            'customer_service_schedule': None,
            'breakdown_label': None,
            'breakdown_schedule': None,
        }
        company.update(kwargs)
        return company

    def _render(self, rel_path, company):
        return render_repo_template(rel_path, {'company': company, 'logo': None, 'secondary_color': '#000000'})

    def test_header_uses_configured_texts(self):
        company = self._company(
            customer_service_label='Oficina',
            customer_service_schedule='Horari oficina',
            breakdown_label='Urgències',
            breakdown_schedule='Horari urgències',
        )
        for rel_path in self.HEADER_TEMPLATES:
            with self.subTest(rel_path):
                rendered = self._render(rel_path, company)
                for text in ('Oficina', 'Horari oficina', 'Urgències', 'Horari urgències', '900000002'):
                    self.assertIn(text, rendered)
                self.assertNotIn('24 hores', rendered)
                self.assertNotIn('dilluns a divendres', rendered)

    def test_header_keeps_previous_texts_when_empty(self):
        for rel_path in self.HEADER_TEMPLATES:
            with self.subTest(rel_path):
                rendered = self._render(rel_path, self._company())
                self.assertIn('Atenció al client', rendered)
                self.assertIn('Avaries', rendered)
                self.assertIn('24 hores', rendered)
                self.assertIn('dilluns a divendres de 8 a 15 hores', rendered)

    def test_header_hides_disabled_blocks_and_schedules(self):
        company = self._company(show_customer_service_schedule=False, show_breakdown_block=False)
        for rel_path in self.HEADER_TEMPLATES:
            with self.subTest(rel_path):
                rendered = self._render(rel_path, company)
                self.assertIn('Atenció al client', rendered)
                self.assertNotIn('dilluns a divendres', rendered)
                self.assertNotIn('Avaries', rendered)
                self.assertNotIn('900000002', rendered)

        company = self._company(show_customer_service_block=False, show_breakdown_schedule=False)
        for rel_path in self.HEADER_TEMPLATES:
            with self.subTest(rel_path):
                rendered = self._render(rel_path, company)
                self.assertNotIn('Atenció al client', rendered)
                self.assertIn('Avaries', rendered)
                self.assertNotIn('24 hores', rendered)

    def test_labels_hide_disabled_blocks(self):
        company = self._company(customer_service_label='Oficina', breakdown_label='Urgències',
                                show_customer_service_block=False, show_breakdown_block=False)
        for rel_path in self.LABEL_TEMPLATES:
            with self.subTest(rel_path):
                rendered = self._render(rel_path, company)
                self.assertNotIn('OFICINA', rendered)
                self.assertNotIn('URGÈNCIES', rendered)
                self.assertNotIn('900000002', rendered)

    def test_labels_use_configured_texts_or_previous_ones(self):
        configured = self._company(customer_service_label='Oficina', breakdown_label='Urgències')
        for rel_path in self.LABEL_TEMPLATES:
            with self.subTest(rel_path):
                rendered = self._render(rel_path, configured)
                self.assertIn('OFICINA', rendered)
                self.assertIn('URGÈNCIES', rendered)
                self.assertNotIn("AVERIES", rendered)

                rendered = self._render(rel_path, self._company())
                self.assertIn("ATENCIÓ AL CLIENT", rendered)
                self.assertNotIn('OFICINA', rendered)


class CompanyContactTextsSerializerTest(TestCase):
    """El formulari d'empresa no envia els camps buits: en un PUT es buiden."""

    def setUp(self):
        self.address = Address.objects.create()
        self.company = Company.objects.create(
            name='Empresa', address=self.address,
            customer_service_label='Oficina', customer_service_schedule='Horari oficina',
            breakdown_label='Urgències', breakdown_schedule='Horari urgències',
        )

    def _save(self, data, partial=False):
        serializer = CompanySerializer(self.company, data={'address': self.address.id, **data}, partial=partial)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.company.refresh_from_db()

    def test_put_without_fields_clears_them(self):
        self._save({'name': 'Empresa', 'breakdown_schedule': 'Sempre'})
        self.assertIsNone(self.company.customer_service_label)
        self.assertIsNone(self.company.customer_service_schedule)
        self.assertIsNone(self.company.breakdown_label)
        self.assertEqual(self.company.breakdown_schedule, 'Sempre')

    def test_patch_without_fields_keeps_them(self):
        self._save({'name': 'Empresa'}, partial=True)
        self.assertEqual(self.company.customer_service_label, 'Oficina')
        self.assertEqual(self.company.breakdown_schedule, 'Horari urgències')

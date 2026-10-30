from types import SimpleNamespace

from django.test import TestCase

from billing.utils.barcode_service import get_barcode_values, get_payments_company_bank, get_reference_suffix
from coredata.models import ConfigProject
from service.models import Company, CompanyBank
from service.serializers.company_bank_serializer import CompanyBankSerializer


class TestBarcodeSuffixPerBank(TestCase):
    """El sufix del codi de barres és propi de cada compte bancari de l'empresa."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Empresa A', vat='B12345678')
        cls.bank_1 = CompanyBank.objects.create(company=cls.company, iban='ES1100000000000000000001', barcode_suffix='502')
        cls.bank_2 = CompanyBank.objects.create(company=cls.company, iban='ES2200000000000000000002', barcode_suffix='503')
        cls.bank_empty = CompanyBank.objects.create(company=cls.company, iban='ES3300000000000000000003')

    def setUp(self):
        # Les dades inicials ja porten el sufix global: cada test parteix sense
        ConfigProject.objects.filter(token='reference_suffix_barcode_token').delete()

    def barcode_data(self, company_bank):
        return {'company': self.company, 'company_bank': company_bank,
                'reference': '123', 'ident': '1', 'total_final': 10.5}

    def test_each_bank_uses_its_own_suffix(self):
        self.assertEqual(get_barcode_values(self.barcode_data(self.bank_1))['suffix'], '502')
        self.assertEqual(get_barcode_values(self.barcode_data(self.bank_2))['suffix'], '503')

    def test_bank_without_suffix_falls_back_to_global(self):
        self.assertEqual(get_reference_suffix(self.bank_empty), '501')
        ConfigProject.objects.create(token='reference_suffix_barcode_token', value='504')
        self.assertEqual(get_reference_suffix(self.bank_empty), '504')
        self.assertEqual(get_reference_suffix(self.bank_1), '502')

    def test_saving_a_bank_does_not_change_the_others(self):
        serializer = CompanyBankSerializer(self.bank_1, data={'barcode_suffix': '599'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.bank_1.refresh_from_db()
        self.bank_2.refresh_from_db()
        self.assertEqual(self.bank_1.barcode_suffix, '599')
        self.assertEqual(self.bank_2.barcode_suffix, '503')
        self.assertFalse(ConfigProject.objects.filter(token='reference_suffix_barcode_token').exists())
        self.assertEqual(CompanyBankSerializer(self.bank_2).data['barcode_suffix'], '503')

    def test_representation_keeps_stored_suffix_apart_from_effective(self):
        ConfigProject.objects.create(token='reference_suffix_barcode_token', value='504')
        data = CompanyBankSerializer(self.bank_empty).data
        self.assertIsNone(data['barcode_suffix'])
        self.assertEqual(data['effective_barcode_suffix'], '504')

    def test_suffix_must_have_three_digits(self):
        for value in ['12', '1234', 'abc', '５０２']:
            serializer = CompanyBankSerializer(self.bank_1, data={'barcode_suffix': value}, partial=True)
            self.assertFalse(serializer.is_valid(), value)
        serializer = CompanyBankSerializer(self.bank_1, data={'barcode_suffix': ''}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.bank_1.refresh_from_db()
        self.assertIsNone(self.bank_1.barcode_suffix)

    def test_grouped_payments_use_common_collection_bank(self):
        invoice_1 = SimpleNamespace(payment_company_bank=self.bank_2)
        invoice_2 = SimpleNamespace(payment_company_bank=self.bank_2)
        payments = [SimpleNamespace(invoice=invoice_1), SimpleNamespace(invoice=invoice_2), SimpleNamespace(invoice=None)]
        self.assertEqual(get_payments_company_bank(payments), self.bank_2)

        payments.append(SimpleNamespace(invoice=SimpleNamespace(payment_company_bank=self.bank_1)))
        self.assertIsNone(get_payments_company_bank(payments))

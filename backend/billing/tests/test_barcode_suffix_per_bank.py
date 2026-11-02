from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from billing.utils.barcode_service import get_barcode_values, get_payments_company_bank, get_reference_suffix
from service.utils.company_bank_service import get_payment_company_bank
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

    def test_invalid_global_suffix_falls_back_to_501(self):
        config = ConfigProject.objects.create(token='reference_suffix_barcode_token', value='504')
        for value in ['12', '1234', '５０２', '١٢٣', ' 504 ']:
            with self.subTest(value=value):
                config.value = value
                config.save()
                self.assertEqual(get_reference_suffix(self.bank_empty), '501')
        config.value = '504'
        config.save()
        self.assertEqual(get_reference_suffix(self.bank_empty), '504')

    def test_migration_copies_only_three_ascii_digits(self):
        migration = import_module('service.migrations.0139_companybank_barcode_suffix')
        from django.apps import apps

        config = ConfigProject.objects.create(token='reference_suffix_barcode_token', value='504')
        for value, expected in [('12', None), ('1234', None), ('５０２', None), ('٥٠٢', None), (' 504 ', None), ('504', '504')]:
            with self.subTest(value=value):
                config.value = value
                config.save()
                self.bank_empty.barcode_suffix = None
                self.bank_empty.save()
                migration.copy_global_suffix(apps, None)
                self.bank_empty.refresh_from_db()
                self.assertEqual(self.bank_empty.barcode_suffix, expected)

    def test_grouped_payments_resolve_every_effective_bank(self):
        self.bank_1.is_default = True
        self.bank_1.is_active = True
        self.bank_1.save()
        explicit = SimpleNamespace(invoice=SimpleNamespace(payment_company_bank=self.bank_1))
        implicit = SimpleNamespace(invoice=SimpleNamespace(payment_company_bank=None))
        no_invoice = SimpleNamespace(invoice=None)
        self.assertEqual(get_payments_company_bank([explicit, implicit, no_invoice], self.company), self.bank_1)
        self.assertEqual(get_payments_company_bank([], self.company), self.bank_1)

        other = SimpleNamespace(invoice=SimpleNamespace(payment_company_bank=self.bank_2))
        # Grup mixt: el compte per defecte de l'empresa
        self.assertEqual(get_payments_company_bank([other, implicit], self.company), self.bank_1)
        self.assertEqual(get_payments_company_bank([other, other], self.company), self.bank_2)

        # Pagament d'un compromís sense factura: el compte de la factura del compromís
        commitment = SimpleNamespace(invoice=None, commitment_deposit=SimpleNamespace(
            invoices=SimpleNamespace(first=lambda: other.invoice)))
        self.assertEqual(get_payments_company_bank([other, commitment], self.company), self.bank_2)

    def test_payment_bank_uses_same_criteria_as_individual_document(self):
        self.bank_1.is_default = True
        self.bank_1.save()
        transfer = SimpleNamespace(invoice=None, commitment_deposit=None,
                                   payment_type_token='BANK_TRANSFER', payment_bank=self.bank_2.iban)
        self.assertEqual(get_payment_company_bank(self.company, transfer), self.bank_2)
        # Domiciliació: payment_bank és l'IBAN del client, no es fa servir
        direct_debit = SimpleNamespace(invoice=None, commitment_deposit=None,
                                       payment_type_token='DIRECT_DEBIT', payment_bank=self.bank_2.iban)
        self.assertEqual(get_payment_company_bank(self.company, direct_debit), self.bank_1)
        # Compromís sense compte a la factura: el compte del pagament del contracte
        commitment = SimpleNamespace(invoice=None, payment_bank=None, payment_type_token='DIRECT_DEBIT',
                                     commitment_deposit=SimpleNamespace(
                                         invoices=SimpleNamespace(first=lambda: None),
                                         contract=SimpleNamespace(payment=SimpleNamespace(company_iban=self.bank_2))))
        self.assertEqual(get_payment_company_bank(self.company, commitment), self.bank_2)
        # Grup amb una transferència al compte B i una factura cobrada a B
        invoice_b = SimpleNamespace(invoice=SimpleNamespace(payment_company_bank=self.bank_2))
        self.assertEqual(get_payments_company_bank([transfer, invoice_b], self.company), self.bank_2)

    def test_explicit_missing_bank_does_not_resolve_default_again(self):
        with patch('billing.utils.barcode_service.get_company_bank', side_effect=AssertionError('unexpected fallback')):
            self.assertEqual(get_barcode_values(self.barcode_data(None))['suffix'], '501')

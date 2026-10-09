from django.test import TestCase

from billing.utils.aca_company_service import ACACompanyError, resolve_aca_company
from coredata.models import ConfigProject
from service.models import Company


class TestResolveACACompany(TestCase):
    """Empresa declarant (supply_code + NIF) dels fitxers ACA.

    Amb `use_multiple_companies` el codi és el de l'empresa de les factures del fitxer, i
    factures de més d'una empresa no es poden declarar juntes.
    """

    def setUp(self):
        self.main = Company.objects.create(name='AV', vat='B00000001', supply_code='1111')
        self.other = Company.objects.create(name='MV', vat='B00000002', supply_code='2222')
        # La fila la crea la migració coredata 0100
        ConfigProject.objects.update_or_create(token='use_multiple_companies', defaults={'value': 'false'})

    def enable_multiple_companies(self):
        ConfigProject.objects.filter(token='use_multiple_companies').update(value='true')

    def test_single_company_uses_main_company(self):
        self.assertEqual(resolve_aca_company({self.other.id}, self.main), self.main)

    def test_single_company_ignores_mixed_invoices(self):
        self.assertEqual(resolve_aca_company({self.main.id, self.other.id, None}, self.main), self.main)

    def test_multiple_companies_uses_invoices_company(self):
        self.enable_multiple_companies()
        self.assertEqual(resolve_aca_company({self.other.id}, self.main), self.other)

    def test_multiple_companies_rejects_mixed_invoices(self):
        self.enable_multiple_companies()
        with self.assertRaisesMessage(ACACompanyError, "més d'una empresa (AV, MV)"):
            resolve_aca_company({self.main.id, self.other.id}, self.main)

    def test_multiple_companies_rejects_invoices_without_company(self):
        self.enable_multiple_companies()
        with self.assertRaisesMessage(ACACompanyError, 'sense empresa'):
            resolve_aca_company({self.other.id, None}, self.main)

    def test_multiple_companies_without_invoices_uses_main_company(self):
        self.enable_multiple_companies()
        self.assertEqual(resolve_aca_company(set(), self.main), self.main)

    def test_missing_supply_code(self):
        self.enable_multiple_companies()
        self.other.supply_code = ''
        self.other.save()
        with self.assertRaisesMessage(ACACompanyError, 'supply_code) de l\'empresa MV'):
            resolve_aca_company({self.other.id}, self.main)

    def test_missing_main_company(self):
        with self.assertRaisesMessage(ACACompanyError, "principal ('main_company_token')"):
            resolve_aca_company(set(), None)

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Payment
from billing.utils.remittance_routing import resolve_payment_banks
from coredata.models import Bank
from service.models import Company, CompanyBank, CompanyBankRouting

SPANISH_IBAN = 'ES9121000418450200051332'
FOREIGN_IBAN = 'DE89370400440532013000'


class TestRemittanceRoutingByOperation(TestCase):
    """Les remeses de cobrament i les transferències de retorn tenen mapes
    d'encaminament independents (`CompanyBankRouting.operation`).

    Cas de referència: es cobra als clients nacionals pel compte X i als
    estrangers pel Y, però els retorns es paguen a l'inrevés.
    """

    def setUp(self):
        self.company = Company.objects.create(name='Empresa')
        self.bank_x = CompanyBank.objects.create(
            company=self.company, iban='ES0000000000000000000001', is_active=True, is_default=True)
        self.bank_y = CompanyBank.objects.create(
            company=self.company, iban='ES0000000000000000000002', is_active=True)

        self.national = Payment.objects.create(payment_bank=SPANISH_IBAN)
        self.foreign = Payment.objects.create(payment_bank=FOREIGN_IBAN)
        self.payments = Payment.objects.filter(id__in=[self.national.id, self.foreign.id])

    def add_routing(self, operation, match_type, company_bank, bank=None):
        CompanyBankRouting.objects.create(
            company=self.company, company_bank=company_bank, bank=bank,
            match_type=match_type, operation=operation)

    def resolve(self, is_return):
        # Rebuts sense factura: s'atribueixen a l'única empresa seleccionada.
        assignments, _ = resolve_payment_banks(
            self.payments, companies=[self.company.id], is_return=is_return)
        return assignments[str(self.national.id)], assignments[str(self.foreign.id)]

    def configure_crossed_routing(self):
        collection = CompanyBankRouting.OPERATION_COLLECTION
        transfer = CompanyBankRouting.OPERATION_TRANSFER
        self.add_routing(collection, CompanyBankRouting.MATCH_DEFAULT, self.bank_x)
        self.add_routing(collection, CompanyBankRouting.MATCH_FOREIGN, self.bank_y)
        self.add_routing(transfer, CompanyBankRouting.MATCH_DEFAULT, self.bank_y)
        self.add_routing(transfer, CompanyBankRouting.MATCH_FOREIGN, self.bank_x)

    def test_cobrament_fa_servir_el_mapa_de_cobraments(self):
        self.configure_crossed_routing()
        self.assertEqual(self.resolve(is_return=False), (self.bank_x.id, self.bank_y.id))

    def test_retorn_fa_servir_el_mapa_de_transferencies(self):
        self.configure_crossed_routing()
        self.assertEqual(self.resolve(is_return=True), (self.bank_y.id, self.bank_x.id))

    def test_entitat_del_pagador_es_independent_per_operacio(self):
        entity = Bank.objects.create(token='2100')
        self.add_routing(CompanyBankRouting.OPERATION_COLLECTION,
                         CompanyBankRouting.MATCH_PAYER_BANK, self.bank_y, bank=entity)

        self.assertEqual(self.resolve(is_return=False)[0], self.bank_y.id)
        # Als retorns l'entitat no té fila: va al compte per defecte.
        self.assertEqual(self.resolve(is_return=True)[0], self.bank_x.id)

    def test_retorn_sense_mapa_propi_no_hereta_el_de_cobraments(self):
        self.add_routing(CompanyBankRouting.OPERATION_COLLECTION,
                         CompanyBankRouting.MATCH_FOREIGN, self.bank_y)

        self.assertEqual(self.resolve(is_return=True), (self.bank_x.id, self.bank_x.id))

    def test_mateixa_fila_especial_a_les_dues_operacions(self):
        self.add_routing(CompanyBankRouting.OPERATION_COLLECTION,
                         CompanyBankRouting.MATCH_DEFAULT, self.bank_x)
        # Abans de separar les operacions això xocava amb la restricció única.
        self.add_routing(CompanyBankRouting.OPERATION_TRANSFER,
                         CompanyBankRouting.MATCH_DEFAULT, self.bank_y)

        self.assertEqual(CompanyBankRouting.objects.filter(company=self.company).count(), 2)


class TestCompanyBankRoutingApiOperation(TestCase):
    """L'API de configuració desa i torna cada operació per separat, i les
    peticions sense `operation` continuen actuant sobre els cobraments."""

    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username='test_routing', password='test_routing', email='test@example.com')
        self.client = APIClient()
        self.client.force_authenticate(user)

        self.company = Company.objects.create(name='Empresa')
        self.bank_x = CompanyBank.objects.create(company=self.company, is_active=True, is_default=True)
        self.bank_y = CompanyBank.objects.create(company=self.company, is_active=True)
        self.entity = Bank.objects.create(token='2100')

    def post(self, action, data):
        return self.client.post(reverse(f'companybankrouting-{action}'), data, format='json')

    def test_set_special_i_bulk_per_operacio(self):
        response = self.post('set-special', {
            'company': self.company.id, 'match_type': 'foreign', 'company_bank': self.bank_y.id,
        })
        self.assertIn(response.status_code, (200, 201))
        response = self.post('set-special', {
            'company': self.company.id, 'match_type': 'foreign', 'company_bank': self.bank_x.id,
            'operation': 'transfer',
        })
        self.assertIn(response.status_code, (200, 201))
        response = self.post('bulk', {
            'company': self.company.id, 'company_bank': self.bank_y.id, 'banks': [self.entity.id],
            'operation': 'transfer',
        })
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('companybankrouting-matrix'), {'company': self.company.id, 'only_used': 'false'})
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['special']['foreign']['company_bank'], self.bank_y.id)
        self.assertEqual(data['transfer']['special']['foreign']['company_bank'], self.bank_x.id)

        row = next(row for row in data['banks'] if row['bank'] == self.entity.id)
        self.assertIsNone(row['company_bank'])
        self.assertEqual(row['transfer']['company_bank'], self.bank_y.id)

    def test_operacio_desconeguda(self):
        response = self.post('set-special', {
            'company': self.company.id, 'match_type': 'foreign', 'company_bank': self.bank_y.id,
            'operation': 'other',
        })
        self.assertEqual(response.status_code, 400)

from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from billing.models import Payment, PaymentRemittance, PaymentRemittanceStatus
from billing.utils.payment_remittance_lock_service import is_remittance_sent
from coredata.models import ConfigProject
from service.models import Company, CompanyBank


class TestSentRemittanceLock(TestCase):
    """Una remesa marcada com a enviada queda bloquejada."""

    def setUp(self):
        self.pending_status = PaymentRemittanceStatus.objects.create(token='lock_pending', is_default=True)
        self.processing_status = PaymentRemittanceStatus.objects.create(token='lock_processing')
        self.sent_status = PaymentRemittanceStatus.objects.create(token='lock_sent')
        for token, value in (
            ('payment_remittance_status_sent_token', 'lock_sent'),
            ('payment_remittance_status_processing_token', 'lock_processing'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})

        company = Company.objects.create(name='Empresa')
        self.company_bank = CompanyBank.objects.create(
            company=company, iban='ES0000000000000000000001', is_active=True, is_default=True)

        self.payment = Payment.objects.create(amount=10)
        self.sent = self._remittance(status=self.sent_status, sent_at=date.today())
        self.pending = self._remittance(status=self.pending_status)

        user = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'pwd')
        self.client = APIClient()
        self.client.force_authenticate(user)

    def _remittance(self, **kwargs):
        remittance = PaymentRemittance.objects.create(company_bank=self.company_bank, **kwargs)
        remittance.payments.add(self.payment)
        return remittance

    def test_is_remittance_sent(self):
        self.assertTrue(is_remittance_sent(self.sent))
        self.assertFalse(is_remittance_sent(self.pending))
        # Només l'estat, sense data d'enviament, també bloqueja
        self.assertTrue(is_remittance_sent(self._remittance(status=self.sent_status)))

    def test_no_es_pot_excloure_un_pagament(self):
        response = self.client.delete(
            f'/billing/payment-remittance/{self.sent.id}/delete-payment-relation/{self.payment.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.sent.payments.filter(id=self.payment.id).exists())

    def test_es_pot_excloure_un_pagament_si_no_s_ha_enviat(self):
        response = self.client.delete(
            f'/billing/payment-remittance/{self.pending.id}/delete-payment-relation/{self.payment.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.pending.payments.exists())

    @mock.patch('billing.tasks.regenerate_sepa_file.delay')
    def test_no_es_pot_regenerar_el_fitxer(self, delay):
        response = self.client.post(f'/billing/payment-remittance/{self.sent.id}/sepa-document-generate/', {})
        self.assertEqual(response.status_code, 400)
        delay.assert_not_called()
        self.sent.refresh_from_db()
        self.assertEqual(self.sent.status, self.sent_status)

    @mock.patch('billing.views.payment_remittance_view.send_payment_remittances.delay')
    def test_no_es_pot_tornar_a_enviar(self, delay):
        response = self.client.post(
            '/billing/payment-remittance/send/',
            {'ids': [self.sent.id, self.pending.id], 'sent_at': '2026-11-10'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['ids'], [self.sent.id])
        delay.assert_not_called()
        self.pending.refresh_from_db()
        self.assertIsNone(self.pending.sent_at)

    def test_no_es_pot_modificar_ni_esborrar(self):
        response = self.client.patch(
            f'/billing/payment-remittance/{self.sent.id}/', {'desired_send_at': '2026-12-01'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.delete(f'/billing/payment-remittance/{self.sent.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(PaymentRemittance.objects.filter(id=self.sent.id).exists())

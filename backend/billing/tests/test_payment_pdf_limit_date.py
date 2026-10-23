import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from billing.utils.payment_pdf_service import generate_report_payment_pdf


class _StopRender(Exception):
    pass


class PaymentPdfLimitDateTests(SimpleTestCase):
    """Data límit que es mostra a la carta de pagament.

    A les reclamacions d'impagats es concedeix un nou termini (limit_date): la carta
    l'ha de mostrar en lloc del venciment original del pagament, que ja ha passat.
    """

    def _render_context(self, limit_date=None):
        payment = MagicMock()
        payment.invoice = None
        payment.commitment_deposit = None
        payment.token = '12345678901'
        payment.amount = 10
        payment.due_date = datetime.date(2026, 9, 1)
        payment.payment_date = datetime.date(2026, 9, 1)
        payment.payment_bank = None
        payment.payment_type_token = 'DIRECT_DEBIT'
        payment.status = None

        exploitation = MagicMock()
        exploitation.company.logo = None

        captured = {}

        def render(template, context):
            captured.update(context)
            raise _StopRender()

        with patch('service.models.Exploitation') as exploitation_model, \
                patch('billing.utils.payment_pdf_service.CompanySerializer') as company_serializer, \
                patch('billing.utils.payment_pdf_service.ConfigProject'), \
                patch('billing.utils.payment_pdf_service.generate_barcode', return_value=None), \
                patch('billing.utils.barcode_service.get_barcode_values', return_value={}), \
                patch('billing.utils.payment_pdf_service.exploitation_logo_source', return_value=None), \
                patch('service.serializers.company_bank_serializer.CompanyBankSerializer'), \
                patch('billing.utils.payment_pdf_service.render_to_string', side_effect=render):
            exploitation_model.objects.filter.return_value.first.return_value = exploitation
            company_serializer.return_value.data = {'logo': None, 'vat': 'B12345678'}
            with self.assertRaises(Exception):
                generate_report_payment_pdf(payment, limit_date=limit_date)
        return captured

    def test_shows_granted_limit_date(self):
        limit_date = datetime.datetime(2026, 12, 20, 10, 0)
        context = self._render_context(limit_date)
        self.assertEqual(context['now_date'], limit_date)
        self.assertEqual(context['ident'], '201226')
        self.assertEqual(context['due_date'], datetime.date(2026, 9, 1))

    def test_without_limit_date_shows_payment_due_date(self):
        context = self._render_context()
        self.assertEqual(context['now_date'], datetime.date(2026, 9, 1))
        self.assertEqual(context['ident'], '010926')

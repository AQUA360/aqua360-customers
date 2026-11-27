"""
Document SEPA generat des de la sol·licitud o el contracte (ContractSepaPDFView):
per defecte surt com a «no domiciliat»; amb direct_debit és el mandat de domiciliació.
"""
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.views import contract_sepa_pdf_view as view_module
from billing.views.contract_sepa_pdf_view import ContractSepaPDFView


class ContractSepaPDFDirectDebitTests(SimpleTestCase):
    def _render_context(self, body, mandate_id=None):
        contract = MagicMock()
        contract.token = "TOKEN"
        contract.payment = MagicMock(IBAN=None, mandate_id=mandate_id)
        contract.supply_point_default = None
        contract.holder = None

        request = APIRequestFactory().post("/billing/contract/1/sepa/", body, format="json")
        force_authenticate(request, user=MagicMock(is_authenticated=True))

        sepa = MagicMock(id=7)
        sepa.template.url = "/media/sepa.pdf"
        with patch.object(view_module, "get_object_or_404", return_value=contract), \
                patch.object(view_module, "_company_from_contract", return_value={}), \
                patch.object(view_module, "render_to_string", return_value="<html></html>") as render, \
                patch.object(view_module.pisa, "CreatePDF", return_value=MagicMock(err=0)), \
                patch.object(view_module, "sign_pdf", return_value=BytesIO(b"%PDF")), \
                patch.object(view_module.GeneralPaymentSepaDocument.objects, "get_or_create",
                             return_value=(sepa, False)):
            response = ContractSepaPDFView.as_view()(request, contract_id=1)

        self.assertEqual(response.status_code, 200)
        return render.call_args[0][1]

    def test_by_default_is_no_direct_debit(self):
        context = self._render_context({}, mandate_id="M-1")
        self.assertTrue(context["no_sepa"])
        self.assertIsNone(context["mandate_reference"])

    def test_direct_debit_uses_given_mandate_id(self):
        context = self._render_context({"direct_debit": True, "mandate_id": "M-2"}, mandate_id="M-1")
        self.assertFalse(context["no_sepa"])
        self.assertEqual(context["mandate_reference"], "M-2")

    def test_direct_debit_falls_back_to_payment_mandate(self):
        context = self._render_context({"direct_debit": True}, mandate_id="M-1")
        self.assertFalse(context["no_sepa"])
        self.assertEqual(context["mandate_reference"], "M-1")

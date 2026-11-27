from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from contract.models import ContractRequest
from documentmanager.models import DocumentSign
from integrations.models import ContractSigningSession, IntegrationRequestLog
from integrations.outbound.signing.exceptions import SigningApiError

URL = "/signing/callback/"
KEY = "clau-de-prova"
SERVICES = "integrations.inbound.signing.services"

CR_SESSION = "11111111-1111-1111-1111-111111111111"
DS_SESSION = "22222222-2222-2222-2222-222222222222"
OTHER_SESSION = "33333333-3333-3333-3333-333333333333"


def signed_payload(reference, session_id, document_id=1):
    return {
        "event": "session.signed",
        "external_reference": reference,
        "session_id": session_id,
        "signed_at": "2026-11-20T10:00:00+01:00",
        "documents": [{"id": document_id, "signed": True}],
    }


@override_settings(SIGN_CALLBACK_API_KEY=KEY)
class SigningCallbackTests(TestCase):
    """Callback d'Aqua360 Sign: clau obligatòria i sessió lligada a la referència."""

    def setUp(self):
        self.client = APIClient()
        self.contract_request = ContractRequest.objects.create(token="CR-TEST")
        self.session = ContractSigningSession.objects.create(
            contract_request=self.contract_request,
            session_id=CR_SESSION,
            external_reference="CR-TEST",
            recipient_name="Prova",
            recipient_email="prova@example.com",
        )
        self.other_request = ContractRequest.objects.create(token="CR-ALTRA")
        ContractSigningSession.objects.create(
            contract_request=self.other_request,
            session_id=OTHER_SESSION,
            external_reference="CR-ALTRA",
            recipient_name="Altra",
            recipient_email="altra@example.com",
        )
        self.document_sign = DocumentSign.objects.create(
            token=DS_SESSION, status=DocumentSign.STATUS_SENDED
        )
        download = mock.patch(f"{SERVICES}.SigningClient")
        self.signing_client = download.start().return_value
        self.signing_client.download_signed_document.return_value = b"%PDF-signat"
        self.addCleanup(download.stop)
        save_contract = mock.patch(f"{SERVICES}.save_signed_contract_file")
        self.save_contract = save_contract.start()
        self.addCleanup(save_contract.stop)
        save_document = mock.patch(f"{SERVICES}.save_signed_document_sign_file")
        self.save_document = save_document.start()
        self.addCleanup(save_document.stop)

    def post(self, payload, key=KEY):
        headers = {"HTTP_X_API_KEY": key} if key is not None else {}
        return self.client.post(URL, payload, format="json", **headers)

    def assert_nothing_changed(self):
        self.session.refresh_from_db()
        self.document_sign.refresh_from_db()
        self.assertEqual(self.session.status, ContractSigningSession.STATUS_PENDING)
        self.assertEqual(self.document_sign.status, DocumentSign.STATUS_SENDED)
        self.save_contract.assert_not_called()
        self.save_document.assert_not_called()
        self.signing_client.download_signed_document.assert_not_called()

    # --- Clau ---

    @override_settings(SIGN_CALLBACK_API_KEY="")
    def test_sense_clau_configurada_ho_rebutja_tot(self):
        response = self.post(signed_payload("CR-TEST", CR_SESSION), key="")
        self.assertEqual(response.status_code, 403)
        response = self.post(signed_payload("CR-TEST", CR_SESSION), key="qualsevol")
        self.assertEqual(response.status_code, 403)
        self.assert_nothing_changed()
        log = IntegrationRequestLog.objects.filter(direction="inbound").latest("id")
        self.assertEqual(log.status_code, 403)
        self.assertFalse(log.success)

    def test_sense_capcalera_rebutjat(self):
        response = self.post(signed_payload("CR-TEST", CR_SESSION), key=None)
        self.assertEqual(response.status_code, 403)
        self.assert_nothing_changed()

    def test_clau_dolenta_rebutjada(self):
        response = self.post(signed_payload("CR-TEST", CR_SESSION), key="dolenta")
        self.assertEqual(response.status_code, 403)
        self.assert_nothing_changed()

    def test_cos_que_no_es_un_objecte(self):
        response = self.client.post(URL, ["x"], format="json", HTTP_X_API_KEY=KEY)
        self.assertEqual(response.status_code, 400)

    # --- Esdeveniments i camps obligatoris ---

    def test_session_expired_rebutjat(self):
        payload = {"event": "session.expired", "external_reference": "docsign-%s" % self.document_sign.id,
                   "session_id": DS_SESSION}
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assert_nothing_changed()

    def test_sense_session_id_rebutjat(self):
        payload = signed_payload("CR-TEST", "")
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assert_nothing_changed()

    # --- Sessió lligada a la referència ---

    def test_sollicitud_amb_sessio_d_una_altra_sollicitud(self):
        response = self.post(signed_payload("CR-TEST", OTHER_SESSION))
        self.assertEqual(response.status_code, 400)
        self.assert_nothing_changed()

    def test_sollicitud_amb_sessio_inventada(self):
        response = self.post(signed_payload("CR-TEST", "44444444-4444-4444-4444-444444444444"))
        self.assertEqual(response.status_code, 400)
        self.assert_nothing_changed()

    def test_sollicitud_per_id_numeric_amb_sessio_aliena(self):
        response = self.post(signed_payload(str(self.contract_request.id), OTHER_SESSION))
        self.assertEqual(response.status_code, 400)
        self.assert_nothing_changed()

    def test_document_amb_sessio_d_una_altra(self):
        response = self.post(signed_payload("docsign-%s" % self.document_sign.id, OTHER_SESSION))
        self.assertEqual(response.status_code, 400)
        self.assert_nothing_changed()

    def test_referencia_inexistent(self):
        response = self.post(signed_payload("NO-EXISTEIX", CR_SESSION))
        self.assertEqual(response.status_code, 404)

    def test_signat_fals_no_bloqueja_el_pdf_real(self):
        """Abans, un «signat» amb una sessió inventada marcava la sessió pendent com a
        signada i el callback real de Sign quedava descartat sense desar el PDF."""
        self.signing_client.download_signed_document.side_effect = SigningApiError("404")
        fake = self.post(signed_payload("CR-TEST", "55555555-5555-5555-5555-555555555555"))
        self.assertEqual(fake.status_code, 400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, ContractSigningSession.STATUS_PENDING)

        self.signing_client.download_signed_document.side_effect = None
        real = self.post(signed_payload("CR-TEST", CR_SESSION))
        self.assertEqual(real.status_code, 200)
        self.assertTrue(real.data["contract_file_saved"])
        self.save_contract.assert_called_once()

    # --- Casos bons ---

    def test_sollicitud_cas_bo_i_idempotent(self):
        response = self.post(signed_payload("CR-TEST", CR_SESSION))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["contract_file_saved"])
        self.signing_client.download_signed_document.assert_called_once_with(CR_SESSION, 1)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, ContractSigningSession.STATUS_SIGNED)

        again = self.post(signed_payload("CR-TEST", CR_SESSION))
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.data["already_processed"])
        self.save_contract.assert_called_once()

    def test_document_cas_bo_amb_capcalera_alternativa(self):
        response = self.client.post(
            URL,
            signed_payload("docsign-%s" % self.document_sign.id, DS_SESSION),
            format="json",
            HTTP_AQUA360_API_KEY=KEY,
        )
        self.assertEqual(response.status_code, 200)
        self.signing_client.download_signed_document.assert_called_once_with(DS_SESSION, 1)
        self.save_document.assert_called_once()

    # --- Revisió ---

    def test_identificadors_que_no_son_text(self):
        for payload in (
            {**signed_payload("CR-TEST", CR_SESSION), "external_reference": 123},
            {**signed_payload("CR-TEST", CR_SESSION), "session_id": 123},
        ):
            response = self.post(payload)
            self.assertEqual(response.status_code, 400)
        self.assert_nothing_changed()

    def test_sollicitud_sense_pdf_no_queda_signada(self):
        self.signing_client.download_signed_document.side_effect = SigningApiError("caigut")
        response = self.post(signed_payload("CR-TEST", CR_SESSION))
        self.assertEqual(response.status_code, 400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, ContractSigningSession.STATUS_PENDING)
        self.save_contract.assert_not_called()

        # El reintent (de Sign o del sondeig) sí que el desa.
        self.signing_client.download_signed_document.side_effect = None
        retry = self.post(signed_payload("CR-TEST", CR_SESSION))
        self.assertEqual(retry.status_code, 200)
        self.save_contract.assert_called_once()

    def test_document_reenviat_durant_la_descarrega(self):
        def resend_while_downloading(session_id, document_id):
            DocumentSign.objects.filter(pk=self.document_sign.pk).update(token=OTHER_SESSION)
            return b"%PDF-sessio-antiga"

        self.signing_client.download_signed_document.side_effect = resend_while_downloading
        response = self.post(signed_payload("docsign-%s" % self.document_sign.id, DS_SESSION))
        self.assertEqual(response.status_code, 400)
        self.save_document.assert_not_called()

    def test_document_amb_sepa_desa_els_dos_pdf(self):
        payload = signed_payload("docsign-%s" % self.document_sign.id, DS_SESSION)
        payload["documents"] = [
            {"id": 1, "signed": True, "external_document_id": str(self.document_sign.id)},
            {"id": 2, "signed": True, "external_document_id": "sepa-%s" % self.document_sign.id},
            {"id": 3, "signed": False, "external_document_id": "invoice-9",
             "requires_signature": False},
        ]
        self.signing_client.download_signed_document.side_effect = (
            lambda session_id, document_id: b"%PDF-" + str(document_id).encode()
        )
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [c.args for c in self.signing_client.download_signed_document.call_args_list],
            [(DS_SESSION, 1), (DS_SESSION, 2)],
        )
        args = self.save_document.call_args.args
        self.assertEqual(args[1], b"%PDF-1")
        self.assertEqual(args[3], b"%PDF-2")


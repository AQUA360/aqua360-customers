from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from contract.models import ContractRequest
from documentmanager.models import DocumentSign
from documentmanager.utils.document_sign_config import DOCUMENT_SIGN_REFERENCE_PREFIX
from documentmanager.utils.main_utils import upload_document
from integrations.models import ContractSigningSession, IntegrationRequestLog
from integrations.outbound.signing.client import SigningClient
from integrations.outbound.signing.exceptions import SigningApiError
from integrations.outbound.signing.services import save_signed_contract_file

PROVIDER = "signing"
CALLBACK_ENDPOINT = "/signing/callback/"


class SigningCallbackError(Exception):
    def __init__(self, detail, status_code=400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _parse_signed_at(value):
    if not value:
        return timezone.now()
    parsed = parse_datetime(value)
    return parsed if parsed else timezone.now()


def _resolve_contract_request(external_reference):
    ref = (external_reference or "").strip()
    if not ref:
        return None
    contract_request = ContractRequest.objects.filter(token=ref).first()
    if contract_request:
        return contract_request
    if ref.isdigit():
        return ContractRequest.objects.filter(id=int(ref)).first()
    return None


def _resolve_document_sign(external_reference):
    ref = (external_reference or "").strip()
    if not ref:
        return None
    document_sign = DocumentSign.objects.filter(token=ref).first()
    if document_sign:
        return document_sign
    if ref.startswith(DOCUMENT_SIGN_REFERENCE_PREFIX):
        suffix = ref[len(DOCUMENT_SIGN_REFERENCE_PREFIX):]
        if suffix.isdigit():
            return DocumentSign.objects.filter(id=int(suffix)).first()
        return None
    # Compatibilitat amb sessions ja enviades abans d'introduir el prefix `docsign-`,
    # que usaven l'id nu com a referència (ambigu amb ContractRequest.id).
    if ref.isdigit():
        return DocumentSign.objects.filter(id=int(ref)).first()
    return None


def save_signed_document_sign_file(document_sign, pdf_bytes, signed_at):
    filename = f"{document_sign.token or document_sign.id}_signed.pdf"
    service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
    file_obj = SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf")
    document = upload_document(
        file_obj,
        "DOCUMENT_SIGN",
        "DOCUMENT_SIGN",
        document_sign.id,
        document_sign.token or "",
        "",
        service,
        filename,
    )

    document_sign.contract_file_signed = document
    document_sign.status = DocumentSign.STATUS_SIGNED
    document_sign.signed_at = signed_at
    document_sign.error_report = None
    document_sign.save(
        update_fields=["contract_file_signed", "status", "signed_at", "error_report", "updated_at"]
    )


def _download_signed_pdf(session_id, payload):
    """
    El webhook `session.signed` només notifica l'esdeveniment; el PDF firmat
    (amb marca SES) cal descarregar-lo a part via
    GET /api/sessions/<session_id>/documents/<document_id>/signed/.
    """
    if not session_id:
        return None

    documents = payload.get("documents") or []
    signed_document = next(
        (
            document
            for document in documents
            if isinstance(document, dict) and document.get("signed") and document.get("id")
        ),
        None,
    )
    if not signed_document:
        return None

    client = SigningClient()
    try:
        return client.download_signed_document(session_id, signed_document["id"])
    except SigningApiError:
        return None


def handle_signing_callback(payload):
    event = payload.get("event")
    external_reference = (payload.get("external_reference") or "").strip()
    session_id = (payload.get("session_id") or "").strip()

    if session_id:
        existing = ContractSigningSession.objects.filter(session_id=session_id).first()
        if existing and existing.status == ContractSigningSession.STATUS_SIGNED:
            return {"ok": True, "already_processed": True}

    # Referència inequívoca de DocumentSign: es resol directament, sense passar
    # per ContractRequest (evita col·lisions quan ambdós comparteixen el mateix id numèric).
    if external_reference.startswith(DOCUMENT_SIGN_REFERENCE_PREFIX):
        document_sign = _resolve_document_sign(external_reference)
        if document_sign:
            if event == "session.expired":
                return _handle_document_sign_expired(document_sign)
            return _handle_document_sign_signed(document_sign, session_id, payload)
        raise SigningCallbackError(
            "No s'ha trobat cap document per firmar amb aquesta referència.",
            status_code=404,
        )

    contract_request = _resolve_contract_request(external_reference)
    if contract_request:
        if event == "session.expired":
            return _handle_contract_request_expired(contract_request, external_reference, session_id)
        return _handle_contract_request_signed(contract_request, external_reference, session_id, payload)

    document_sign = _resolve_document_sign(external_reference)
    if document_sign:
        if event == "session.expired":
            return _handle_document_sign_expired(document_sign)
        return _handle_document_sign_signed(document_sign, session_id, payload)

    raise SigningCallbackError(
        "No s'ha trobat cap sol·licitud de contracte ni document per firmar amb aquesta referència.",
        status_code=404,
    )


def _handle_contract_request_signed(contract_request, external_reference, session_id, payload):
    session = None
    if session_id:
        session = ContractSigningSession.objects.filter(session_id=session_id).first()
    if not session:
        session = (
            ContractSigningSession.objects.filter(
                contract_request=contract_request,
                external_reference=external_reference,
                status=ContractSigningSession.STATUS_PENDING,
            )
            .order_by("-created_at")
            .first()
        )

    signed_at = _parse_signed_at(payload.get("signed_at"))
    contract_file_saved = False

    pdf_bytes = _download_signed_pdf(session_id, payload)
    if pdf_bytes:
        save_signed_contract_file(contract_request, pdf_bytes)
        contract_file_saved = True

    if session:
        session.status = ContractSigningSession.STATUS_SIGNED
        session.signed_at = signed_at
        session.save(update_fields=["status", "signed_at", "updated_at"])

    return {
        "ok": True,
        "contract_request_id": contract_request.id,
        "contract_request_token": contract_request.token,
        "session_id": session_id or None,
        "contract_file_saved": contract_file_saved,
    }


def _handle_document_sign_signed(document_sign, session_id, payload):
    signed_at = _parse_signed_at(payload.get("signed_at"))
    pdf_bytes = _download_signed_pdf(session_id, payload)

    if not pdf_bytes:
        raise SigningCallbackError(
            "No s'ha pogut descarregar el document firmat des d'Aqua360 Sign.",
            status_code=400,
        )

    save_signed_document_sign_file(document_sign, pdf_bytes, signed_at)

    return {
        "ok": True,
        "document_sign_id": document_sign.id,
        "document_sign_token": document_sign.token,
        "contract_file_saved": True,
    }


def _handle_contract_request_expired(contract_request, external_reference, session_id):
    session = None
    if session_id:
        session = ContractSigningSession.objects.filter(session_id=session_id).first()
    if not session:
        session = (
            ContractSigningSession.objects.filter(
                contract_request=contract_request,
                external_reference=external_reference,
                status=ContractSigningSession.STATUS_PENDING,
            )
            .order_by("-created_at")
            .first()
        )

    if session and session.status != ContractSigningSession.STATUS_SIGNED:
        session.status = ContractSigningSession.STATUS_EXPIRED
        session.save(update_fields=["status", "updated_at"])

    return {
        "ok": True,
        "contract_request_id": contract_request.id,
        "contract_request_token": contract_request.token,
        "session_id": session_id or None,
        "status": ContractSigningSession.STATUS_EXPIRED,
    }


def _handle_document_sign_expired(document_sign):
    if document_sign.status != DocumentSign.STATUS_SIGNED:
        document_sign.status = DocumentSign.STATUS_EXPIRED
        document_sign.error_report = None
        document_sign.save(update_fields=["status", "error_report", "updated_at"])

    return {
        "ok": True,
        "document_sign_id": document_sign.id,
        "document_sign_token": document_sign.token,
        "status": DocumentSign.STATUS_EXPIRED,
    }


def log_signing_callback(
    payload, *, success, status_code, error_message="", response_payload=None
):
    IntegrationRequestLog.objects.create(
        provider=PROVIDER,
        direction=IntegrationRequestLog.DIRECTION_INBOUND,
        method="POST",
        endpoint=CALLBACK_ENDPOINT,
        request_payload=payload,
        response_payload=response_payload or {"success": success},
        status_code=status_code,
        success=success,
        error_message=error_message,
        object_type="contract_request_signing_session",
        object_id=str(payload.get("session_id") or payload.get("external_reference") or ""),
    )

from django.conf import settings
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from contract.models import ContractRequest
from documentmanager.models import DocumentSign
from documentmanager.utils.document_sign_config import (
    DOCUMENT_SIGN_REFERENCE_PREFIX,
    DOCUMENT_SIGN_SEPA_ID_PREFIX,
)
from documentmanager.utils.main_utils import upload_document
from integrations.models import ContractSigningSession, IntegrationRequestLog
from integrations.outbound.signing.client import SigningClient
from integrations.outbound.signing.exceptions import SigningApiError
from integrations.outbound.signing.services import save_signed_contract_file

PROVIDER = "signing"
CALLBACK_ENDPOINT = "/signing/callback/"
EVENT_SIGNED = "session.signed"
SESSION_MISMATCH = "La sessió no correspon a aquesta referència."


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


def _upload_signed_pdf(document_sign, pdf_bytes, field, filename):
    service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
    file_obj = SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf")
    return upload_document(
        file_obj,
        "DOCUMENT_SIGN",
        field,
        document_sign.id,
        document_sign.token or "",
        "",
        service,
        filename,
    )


def save_signed_document_sign_file(document_sign, pdf_bytes, signed_at, sepa_pdf_bytes=None):
    name = document_sign.token or document_sign.id
    document_sign.contract_file_signed = _upload_signed_pdf(
        document_sign, pdf_bytes, "DOCUMENT_SIGN", f"{name}_signed.pdf"
    )
    if sepa_pdf_bytes:
        document_sign.sepa_file_signed = _upload_signed_pdf(
            document_sign, sepa_pdf_bytes, "SEPA", f"{name}_SEPA_signed.pdf"
        )
    document_sign.status = DocumentSign.STATUS_SIGNED
    document_sign.signed_at = signed_at
    document_sign.error_report = None
    document_sign.save(
        update_fields=[
            "contract_file_signed", "sepa_file_signed", "status", "signed_at",
            "error_report", "updated_at",
        ]
    )


def signed_document_sign_ids(documents):
    """
    Ids remots dels documents signats d'una sessió de DocumentSign:
    (contracte, SEPA). El SEPA es reconeix pel prefix de l'`external_document_id`;
    el contracte és el primer altre document signat (els adjunts no se signen).
    """
    contract_id = None
    sepa_id = None
    for document in documents or []:
        if not (isinstance(document, dict) and document.get("signed") and document.get("id")):
            continue
        external_id = str(document.get("external_document_id") or "")
        if external_id.startswith(DOCUMENT_SIGN_SEPA_ID_PREFIX):
            sepa_id = sepa_id or document["id"]
        elif contract_id is None:
            contract_id = document["id"]
    return contract_id, sepa_id


def download_signed_document_sign_files(client, session_id, documents, **log_kwargs):
    """
    Baixa el contracte i, si n'hi ha, el SEPA signats. Retorna (contracte, sepa)
    o (None, None) si no hi ha contracte signat. Aixeca SigningApiError si falla.
    """
    contract_id, sepa_id = signed_document_sign_ids(documents)
    if not contract_id:
        return None, None
    contract_bytes = client.download_signed_document(session_id, contract_id, **log_kwargs)
    sepa_bytes = (
        client.download_signed_document(session_id, sepa_id, **log_kwargs) if sepa_id else None
    )
    return contract_bytes, sepa_bytes


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
    """
    Processa un `session.signed` d'Aqua360 Sign. El `session_id` ha de ser una sessió
    que hem creat nosaltres per a la referència que arriba: no es busca cap sessió
    de reserva, perquè un avís amb una sessió aliena no pugui marcar res com a signat
    ni penjar-hi el PDF d'una altra sessió.
    """
    if payload.get("event") != EVENT_SIGNED:
        raise SigningCallbackError("Esdeveniment no suportat.", status_code=400)

    external_reference = (payload.get("external_reference") or "").strip()
    session_id = (payload.get("session_id") or "").strip()
    if not external_reference or not session_id:
        raise SigningCallbackError(
            "external_reference i session_id són obligatoris.", status_code=400
        )

    # Referència inequívoca de DocumentSign: es resol directament, sense passar
    # per ContractRequest (evita col·lisions quan ambdós comparteixen el mateix id numèric).
    if external_reference.startswith(DOCUMENT_SIGN_REFERENCE_PREFIX):
        document_sign = _resolve_document_sign(external_reference)
        if not document_sign:
            raise SigningCallbackError(
                "No s'ha trobat cap document per firmar amb aquesta referència.",
                status_code=404,
            )
        _check_document_sign_session(document_sign, session_id)
        return _handle_document_sign_signed(document_sign, session_id, payload)

    contract_request = _resolve_contract_request(external_reference)
    if contract_request:
        session = ContractSigningSession.objects.filter(
            contract_request=contract_request, session_id=session_id
        ).first()
        if session:
            return _handle_contract_request_signed(contract_request, session, payload)

    # Compatibilitat amb sessions de DocumentSign enviades abans del prefix `docsign-`.
    document_sign = _resolve_document_sign(external_reference)
    if document_sign and document_sign.token == session_id:
        return _handle_document_sign_signed(document_sign, session_id, payload)

    if contract_request or document_sign:
        raise SigningCallbackError(SESSION_MISMATCH, status_code=400)
    raise SigningCallbackError(
        "No s'ha trobat cap sol·licitud de contracte ni document per firmar amb aquesta referència.",
        status_code=404,
    )


def _check_document_sign_session(document_sign, session_id):
    # `token` guarda l'id de la sessió remota creada per l'últim enviament.
    if not document_sign.token or document_sign.token != session_id:
        raise SigningCallbackError(SESSION_MISMATCH, status_code=400)


def _handle_contract_request_signed(contract_request, session, payload):
    if session.status == ContractSigningSession.STATUS_SIGNED:
        return {"ok": True, "already_processed": True}

    signed_at = _parse_signed_at(payload.get("signed_at"))

    # Sense PDF no es marca com a signada: així Sign (o el sondeig, que mira les
    # sessions pendents) ho pot tornar a intentar.
    pdf_bytes = _download_signed_pdf(session.session_id, payload)
    if not pdf_bytes:
        raise SigningCallbackError(
            "No s'ha pogut descarregar el contracte firmat des d'Aqua360 Sign.",
            status_code=400,
        )
    save_signed_contract_file(contract_request, pdf_bytes)

    session.status = ContractSigningSession.STATUS_SIGNED
    session.signed_at = signed_at
    session.save(update_fields=["status", "signed_at", "updated_at"])

    return {
        "ok": True,
        "contract_request_id": contract_request.id,
        "contract_request_token": contract_request.token,
        "session_id": session.session_id,
        "contract_file_saved": True,
    }


def _handle_document_sign_signed(document_sign, session_id, payload):
    if document_sign.status == DocumentSign.STATUS_SIGNED and document_sign.contract_file_signed_id:
        return {"ok": True, "already_processed": True}

    signed_at = _parse_signed_at(payload.get("signed_at"))
    try:
        pdf_bytes, sepa_pdf_bytes = download_signed_document_sign_files(
            SigningClient(), session_id, payload.get("documents")
        )
    except SigningApiError:
        pdf_bytes = sepa_pdf_bytes = None

    if not pdf_bytes:
        raise SigningCallbackError(
            "No s'ha pogut descarregar el document firmat des d'Aqua360 Sign.",
            status_code=400,
        )

    # Mentre es baixava el PDF el document es pot haver tornat a enviar (token nou):
    # es revalida la sessió amb la fila bloquejada abans de desar-lo.
    with transaction.atomic():
        document_sign = DocumentSign.objects.select_for_update().get(pk=document_sign.pk)
        _check_document_sign_session(document_sign, session_id)
        save_signed_document_sign_file(document_sign, pdf_bytes, signed_at, sepa_pdf_bytes)

    return {
        "ok": True,
        "document_sign_id": document_sign.id,
        "document_sign_token": document_sign.token,
        "contract_file_saved": True,
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

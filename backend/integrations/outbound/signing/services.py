import base64

import requests
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.dateparse import parse_datetime

from contract.models import Contract, ContractRequest
from contract.utils.contract_pdf_service import (
    ContractPdfGenerationError,
    generate_contract_pdf_bytes,
    get_contract_pdf_filename,
)
from documentmanager.models import DocumentSign
from documentmanager.utils.document_sign_config import (
    DOCUMENT_SIGN_REFERENCE_PREFIX,
    is_document_sign_enabled,
)
from documentmanager.utils.main_utils import download_document, upload_document

from integrations.models import ContractSigningSession

from .client import SigningClient
from .exceptions import SigningApiError


def _resolve_recipient(
    contract_request, recipient_name=None, recipient_email=None, recipient_phone=None
):
    holder = contract_request.holder
    name = recipient_name
    email = recipient_email
    phone = recipient_phone

    if not name and holder:
        name = f"{holder.name or ''} {holder.surname or ''}".strip()

    contact = contract_request.person_contact_email
    if not contact and holder:
        contact = (
            holder.contacts.filter(is_active=True, is_default=True).first()
            or holder.contacts.filter(is_active=True)
            .exclude(email__isnull=True)
            .exclude(email="")
            .first()
        )

    if not email and contact:
        email = contact.email
    if not phone and contact:
        phone = contact.phone

    if not name:
        raise SigningApiError("Falta el nom del signant")
    if not email:
        raise SigningApiError("Falta el correu del signant")

    return name, email, phone


def _resolve_callback_url(callback_url=None):
    if callback_url:
        return callback_url
    default_url = getattr(settings, "SIGNING_CALLBACK_URL", "")
    if default_url:
        return default_url
    raise SigningApiError("Falta la URL de callback per a la signatura")


def create_contract_request_signing_session(
    contract_request,
    *,
    recipient_name=None,
    recipient_email=None,
    recipient_phone=None,
    callback_url=None,
    force=False,
):
    if not is_document_sign_enabled():
        raise SigningApiError("La signatura de documents (DocumentSign) no està habilitada")

    if contract_request.contract_file and not force:
        raise SigningApiError(
            "La sol·licitud ja té contract_file (document signat). "
            "Utilitza force=True per tornar a enviar-la a signar."
        )

    if not settings.SIGNING_BASE_URL:
        raise SigningApiError("SIGNING_BASE_URL no està configurat")
    if not settings.SIGNING_API_KEY:
        raise SigningApiError("SIGNING_API_KEY no està configurat")

    try:
        pdf_bytes = generate_contract_pdf_bytes(
            contract_request,
            include_requested_at=True,
        )
    except ContractPdfGenerationError as exc:
        raise SigningApiError(f"No s'ha pogut generar el PDF del contracte: {exc}") from exc

    filename = get_contract_pdf_filename(contract_request)

    name, email, phone = _resolve_recipient(
        contract_request,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
    )
    resolved_callback_url = _resolve_callback_url(callback_url)
    external_reference = (contract_request.token or "").strip() or str(contract_request.id)

    client = SigningClient()
    response = client.create_session(
        recipient_name=name,
        recipient_email=email,
        recipient_phone=phone,
        external_reference=external_reference,
        callback_url=resolved_callback_url,
        documents=[(filename, pdf_bytes, "application/pdf")],
        document_metadata=[
            {
                "title": f"Contracte {contract_request.token}",
                "external_document_id": str(contract_request.id),
                "sort_order": 0,
            }
        ],
        object_type="contract_request",
        object_id=str(contract_request.id),
    )

    session = ContractSigningSession.objects.create(
        contract_request=contract_request,
        session_id=response["id"],
        external_reference=external_reference,
        status=response.get("status", ContractSigningSession.STATUS_PENDING),
        signing_url=response.get("signing_url", ""),
        recipient_name=name,
        recipient_email=email,
        recipient_phone=phone or "",
        callback_url=resolved_callback_url,
        email_sent=response.get("email_sent", False),
        expires_at=parse_datetime(response["expires_at"])
        if response.get("expires_at")
        else None,
    )

    return {
        "session_id": session.session_id,
        "contract_request_id": contract_request.id,
        "contract_request_token": contract_request.token,
        "status": session.status,
        "signing_url": session.signing_url,
        "expires_at": session.expires_at,
        "email_sent": session.email_sent,
    }


def save_signed_contract_file(contract_request, pdf_bytes):
    filename = get_contract_pdf_filename(contract_request).replace(".pdf", "_signed.pdf")
    service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
    file_obj = SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf")
    document = upload_document(
        file_obj,
        "CONTRACT",
        "CONTRACT",
        contract_request.id,
        contract_request.token,
        "",
        service,
        filename,
        contract_request.created_at,
    )
    contract_request.contract_file = document
    contract_request.save(update_fields=["contract_file"])

    contract = Contract.objects.filter(contract_request=contract_request).first()
    if contract:
        contract.contract_file = document
        contract.save(update_fields=["contract_file"])

    return document


def _ensure_document_sign_contract_file(document_sign):
    """
    Si el DocumentSign encara no té `contract_file`, genera ara el PDF del contracte
    (a partir de `contract` o, si encara no existeix, de `contract_request`), el desa
    com a `Document` i el vincula al DocumentSign, per no dependre de que front l'hagi
    generat prèviament (p. ex. via `contract/download/<id>/?is_contract=false`).
    """
    if document_sign.contract_file:
        return document_sign.contract_file

    pdf_source = document_sign.contract or document_sign.contract_request
    if not pdf_source:
        raise SigningApiError(
            "El DocumentSign no té contract_file ni contract/contract_request per generar-lo"
        )

    # Si el contracte/sol·licitud ja té el PDF generat (p. ex. via
    # `contract/download/<id>/?is_contract=false`), el reutilitzem en lloc de regenerar-lo.
    if pdf_source.contract_file:
        document = pdf_source.contract_file
    else:
        try:
            pdf_bytes = generate_contract_pdf_bytes(
                pdf_source, include_requested_at=isinstance(pdf_source, ContractRequest)
            )
        except ContractPdfGenerationError as exc:
            raise SigningApiError(f"No s'ha pogut generar el PDF del contracte: {exc}") from exc

        filename = get_contract_pdf_filename(pdf_source)
        service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
        file_obj = SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf")
        document = upload_document(
            file_obj,
            "CONTRACT",
            "CONTRACT",
            pdf_source.id,
            pdf_source.token or "",
            "",
            service,
            filename,
        )
        pdf_source.contract_file = document
        pdf_source.save(update_fields=["contract_file"])

    document_sign.contract_file = document
    document_sign.save(update_fields=["contract_file", "updated_at"])
    return document


def create_document_sign_session(document_sign, *, callback_url=None, force=False):
    """
    Envia el `contract_file` d'un DocumentSign a Aqua360 Sign per a la firma OTP.
    Si encara no existeix, el genera ara mateix a partir del contracte/sol·licitud.
    """
    if not is_document_sign_enabled():
        raise SigningApiError("La signatura de documents (DocumentSign) no està habilitada")

    if document_sign.status == DocumentSign.STATUS_SIGNED and not force:
        raise SigningApiError(
            "El document ja està firmat. Utilitza force=True per tornar-lo a enviar."
        )

    _ensure_document_sign_contract_file(document_sign)

    if not settings.SIGNING_BASE_URL:
        raise SigningApiError("SIGNING_BASE_URL no està configurat")
    if not settings.SIGNING_API_KEY:
        raise SigningApiError("SIGNING_API_KEY no està configurat")

    if not document_sign.otp_name:
        raise SigningApiError("Falta el nom del signant (otp_name)")
    if not document_sign.otp_email:
        raise SigningApiError("Falta el correu del signant (otp_email)")

    resolved_callback_url = _resolve_callback_url(callback_url)
    # `external_reference` ha de ser sempre estable (basat en l'id del DocumentSign),
    # NO l'últim `document_sign.token` (que és l'id de sessió remot d'Aqua360, i canvia
    # a cada reenviament), o el callback deixaria de poder resoldre el DocumentSign.
    # Es prefixa per evitar col·lisions amb l'id numèric d'altres entitats
    # (p. ex. ContractRequest) que també poden usar el mateix id com a referència.
    external_reference = f"{DOCUMENT_SIGN_REFERENCE_PREFIX}{document_sign.id}"

    document_content = download_document(document_sign.contract_file)
    if not document_content:
        raise SigningApiError(
            f"No s'ha pogut descarregar el contract_file (id={document_sign.contract_file.id})"
        )
    try:
        document_bytes = document_content.getvalue()
    except AttributeError:
        document_bytes = document_content.content
    filename = document_sign.contract_file.document_name

    client = SigningClient()

    try:
        response = client.create_session(
            recipient_name=document_sign.otp_name,
            recipient_email=document_sign.otp_email,
            recipient_phone=document_sign.otp_phone,
            external_reference=external_reference,
            callback_url=resolved_callback_url,
            documents=[(filename, document_bytes, "application/pdf")],
            document_metadata=[
                {
                    "title": filename,
                    "external_document_id": str(document_sign.id),
                    "sort_order": 0,
                }
            ],
            object_type="document_sign",
            object_id=str(document_sign.id),
        )
    except SigningApiError as exc:
        document_sign.status = DocumentSign.STATUS_ERROR
        document_sign.error_report = (str(exc) or "")[:255] or None
        document_sign.save(update_fields=["status", "error_report", "updated_at"])
        raise

    document_sign.token = response.get("id") or external_reference
    document_sign.status = DocumentSign.STATUS_SENDED
    document_sign.error_report = None
    # Un reenviament encara no té PDF firmat: el d'una sessió anterior deixa de ser descarregable.
    document_sign.contract_file_signed = None
    document_sign.signed_at = None
    document_sign.save(update_fields=[
        "token", "status", "error_report", "contract_file_signed", "signed_at", "updated_at",
    ])

    return {
        "document_sign_id": document_sign.id,
        "token": document_sign.token,
        "status": document_sign.status,
        "signing_url": response.get("signing_url", ""),
        "email_sent": response.get("email_sent", False),
    }

"""
Sondeig de l'estat de les sessions d'Aqua360 Sign.

El camí normal perquè un document firmat torni a l'aplicació és el webhook
`session.signed` (`integrations/inbound/signing/`). Això obliga a que el backend
sigui accessible des d'Internet, cosa que no passa a les instal·lacions que viuen
darrere d'una IP privada, i a més un POST perdut és definitiu: no hi ha reintents.

Aquest mòdul tanca el cicle en sentit contrari, només amb trànsit de sortida:
per a cada sessió encara oberta consulta `GET /api/sessions/<id>/` i, si Sign la
dóna per firmada, es baixa el PDF segellat i el desa amb les mateixes funcions que
fa servir el callback, de manera que el resultat és idèntic pels dos camins.

Els dos camins conviuen: el que ja està firmat no es torna a processar.
"""

from django.conf import settings

from documentmanager.models import DocumentSign
from documentmanager.utils.document_sign_config import (
    DOCUMENT_SIGN_REFERENCE_PREFIX,
    is_document_sign_enabled,
)
from integrations.inbound.signing.services import (
    _parse_signed_at,
    save_signed_document_sign_file,
)
from integrations.models import ContractSigningSession
from integrations.outbound.signing.client import SigningClient
from integrations.outbound.signing.exceptions import SigningApiError
from integrations.outbound.signing.services import save_signed_contract_file

REMOTE_STATUS_SIGNED = "signed"
REMOTE_STATUS_EXPIRED = "expired"


def settings_ready():
    return bool(settings.SIGNING_BASE_URL and settings.SIGNING_API_KEY)


def _signed_document_id(session_data):
    """
    Retorna l'id del document firmat d'una sessió, o None si encara no n'hi ha cap.
    Mateix criteri que `_download_signed_pdf` del callback.
    """
    for document in session_data.get("documents") or []:
        if isinstance(document, dict) and document.get("signed") and document.get("id"):
            return document["id"]
    return None


def _remote_session_id(document_sign):
    """
    `DocumentSign.token` guarda l'id de sessió remot, però `create_document_sign_session`
    hi deixa l'`external_reference` (`docsign-<id>`) si Sign no ha retornat cap id.
    En aquest cas no hi ha res a consultar.
    """
    token = (document_sign.token or "").strip()
    if not token or token.startswith(DOCUMENT_SIGN_REFERENCE_PREFIX):
        return None
    return token


def _mark_document_sign_error(document_sign, detail):
    document_sign.status = DocumentSign.STATUS_ERROR
    document_sign.error_report = ((detail or "")[:255] or None)
    document_sign.save(update_fields=["status", "error_report", "updated_at"])


def _remote_failure(document_sign, detail, fail_on_error):
    """
    El sondeig periòdic empassa l'error per no aturar la resta del lot.
    La consulta que dispara l'usuari (`fail_on_error`) deixa el registre en Error.
    """
    if fail_on_error:
        _mark_document_sign_error(document_sign, detail)
        raise SigningApiError(detail)
    return {"document_sign_id": document_sign.id, "action": "error", "detail": detail}


def poll_document_sign(document_sign, client=None, dry_run=False, fail_on_error=False, log_success=False):
    """
    Consulta una sessió de `DocumentSign` i, si està firmada, en desa el PDF segellat.
    Per defecte no propaga els errors d'Aqua360 perquè una sessió que falla no aturi
    la resta del lot. Amb `fail_on_error=True` (el botó de sol·licitar) els propaga
    i marca el registre com a Error.
    """
    session_id = _remote_session_id(document_sign)
    if not session_id:
        detail = "El DocumentSign no té id de sessió remot."
        if fail_on_error:
            return _remote_failure(document_sign, detail, fail_on_error=True)
        return {"document_sign_id": document_sign.id, "action": "skipped", "detail": detail}

    client = client or SigningClient()
    try:
        session_data = client.get_session(
            session_id,
            object_type="document_sign",
            object_id=str(document_sign.id),
            log_success=log_success,
        )
    except SigningApiError as exc:
        return _remote_failure(document_sign, str(exc), fail_on_error)

    remote_status = (session_data.get("status") or "").lower()

    if remote_status == REMOTE_STATUS_EXPIRED:
        if not dry_run and document_sign.status != DocumentSign.STATUS_SIGNED:
            document_sign.status = DocumentSign.STATUS_EXPIRED
            document_sign.error_report = None
            document_sign.save(update_fields=["status", "error_report", "updated_at"])
        return {"document_sign_id": document_sign.id, "action": "expired"}

    if remote_status != REMOTE_STATUS_SIGNED:
        return {"document_sign_id": document_sign.id, "action": "pending",
                "detail": remote_status}

    document_id = _signed_document_id(session_data)
    if not document_id:
        return _remote_failure(
            document_sign,
            "La sessió consta com a firmada però cap document té signed=true.",
            fail_on_error,
        )

    if dry_run:
        return {"document_sign_id": document_sign.id, "action": "would_sign",
                "session_id": session_id, "document_id": document_id}

    try:
        pdf_bytes = client.download_signed_document(
            session_id, document_id,
            object_type="document_sign", object_id=str(document_sign.id),
        )
    except SigningApiError as exc:
        return _remote_failure(document_sign, str(exc), fail_on_error)

    save_signed_document_sign_file(
        document_sign, pdf_bytes, _parse_signed_at(session_data.get("signed_at"))
    )
    return {"document_sign_id": document_sign.id, "action": "signed",
            "session_id": session_id, "document_id": document_id}


def retrieve_signed_document(document_sign, client=None):
    """
    Consulta Aqua360 per al botó «Sol·licitar document signat».
    No descarrega res si encara no està firmat. Si Aqua360 falla, marca Error.
    """
    return poll_document_sign(
        document_sign,
        client=client,
        dry_run=False,
        fail_on_error=True,
        log_success=True,
    )


def poll_contract_signing_session(session, client=None, dry_run=False):
    """
    Igual que `poll_document_sign`, per a les sessions del flux de `ContractRequest`.
    """
    client = client or SigningClient()
    try:
        session_data = client.get_session(
            session.session_id,
            object_type="contract_request",
            object_id=str(session.contract_request_id),
        )
    except SigningApiError as exc:
        return {"session_id": session.session_id, "action": "error", "detail": str(exc)}

    remote_status = (session_data.get("status") or "").lower()

    if remote_status == REMOTE_STATUS_EXPIRED:
        if not dry_run and session.status != ContractSigningSession.STATUS_SIGNED:
            session.status = ContractSigningSession.STATUS_EXPIRED
            session.save(update_fields=["status", "updated_at"])
        return {"session_id": session.session_id, "action": "expired"}

    if remote_status != REMOTE_STATUS_SIGNED:
        return {"session_id": session.session_id, "action": "pending", "detail": remote_status}

    document_id = _signed_document_id(session_data)
    if not document_id:
        return {"session_id": session.session_id, "action": "error",
                "detail": "La sessió consta com a firmada però cap document té signed=true."}

    if dry_run:
        return {"session_id": session.session_id, "action": "would_sign",
                "document_id": document_id}

    try:
        pdf_bytes = client.download_signed_document(
            session.session_id, document_id,
            object_type="contract_request", object_id=str(session.contract_request_id),
        )
    except SigningApiError as exc:
        return {"session_id": session.session_id, "action": "error", "detail": str(exc)}

    save_signed_contract_file(session.contract_request, pdf_bytes)
    session.status = ContractSigningSession.STATUS_SIGNED
    session.signed_at = _parse_signed_at(session_data.get("signed_at"))
    session.save(update_fields=["status", "signed_at", "updated_at"])
    return {"session_id": session.session_id, "action": "signed", "document_id": document_id}


def poll_signing_sessions(
    *, document_sign_ids=None, session_ids=None, dry_run=False, limit=None,
    include_contract_requests=True,
):
    """
    Recorre les sessions encara obertes (`DocumentSign` en estat SENDED i
    `ContractSigningSession` en estat pending) i les posa al dia contra Aqua360.

    Amb `document_sign_ids` o `session_ids` es limita a aquests, ignorant l'estat
    local, per poder recuperar a mà un cas concret.
    """
    if not is_document_sign_enabled():
        return {"status": "skipped",
                "message": "La signatura de documents (DocumentSign) no està habilitada"}

    if not settings_ready():
        return {"status": "skipped",
                "message": "SIGNING_BASE_URL o SIGNING_API_KEY no estan configurats"}

    client = SigningClient()
    results = []

    document_signs = DocumentSign.objects.all().order_by("id")
    if document_sign_ids:
        document_signs = document_signs.filter(id__in=document_sign_ids)
    else:
        document_signs = document_signs.filter(status=DocumentSign.STATUS_SENDED)
    if limit:
        document_signs = document_signs[:limit]

    for document_sign in document_signs:
        results.append(poll_document_sign(document_sign, client=client, dry_run=dry_run))

    if include_contract_requests:
        sessions = ContractSigningSession.objects.all().order_by("id")
        if session_ids:
            sessions = sessions.filter(session_id__in=session_ids)
        else:
            sessions = sessions.filter(status=ContractSigningSession.STATUS_PENDING)
        if limit:
            sessions = sessions[:limit]

        for session in sessions:
            results.append(
                poll_contract_signing_session(session, client=client, dry_run=dry_run)
            )

    summary = {}
    for result in results:
        summary[result["action"]] = summary.get(result["action"], 0) + 1

    return {"status": "success", "dry_run": dry_run, "summary": summary, "results": results}


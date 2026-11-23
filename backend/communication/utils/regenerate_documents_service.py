"""Regeneració dels documents de les comunicacions (carta i factures).

Els documents nous s'afegeixen a la comunicació i els antics queden com a
històric: el CommunicationFile antic es desactiva (`is_active=False`), de manera
que ja no s'envia ni es descarrega, però el Document del gestor documental es
conserva. El Document no es pot desactivar perquè el PDF d'una factura és el
mateix document de la factura.
"""
import logging

from django.db.models import Q

from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from communication.models import CANCELLED_STATUS_TOKEN, Communication, CommunicationFile

logger = logging.getLogger(__name__)

INVOICE_PDF_ENTITY = 'FACTURES'
INVOICE_PDF_FIELD = 'FACTURA'
# Mateix token fix que fa servir la devolució de cartes (communication_view)
RETURNED_STATUS_TOKEN = '-3'


def _pending_filter():
    """Comunicacions que s'han de tornar a enviar: pendents sense enviar, rebutjades i
    retornades. Les rebutjades i retornades poden tenir data d'enviament (ja es van
    enviar un cop), per això la condició `sent_at` només s'aplica a les pendents."""
    rejected_token = ConfigProject.objects.filter(
        token='communication_status_rejected_token'
    ).values_list('value', flat=True).first()
    resend_tokens = [token for token in (rejected_token, RETURNED_STATUS_TOKEN) if token]
    return Q(status__is_default=True, sent_at__isnull=True) | Q(status__token__in=resend_tokens)


def communications_to_regenerate(process, only_pending):
    """Comunicacions d'un procés a regenerar: totes (menys les cancel·lades) o només les
    pendents d'enviar (pendents, rebutjades i retornades)."""
    communications = Communication.objects.filter(process=process, is_active=True).exclude(
        status__token=CANCELLED_STATUS_TOKEN
    )
    if only_pending:
        communications = communications.filter(_pending_filter())
    return list(communications.order_by('id').values_list('id', flat=True))


def _invoice_of(comm_file):
    if comm_file.invoice_id:
        return comm_file.invoice
    from billing.models import Invoice
    return Invoice.objects.filter(id=comm_file.file.entity_id).first()


def _regenerate_invoice_files(communication, regenerated_invoices):
    """Regenera el PDF de cada factura vinculada i el torna a vincular.

    `regenerated_invoices` (id factura -> Document) evita regenerar dues vegades la
    mateixa factura quan surt a més d'una comunicació.
    """
    from billing.views.invoice_pdf_view import generate_report_invoice_pdf

    old_files = communication.files.filter(
        is_active=True, file__entity=INVOICE_PDF_ENTITY, file__field=INVOICE_PDF_FIELD,
    ).select_related('file', 'invoice')
    count = 0
    for old_file in old_files:
        invoice = _invoice_of(old_file)
        if not invoice:
            continue
        if invoice.id not in regenerated_invoices:
            # El fitxer antic encara és actiu: generate_report_invoice_pdf el conserva
            generate_report_invoice_pdf(invoice)
            regenerated_invoices[invoice.id] = invoice.invoice_file
        new_document = regenerated_invoices[invoice.id]
        if not new_document or new_document.id == old_file.file_id:
            continue
        CommunicationFile.objects.create(
            token=generate_token(CommunicationFile),
            communication=communication,
            invoice=old_file.invoice,
            file=new_document,
            is_letter=False,
            attach_to_email=old_file.attach_to_email,
            attach_to_letter=old_file.attach_to_letter,
        )
        old_file.is_active = False
        old_file.save(update_fields=['is_active', 'updated_at'])
        count += 1
    return count


def _regenerate_letter(communication):
    """Torna a renderitzar la carta si la comunicació en tenia. True si s'ha regenerat."""
    from communication.utils.communication_service import get_communication_file

    letters = communication.files.filter(is_letter=True).order_by('-id')
    previous = letters.first()
    if not previous:
        return False
    new_letter = CommunicationFile.objects.create(
        token=generate_token(CommunicationFile),
        communication=communication,
        file=None,
        is_letter=True,
        attach_to_email=previous.attach_to_email,
        attach_to_letter=previous.attach_to_letter,
    )
    try:
        document = get_communication_file(new_letter.id)
    except Exception:
        new_letter.delete()
        raise
    if not document:
        new_letter.delete()
        raise ValueError("No s'ha pogut generar la carta")
    new_letter.file = document
    new_letter.save(update_fields=['file', 'updated_at'])
    letters.filter(is_active=True).exclude(id=new_letter.id).update(is_active=False)
    return True


def regenerate_communication_documents(communication_ids, on_progress=None):
    """Regenera les factures i la carta de cada comunicació.

    Primer les factures: el cos de la carta pot fer referència a les seves dades.
    Un error en una comunicació no atura les altres; els seus documents antics
    queden actius.
    """
    communications = Communication.objects.filter(id__in=communication_ids, is_active=True).order_by('id')
    total = communications.count()
    regenerated_invoices = {}
    summary = {'total': total, 'letters': 0, 'invoices': 0, 'errors': []}
    for index, communication in enumerate(communications, start=1):
        try:
            summary['invoices'] += _regenerate_invoice_files(communication, regenerated_invoices)
            if _regenerate_letter(communication):
                summary['letters'] += 1
        except Exception as e:
            logger.exception("Error regenerant els documents de la comunicació %s", communication.id)
            summary['errors'].append({'communication': communication.token or communication.id, 'error': str(e)})
        if on_progress:
            on_progress(index, total)
    return summary

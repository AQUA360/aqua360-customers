from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView, Response

from communication.models import (
    Communication,
    CommunicationFile,
    CommunicationStatus,
    Message,
    MessageType,
    MessageTypeTemplate,
)
from communication.utils.communication_service import create_email_template, send_electronic_mail
from contract.models import Contract
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from service.models import Company, CompanyConfig

from ..models import Invoice
import logging

logger = logging.getLogger(__name__)


def _invoice_contract(invoice):
    return (
        invoice.contract
        or invoice.contract_request
        or (invoice.contract_termination.contract if invoice.contract_termination else None)
    )


class InvoiceSendGroupedEmailView(APIView):
    """Envia diverses factures al mateix destinatari en UN sol correu.

    URL: POST /invoice/send-grouped-email/
    Body:
        - invoice_ids (obligatori): llista d'ids de factura.
        - email (obligatori): adreça/es del destinatari (separades per ';').
        - company_config_id (opcional): CompanyConfig (remitent). Si no s'indica,
          es dedueix de la primera factura.
        - subject (opcional): assumpte del correu.
        - body (opcional): cos del missatge.

    Crea UNA Communication enllaçada a totes les factures, hi adjunta el PDF
    (invoice_file) de cada una i l'envia amb send_electronic_mail, que adjunta
    tots els CommunicationFile de la comunicació.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # 1. Validar el destinatari
        raw_email = request.data.get('email') or ''
        if not isinstance(raw_email, str):
            return Response(
                {"error": "El camp 'email' ha de ser un text."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw_email = raw_email.strip()
        if not raw_email:
            return Response(
                {"error": "El camp 'email' és obligatori."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        emails = [e.strip() for e in raw_email.split(';') if e.strip()]
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                return Response(
                    {"error": f"Adreça d'email no vàlida: {email}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 2. Validar les factures (sense duplicats, mantenint l'ordre rebut)
        raw_ids = request.data.get('invoice_ids')
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {"error": "El camp 'invoice_ids' és obligatori i ha de ser una llista."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            invoice_ids = list(dict.fromkeys(int(i) for i in raw_ids))
        except (TypeError, ValueError):
            return Response(
                {"error": "'invoice_ids' conté valors no vàlids."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoices_by_id = {inv.id: inv for inv in Invoice.objects.filter(id__in=invoice_ids).select_related('invoice_file')}
        missing = [i for i in invoice_ids if i not in invoices_by_id]
        if missing:
            return Response(
                {"error": f"No existeixen les factures: {', '.join(str(i) for i in missing)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoices = [invoices_by_id[i] for i in invoice_ids]

        without_pdf = [
            (inv.serie_final or inv.token or str(inv.id))
            for inv in invoices
            # send_electronic_mail no adjunta els documents desactivats
            if not inv.invoice_file or not inv.invoice_file.is_active
        ]
        if without_pdf:
            return Response(
                {"error": f"Aquestes factures no tenen PDF vinculat o actiu: {', '.join(without_pdf)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_invoice = invoices[0]

        # 3. Resoldre la configuració de correu i el remitent (igual que send-email)
        company_config_id = request.data.get('company_config_id')
        if company_config_id:
            try:
                company_config_id = int(company_config_id)
            except (TypeError, ValueError):
                return Response(
                    {"error": "'company_config_id' ha de ser un enter."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            comm_config = CompanyConfig.objects.filter(id=company_config_id).first()
            if not comm_config:
                return Response(
                    {"error": f"No existeix cap CompanyConfig amb id '{company_config_id}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            company_obj = first_invoice.company or (
                first_invoice.exploitation.company if first_invoice.exploitation else None
            )
            if not company_obj:
                company_obj = (
                    Company.objects.filter(is_default=True, is_active=True).first()
                    or Company.objects.filter(is_active=True).first()
                )
            comm_config = company_obj.config if company_obj else None

        if not comm_config:
            return Response(
                {"error": "No s'ha trobat cap configuració de correu per a la companyia de la factura."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company_config_email = (
            comm_config.company_config_emails.filter(is_default=True, is_active=True).first()
            or comm_config.company_config_emails.filter(is_active=True).first()
            or comm_config.company_config_emails.first()
        )

        # 4. Tipus de missatge email i plantilla de text
        try:
            email_token = ConfigProject.objects.get(token='message_type_email_token').value
        except ConfigProject.DoesNotExist:
            return Response(
                {"error": "Falta la configuració 'message_type_email_token'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_type = MessageType.objects.filter(token=email_token).first()
        if not email_type:
            return Response(
                {"error": f"No existeix cap MessageType amb token '{email_token}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_names = [
            (inv.serie_final or inv.token or str(inv.id)) for inv in invoices
        ]
        names_text = ', '.join(invoice_names)

        template_type = (
            MessageTypeTemplate.objects.filter(type=email_type, is_active=True, unused=False)
            .order_by('-updated_at')
            .first()
        )
        subject = (
            request.data.get('subject')
            or (template_type.subject if template_type else None)
            or f"Factures {names_text}"
        )
        body = (
            request.data.get('body')
            or (template_type.body if template_type else None)
            or f"Us adjuntem les factures {names_text} en format PDF."
        )

        # 5. Contractes i titular (de la primera factura)
        contracts = []
        for inv in invoices:
            c = _invoice_contract(inv)
            if isinstance(c, Contract) and c not in contracts:
                contracts.append(c)

        first_contract = _invoice_contract(first_invoice)
        person = getattr(first_contract, 'holder', None)

        # Línies informatives amb TOTS els números (en text, no amb placeholders,
        # perquè un placeholder només resoldria la primera factura).
        info_lines = [f"Factura: {names_text}"]
        if contracts:
            info_lines.append(
                "Contracte: " + ', '.join(c.token for c in contracts if c.token)
            )
        body = f"{body}\n\n" + "\n".join(info_lines)

        # 6. Crear UNA Communication amb tots els PDF adjunts
        try:
            with transaction.atomic():
                status_default = CommunicationStatus.objects.get(is_default=True)

                message = Message.objects.create(
                    token=generate_token(Message),
                    subject=subject,
                    body=body,
                    type=email_type,
                )

                comm = Communication.objects.create(
                    token=generate_token(Communication),
                    person=person,
                    company_config=comm_config,
                    company_config_email=company_config_email,
                    status=status_default,
                    used_email=';'.join(emails),
                    type_tokens=email_type.token,
                    type_names=email_type.name,
                    user=request.user if request.user and request.user.is_authenticated else None,
                )
                comm.types.set([email_type])
                comm.messages.set([message])
                comm.invoices.set(invoices)
                if contracts:
                    comm.contracts.set(contracts)

                for inv in invoices:
                    CommunicationFile.objects.create(
                        token=generate_token(CommunicationFile),
                        communication=comm,
                        file=inv.invoice_file,
                        invoice=inv,
                        is_letter=False,
                    )

                create_email_template(comm)
        except Exception:
            logger.exception("Error creant la comunicació agrupada")
            return Response(
                {"error": "Error creant la comunicació."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 7. Enviar el correu
        try:
            send_electronic_mail(comm)
        except Exception:
            logger.exception("Error enviant la comunicació agrupada")
            return Response(
                {
                    "detail": "No s'ha pogut enviar el correu.",
                    "sent": False,
                    "invoice_ids": invoice_ids,
                    "communication_id": comm.id,
                    "error": "Ha ocorregut un error inesperat.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        comm.refresh_from_db()
        try:
            sent_token = ConfigProject.objects.get(token='communication_status_sent_token').value
        except ConfigProject.DoesNotExist:
            sent_token = None

        sent = bool(comm.status and sent_token and comm.status.token == sent_token) or bool(comm.sent_at)
        if sent:
            return Response(
                {
                    "detail": f"{len(invoices)} factures enviades correctament a {comm.used_email}.",
                    "sent": True,
                    "invoice_ids": invoice_ids,
                    "communication_id": comm.id,
                    "used_email": comm.used_email,
                    "sent_at": comm.sent_at,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "detail": "No s'ha pogut enviar el correu.",
                "sent": False,
                "invoice_ids": invoice_ids,
                "communication_id": comm.id,
                "error": comm.rejection_reason,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
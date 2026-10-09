from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404
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


class InvoiceSendEmailView(APIView):
    """Genera el PDF d'una factura i crea una Communication amb l'email preparat.

    URL: POST /invoice/<invoice id>/send-email/
    Body:
        - email (obligatori): adreça/es del destinatari (separades per ';').
        - company_config_id (opcional): selecciona la CompanyConfig (i la
          companyia). Si no s'indica, es dedueix de la factura.
        - subject (opcional): assumpte del correu.
        - body (opcional): cos del missatge.

    Crea un objecte Communication (com a communication/utils/message_service.py),
    hi adjunta el PDF ja vinculat a la factura (invoice_file, no es regenera),
    genera la plantilla d'email amb create_email_template (basic_email.html) i
    finalment envia el correu, retornant el resultat de l'enviament.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, id, *args, **kwargs):
        # 1. Validar el destinatari
        raw_email = (request.data.get('email') or '').strip()
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

        invoice = get_object_or_404(Invoice, id=id)

        # 2. Usar el PDF ja vinculat a la factura (no el regenerem)
        if not invoice.invoice_file:
            return Response(
                {"error": "La factura no té cap PDF vinculat (invoice_file)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Resoldre la configuració de correu i el remitent.
        # Si el body inclou company_config_id, s'usa per seleccionar la
        # CompanyConfig (i la companyia se'n deriva). Si no, es dedueix de la factura.
        company_config_id = request.data.get('company_config_id')
        if company_config_id:
            comm_config = CompanyConfig.objects.filter(id=company_config_id).first()
            if not comm_config:
                return Response(
                    {"error": f"No existeix cap CompanyConfig amb id '{company_config_id}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company_obj = comm_config.company_configs.first()
        else:
            company_obj = invoice.company or (
                invoice.exploitation.company if invoice.exploitation else None
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

        # 4. Resoldre el tipus de missatge email i la plantilla de text
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

        base_name = invoice.serie_final or invoice.token or str(invoice.id)
        template_type = (
            MessageTypeTemplate.objects.filter(type=email_type, is_active=True, unused=False)
            .order_by('-updated_at')
            .first()
        )
        subject = (
            request.data.get('subject')
            or (template_type.subject if template_type else None)
            or f"Factura {base_name}"
        )
        body = (
            request.data.get('body')
            or (template_type.body if template_type else None)
            or f"Us adjuntem la factura {base_name} en format PDF."
        )

        # 5. Crear la Communication amb la factura adjunta i la plantilla d'email
        contract = (
            invoice.contract
            or invoice.contract_request
            or (invoice.contract_termination.contract if invoice.contract_termination else None)
        )
        person = getattr(contract, 'holder', None)

        # Afegim al cos del missatge la informació del que s'envia (factura, contracte),
        # usant els placeholders que create_email_template substitueix per les dades reals.
        # Així el destinatari sempre veu aquesta informació, encara que el cos sigui personalitzat.
        info_lines = ["Factura: %invoice.serie_final"]
        if isinstance(contract, Contract):
            info_lines.append("Contracte: %contract.token")
        body = f"{body}\n\n" + "\n".join(info_lines)

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
                comm.invoices.set([invoice])
                if isinstance(contract, Contract):
                    comm.contracts.set([contract])

                # Adjuntar el PDF ja vinculat a la factura
                CommunicationFile.objects.create(
                    token=generate_token(CommunicationFile),
                    communication=comm,
                    file=invoice.invoice_file,
                    invoice=invoice,
                    is_letter=False,
                )

                # Generar el HTML de l'email (basic_email.html)
                create_email_template(comm)
        except Exception as e:
            return Response(
                {"error": f"Error creant la comunicació: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 6. Enviar el correu. send_electronic_mail gestiona la selecció de backend
        # (SMTP / MS Graph), adjunta el fitxer i actualitza l'estat de la comunicació
        # (enviada) o hi desa el motiu de rebuig si falla.
        try:
            send_electronic_mail(comm)
        except Exception as e:
            return Response(
                {
                    "detail": "No s'ha pogut enviar el correu.",
                    "sent": False,
                    "invoice_id": invoice.id,
                    "communication_id": comm.id,
                    "error": str(e),
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
                    "detail": f"Factura enviada correctament a {comm.used_email}.",
                    "sent": True,
                    "invoice_id": invoice.id,
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
                "invoice_id": invoice.id,
                "communication_id": comm.id,
                "error": comm.rejection_reason,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
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
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from documentmanager.utils.main_utils import upload_document
from service.models import Company, CompanyConfig

from ..models import GeneralPaymentSepaDocument


class SepaDocumentSendEmailView(APIView):
    """Envia per correu el document SEPA (autorització de domiciliació) generat.

    URL: POST /sepa-document/<GeneralPaymentSepaDocument id>/send-email/
    Body:
        - email (obligatori): adreça/es del destinatari (separades per ';').
        - contract_id (obligatori): contracte o sol·licitud del document.
        - is_request (opcional): `true` si contract_id és d'una ContractRequest.
        - company_config_id (opcional): selecciona la CompanyConfig. Si no
          s'indica, es dedueix de l'explotació del contracte.
        - subject (opcional): assumpte del correu.
        - body (opcional): cos del missatge.

    El PDF generat (GeneralPaymentSepaDocument.template) es puja al gestor
    documental vinculat al contracte i s'adjunta a una Communication nova, que
    s'envia amb send_electronic_mail (com a InvoiceSendEmailView).
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

        sepa = get_object_or_404(GeneralPaymentSepaDocument, id=id)
        if not sepa.template:
            return Response(
                {"error": "El document SEPA no s'ha generat."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract_id = request.data.get('contract_id')
        if not contract_id:
            return Response(
                {"error": "El camp 'contract_id' és obligatori."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_request = str(request.data.get('is_request', '')).lower() == 'true'
        contract = get_object_or_404(ContractRequest if is_request else Contract, id=contract_id)

        # 2. Resoldre la configuració de correu i el remitent
        company_config_id = request.data.get('company_config_id')
        if company_config_id:
            comm_config = CompanyConfig.objects.filter(id=company_config_id).first()
            if not comm_config:
                return Response(
                    {"error": f"No existeix cap CompanyConfig amb id '{company_config_id}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            supply_point = contract.supply_point_default
            exploitation = (
                supply_point.connection.exploitation
                if supply_point and supply_point.connection
                else None
            )
            company_obj = exploitation.company if exploitation else None
            if not company_obj:
                company_obj = (
                    Company.objects.filter(is_default=True, is_active=True).first()
                    or Company.objects.filter(is_active=True).first()
                )
            comm_config = company_obj.config if company_obj else None

        if not comm_config:
            return Response(
                {"error": "No s'ha trobat cap configuració de correu per a la companyia del contracte."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company_config_email = (
            comm_config.company_config_emails.filter(is_default=True, is_active=True).first()
            or comm_config.company_config_emails.filter(is_active=True).first()
            or comm_config.company_config_emails.first()
        )

        # 3. Resoldre el tipus de missatge email i la plantilla de text
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

        template_type = (
            MessageTypeTemplate.objects.filter(type=email_type, is_active=True, unused=False)
            .order_by('-updated_at')
            .first()
        )
        subject = (
            request.data.get('subject')
            or (template_type.subject if template_type else None)
            or "Autorització de domiciliació bancària SEPA"
        )
        body = (
            request.data.get('body')
            or (template_type.body if template_type else None)
            or "Us adjuntem l'autorització de domiciliació bancària SEPA per signar."
        )
        if isinstance(contract, Contract):
            body = f"{body}\n\nContracte: %contract.token"

        # 4. Crear la Communication amb el document SEPA adjunt
        try:
            with transaction.atomic():
                sepa.template.open('rb')
                try:
                    content = ContentFile(sepa.template.read())
                finally:
                    sepa.template.close()

                document = upload_document(
                    content,
                    'CONTRACT',
                    'SEPA',
                    contract.id,
                    contract.token,
                    '',
                    settings.DOCUMENT_MANAGER_SERVICES.get("contract"),
                    f"SEPA_{contract.token}.pdf",
                )

                status_default = CommunicationStatus.objects.get(is_default=True)

                message = Message.objects.create(
                    token=generate_token(Message),
                    subject=subject,
                    body=body,
                    type=email_type,
                )

                comm = Communication.objects.create(
                    token=generate_token(Communication),
                    person=contract.holder,
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
                if isinstance(contract, Contract):
                    comm.contracts.set([contract])

                CommunicationFile.objects.create(
                    token=generate_token(CommunicationFile),
                    communication=comm,
                    file=document,
                    is_letter=False,
                )

                create_email_template(comm)
        except Exception as e:
            return Response(
                {"error": f"Error creant la comunicació: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 5. Enviar el correu (send_electronic_mail actualitza l'estat de la comunicació)
        try:
            send_electronic_mail(comm)
        except Exception as e:
            return Response(
                {
                    "detail": "No s'ha pogut enviar el correu.",
                    "sent": False,
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
                    "detail": f"Document SEPA enviat correctament a {comm.used_email}.",
                    "sent": True,
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
                "communication_id": comm.id,
                "error": comm.rejection_reason,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

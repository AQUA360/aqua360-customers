from django.http import FileResponse
from django.conf import settings
from django.db import transaction
from django.db.models import Case, Count, F, Prefetch, Q, Value, When
from django.db.models.functions import Replace, Upper
from django.utils import translation, timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
import base64
import csv
import re
import zipfile
import logging
from io import BytesIO, StringIO
from billing.utils.biller_period_service import current_and_next_cycles
from billing.views.invoice_pdf_view import generate_report_invoice_pdf
from coredata.utils.pdf_utils import merge_pdfs
from coredata.models import (
    ConfigProject,
    Person,
    PersonAddress,
    PersonBank,
    PersonContact,
)
from coredata.utils.name_utils import generate_token, check_token_exists
from coredata.utils import name_utils as name_utils_module
from contract.utils.contract_token_service import generate_contract_request_token
from logger.models import LogIncidentStatusChange, LogContractRequestStatus
from notification.models import Incident, IncidentStatus, IncidentType
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from contract.models import (
    Contract,
    ContractLog,
    ContractObservation,
    ContractPriceRate,
    ContractRequest,
    ContractRequestStatus,
    ContractRequestType,
    ContractStatus,
    ContractTerminationRequest,
    ContractTerminationRequestObservation,
    ContractTerminationStatus,
    ContractTerminationType,
    PaymentType,
)
from billing.models import (
    GeneralPayment,
    GeneralPaymentSepaDocument,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    Reading,
)
from documentmanager.utils.main_utils import download_document, upload_document
from pricing.models import PriceRate, Product
from service.models import Property, SupplyPoint
from service.utils.route_scope import effective_route
from ov.serializers import (
    BillingDataOVSerializer,
    BillingContractInvoicesOVSerializer,
    UpdateBillingDataOVSerializer,
    UpdateBillingDataOVIBANSerializer,
    BilledConsumptionsOVSerializer,
    InvoicePaidSerializer,
    InvoicePDFSerializer,
    ContractListItemOVSerializer,
    ContractFullDetailSerializer,
    ContractByNicSerializer,
    InvoiceFullDetailSerializer,
    MeterDetailSerializer,
    ConsumptionHistoryItemSerializer,
    ConsumptionDownloadRequestSerializer,
    BillingPeriodItemSerializer,
    SepaDocumentUploadSerializer,
    CancelDirectDebitSerializer,
    ContactDataOVSerializer,
    BatchInvoiceDownloadSerializer,
    ContractRequestTypeDictionarySerializer,
    ContractStatusDictionarySerializer,
    PaymentTypeDictionarySerializer,
    InvoiceStatusDictionarySerializer,
    ProcedureTariffDictionarySerializer,
    PropertyItemSerializer,
    PersonDataSerializer,
    QuickPayRequestSerializer,
    QuickPayResponseSerializer,
    ReturnRequestSerializer,
    ReturnRequestResponseSerializer,
    ContractProcedureRequestSerializer,
    ContractProcedureResponseSerializer,
    mask_iban,
    ContractRequestStatusSerializer,
    ContractTerminationProcedureRequestSerializer,
    ContractChangeProcedureRequestSerializer,
    ContractChangeProcedureResponseSerializer,
    ContractTerminationProcedureResponseSerializer,
)
from pagination.ov_pagination import OVLimitPagination, OVConsumptionPagination
from ov.throttles import (
    ContractProcedureThrottle,
    ContractTerminationProcedureThrottle,
    ContractChangeProcedureThrottle,
    DniEnumerationThrottle,
    PaymentReceiptThrottle,
    PersonDataThrottle,
    QuickPayThrottle,
    ReturnRequestThrottle,
)

logger = logging.getLogger(__name__)


class ContractOVView(APIView):
    """Detalle completo del contrato por `contract_token` (query string).

    `GET /ov/contract-detail/?contract_token=<token>` devuelve directamente
    los datos del contrato (mismo esquema `ContractFullDetail` que
    `GET /ov/contract/{token}/`), sin redirigir. El token puede contener
    barra (`/`), por lo que no puede resolverse como parámetro de ruta
    `<str:token>`: se busca por consulta a la base de datos. `400` si falta
    el parámetro, `404` si el contrato no existe.
    """

    permission_classes = [IsAuthenticated]
    queryset = Contract.objects.select_related(
        "holder",
        "status",
        "payment__type",
        "payment__IBAN",
        "payment__IBAN__person",
        "supply_point_default",
        "supply_point_default__address",
        "use_type",
    )

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = self.queryset.filter(token=contract_token).first()
        if contract is None:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )
        self.check_object_permissions(request, contract)

        serializer = ContractFullDetailSerializer(
            contract, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class BillingDataOVView(APIView):
    queryset = Contract.objects.all()
    permission_classes = [IsAuthenticated]
    LookupField = "token"

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)

        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = self.queryset.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BillingDataOVSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        contract_token = request.query_params.get("contract_token", None)
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = self.queryset.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UpdateBillingDataOVSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Update the contract with validated data
            updated_contract = serializer.update(contract, serializer.validated_data)

            # Return the updated data
            response_serializer = BillingDataOVSerializer(updated_contract)
            return Response(
                {
                    "message": "Billing data updated successfully",
                    "data": response_serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception("Error inesperat")
            return Response(
                {"error": "Failed to update billing data."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BillingDataOVUpdateIBANView(APIView):
    queryset = Contract.objects.all()
    permission_classes = [IsAuthenticated]
    LookupField = "token"

    def post(self, request):
        contract_token = request.query_params.get("contract_token", None)
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = self.queryset.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = UpdateBillingDataOVIBANSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            upadated_contract = serializer.update(contract, serializer.validated_data)
            response_serializer = BillingDataOVSerializer(upadated_contract)

            return Response(
                {
                    "message": "IBAN updated successfully ",
                    "data": response_serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("Error inesperat")
            return Response(
                {"error": "Failed to update IBAN."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BillingContractInvoicesOVView(APIView):
    permission_classes = [IsAuthenticated]
    queryset = Contract.objects.all()

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = self.queryset.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        invoices = (
            Invoice.objects.filter(contract=contract)
            .exclude(status__token="1")  # excluïm les factures de pre-factura
            .select_related("status", "contract", "payment_type")
        )

        serializer = BillingContractInvoicesOVSerializer(invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BillingContractInvoiceOVView(APIView):
    permission_classes = [IsAuthenticated]
    queryset = Invoice.objects.all()

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)
        invoice_token = request.query_params.get("invoice_token", None)

        if not contract_token or not invoice_token:
            return Response(
                {"error": "Contract token and invoice token are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = self.queryset.filter(
            token=invoice_token, contract__token=contract_token
        ).first()

        if not invoice:
            return Response(
                {"error": "Invoice not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BillingContractInvoicesOVSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UnpayedInvoicesOVView(APIView):
    permission_classes = [IsAuthenticated]
    queryset = Invoice.objects.all()

    @staticmethod
    def _automated_unpaid_status_tokens():
        unpaid_config_tokens = (
            "invoice_status_confirmed_token",
            "invoice_status_sent_token",
            "invoice_status_expired_token",
            "invoice_status_endowment_token",
            "invoice_status_default_token",
            "invoice_status_commitment_token",
        )
        terminal_config_tokens = (
            "invoice_status_paid_token",
            "invoice_status_cancelled_token",
            "invoice_status_pending_token",
        )
        configured_values = dict(
            ConfigProject.objects.filter(
                token__in=unpaid_config_tokens + terminal_config_tokens
            ).values_list("token", "value")
        )
        unpaid_tokens = {
            configured_values[token]
            for token in unpaid_config_tokens
            if configured_values.get(token)
        }
        terminal_tokens = {
            configured_values[token]
            for token in terminal_config_tokens
            if configured_values.get(token)
        }
        return unpaid_tokens - terminal_tokens

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)

        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        qp_statuses = request.query_params.get("statuses", None)
        automated_unpaid = (
            (request.query_params.get("unpaid") or "").strip().lower() == "true"
        )
        if not qp_statuses and not automated_unpaid:
            return Response(
                {"error": "Statuses are required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if qp_statuses:
            status_tokens = [
                token.strip() for token in qp_statuses.split(",") if token.strip()
            ]
        else:
            status_tokens = list(self._automated_unpaid_status_tokens())
        if not status_tokens:
            return Response(
                {"error": "At least one valid status token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        statuses = InvoiceStatus.objects.filter(token__in=status_tokens)
        if not statuses.exists():
            return Response(
                {
                    "error": f"No valid statuses found for tokens: {', '.join(status_tokens)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # optional payment type exclusion
        invoices_queryset = Invoice.objects.filter(
            contract=contract, status__in=statuses
        ).exclude(
            status__token="1"
        )  # mateix filtre base que /ov/invoices/: sense pre-factures

        qp_exc_payment_type = request.query_params.get("exc_payment_type_token", None)
        if qp_exc_payment_type:
            payment_type_tokens = [
                token.strip()
                for token in qp_exc_payment_type.split(",")
                if token.strip()
            ]
            if payment_type_tokens:
                invoices_queryset = invoices_queryset.exclude(
                    payment_type_token_final__in=payment_type_tokens
                )

        invoices = invoices_queryset.select_related(
            "status", "payment_type", "contract"
        )
        serializer = BillingContractInvoicesOVSerializer(invoices, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class BilledConsumptionsOVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        invoices = Invoice.objects.filter(contract=contract)
        serilizer = BilledConsumptionsOVSerializer(invoices, many=True)

        return Response(serilizer.data, status=status.HTTP_200_OK)


class InvoicePaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InvoicePaidSerializer(data=request.data)
        if serializer.is_valid():
            invoice = serializer.update(serializer.validated_data)
            return Response(
                {
                    "success": True,
                    "message": "Invoice marked as paid successfully",
                    "invoice_token": invoice.token,
                    "new_status": invoice.status.name if invoice.status else None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


import base64
from io import BytesIO
from xhtml2pdf import pisa
from django.template.loader import render_to_string


class InvoicePDFView(APIView):
    permission_classes = [IsAuthenticated]
    queryset = Invoice.objects.all()

    # def get_template_name(self):
    #    language = getattr(settings, 'INVOICE_LANGUAGE', 'ca')
    #    return f'invoice_pdf_{language}.html'

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)
        invoice_token = request.query_params.get("invoice_token", None)

        if not contract_token or not invoice_token:
            return Response(
                {"error": "Contract token and invoice token are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from coredata.models import ConfigProject

        invoice_type_config = ConfigProject.objects.filter(
            token="invoice_type_invoice_token"
        ).first()
        if not invoice_type_config or not invoice_type_config.value:
            return Response(
                {"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND
            )
        file_type_value = invoice_type_config.value
        invoice: Invoice = self.queryset.filter(
            token=invoice_token,
            contract__token=contract_token,
            type_final=file_type_value,
        ).first()

        if not invoice:
            invoice = self.queryset.filter(
                serie_final=invoice_token,
                contract__token=contract_token,
                type_final=file_type_value,
            ).first()

        if not invoice:
            return Response(
                {"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND
            )

        from documentmanager.utils.main_utils import download_document

        try:
            filename = (
                f"invoice_{invoice.serie_final}_{invoice.id}.pdf"
                if invoice.serie_final
                else f"invoice_{invoice.token}_{invoice.id}.pdf"
            )
            pdf_bytes = None
            document_name = filename
            if invoice.invoice_file:
                try:
                    pdf_bytes = download_document(invoice.invoice_file).content
                    document_name = invoice.invoice_file.document_name or filename
                except Exception:
                    logger.warning(
                        "Could not retrieve stored PDF for invoice %s", invoice.id
                    )
            if pdf_bytes is None:
                _, _, pdf_buffer = generate_report_invoice_pdf(
                    invoice, request, context={"request": request}, save_pdf=False
                )
                pdf_bytes = pdf_buffer.getvalue()
                document_name = filename
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            return Response(
                {
                    "pdf": pdf_base64,  # Base64-encoded PDF content
                    "filename": filename,  # Suggested filename for download
                    "document_name": document_name,  # Original document name
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception("Error inesperat")
            # Step 12: Handle any errors during document retrieval or conversion
            return Response(
                {"error": "Failed to retrieve invoice PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        #                          !-> old logic <-!
        #
        # Use the new PDF-specific serializer
        # serializer = InvoicePDFSerializer(invoice)
        # invoice_data = serializer.data

        # Get template based on language setting
        # template_name = self.get_template_name()

        # try:
        #     html_content = render_to_string(template_name, {'invoice': invoice_data})
        # except:
        #     # Fallback to default template if language-specific template doesn't exist
        #     html_content = render_to_string('invoice_pdf_ca.html', {'invoice': invoice_data})

        # # Generate PDF
        # pdf_buffer = BytesIO()
        # pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)

        # if pisa_status.err:
        #     return Response(
        #         {'error': 'PDF generation failed'},
        #         status=status.HTTP_500_INTERNAL_SERVER_ERROR
        #     )

        # pdf_buffer.seek(0)
        # pdf_bytes = pdf_buffer.read()
        # pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # return Response(
        #     {'pdf': pdf_base64, 'filename': f'invoice_{invoice.number}.pdf'},
        #     status=status.HTTP_200_OK
        # )


class CreateReadingOVView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from ov.serializers_refactor.create_reading_serializer import (
            CreateReadingSerializer,
        )

        serializer = CreateReadingSerializer(data=request.data)
        if serializer.is_valid():
            reading = serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Reading created successfully",
                    "reading_token": reading.token,
                    "reading_value": str(reading.reading_value),
                    "reading_date": str(reading.reading_date),
                    "contract_token": (
                        reading.contract.token if reading.contract else None
                    ),
                    "meter_token": reading.meter.token if reading.meter else None,
                    "supply_point_token": (
                        reading.supply_point.token if reading.supply_point else None
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContractsListOVView(APIView):
    """
    GET /ov/contracts/?dni=<DNI>[&estado=<token>][&page=<n>][&limit=<n>]

    Lists every contract in which the supplied DNI acts either as the contract
    holder or as the holder of the direct-debit (IBAN) account.

    Authenticated with `Authorization: Token <token>`; `RestrictOVUserMiddleware`
    confines `ov` group members to `/ov/` paths.
    """

    permission_classes = [IsAuthenticated]
    queryset = Contract.objects.all()
    pagination_class = OVLimitPagination
    throttle_classes = [DniEnumerationThrottle]

    def get(self, request):
        dni = (request.query_params.get("dni") or "").strip().upper()
        if not dni:
            return Response(
                {"error": "DNI is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        estado = (request.query_params.get("estado") or "").strip()

        contracts = (
            self.queryset.filter(
                Q(holder__token=dni)
                | Q(payment__IBAN__person__token=dni)
                | Q(payment__IBAN__dni=dni)
            )
            .select_related("status", "holder", "payment__type", "payment__IBAN")
            .order_by("token")
            .distinct()
        )
        if estado:
            contracts = contracts.filter(status__token=estado)

        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(contracts, request, view=self)
        except NotFound:
            return Response(
                {"error": "Invalid page"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ContractListItemOVSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)


class ContractDetailByTokenOVView(RetrieveAPIView):
    """GET /ov/contract/{token}/ — detalle completo de un contrato por token."""

    queryset = Contract.objects.select_related(
        "holder",
        "status",
        "payment__type",
        "payment__IBAN",
        "payment__IBAN__person",
        "supply_point_default",
        "supply_point_default__address",
        "use_type",
    )
    permission_classes = [IsAuthenticated]
    serializer_class = ContractFullDetailSerializer
    lookup_field = "token"
    lookup_url_kwarg = "token"

    def get_object(self):
        token = self.kwargs.get(self.lookup_url_kwarg)
        contract = self.get_queryset().filter(**{self.lookup_field: token}).first()
        if contract is None:
            raise NotFound({"error": "Contract not found"})
        self.check_object_permissions(self.request, contract)
        return contract


def is_valid_nic(nic):
    r"""Equivale a re.fullmatch(r"\d+(?:/\d+){1,2}", nic) sin regex: de 2 a 3
    grupos de dígitos separados por «/» (CodeQL marca la regex como ReDoS)."""
    parts = nic.split("/")
    return 2 <= len(parts) <= 3 and all(part.isdecimal() for part in parts)


class ContractByNicView(RetrieveAPIView):
    """GET /ov/contract/by-nic/<nic>/ — detalle del contrato por NIC (token del
    punto de suministro). El NIC incluye «/» con una o dos barras (p. ej.
    `12345/1234` o `012345/654321/12345678`), por eso la
    ruta usa `<path:nic>`; el formato se valida con regex ANTES de consultar la
    BD. Si el punto de suministro es el por defecto de varios contratos se
    devuelve el más reciente (`created_at` desc)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [DniEnumerationThrottle]
    serializer_class = ContractByNicSerializer
    queryset = Contract.objects.select_related(
        "holder",
        "status",
        "payment__type",
        "payment__IBAN",
        "payment__IBAN__person",
        "supply_point_default",
        "supply_point_default__address",
        "use_type",
    )

    def get_object(self):
        """Valida el NIC, busca el contrato más reciente y comprueba los permisos.

        Prioriza el punto de suministro por defecto y después busca en los demás.
        Lanza ValidationError si el NIC es inválido o NotFound si no hay contrato.
        """
        nic = (self.kwargs.get("nic") or "").strip()
        if not is_valid_nic(nic):
            raise ValidationError({"error": "Invalid NIC format"})
        contract = (
            self.queryset.filter(supply_point_default__token=nic)
            .order_by("-created_at")
            .first()
            or self.queryset.filter(supply_points__token=nic)
            .order_by("-created_at")
            .first()
        )
        if contract is None:
            raise NotFound({"error": "Contract not found"})
        self.check_object_permissions(self.request, contract)
        return contract


class InvoiceDetailByTokenOVView(RetrieveAPIView):
    """GET /ov/invoice/{token}/detail/ — detalle completo de una factura definitiva.
    Excluye proformas, pre-facturas y presupuestos (igual que `/ov/invoice-pdf/`)."""

    serializer_class = InvoiceFullDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "token"
    lookup_url_kwarg = "token"

    def get_queryset(self):
        cfg = ConfigProject.objects.filter(token="invoice_type_invoice_token").first()
        invoice_type_token = cfg.value if cfg and cfg.value else None
        queryset = (
            Invoice.objects.exclude(status__token="1")
            .select_related("contract", "status")
            .prefetch_related("readings__previous_reading")
        )
        if invoice_type_token:
            queryset = queryset.filter(type_final=invoice_type_token)
        return queryset

    def get_object(self):
        token = self.kwargs.get(self.lookup_url_kwarg)
        invoice = self.get_queryset().filter(**{self.lookup_field: token}).first()
        if invoice is None:
            raise NotFound({"error": "Invoice not found"})
        self.check_object_permissions(self.request, invoice)
        return invoice


class MeterDetailByTokenOVView(RetrieveAPIView):
    """GET /ov/meter/{contract_token}/ — detalle del contador por token de contrato."""

    queryset = Contract.objects.select_related("supply_point_default__meter")
    permission_classes = [IsAuthenticated]
    serializer_class = MeterDetailSerializer
    lookup_field = "token"
    lookup_url_kwarg = "token"

    def get_object(self):
        token = self.kwargs.get(self.lookup_url_kwarg)
        contract = self.get_queryset().filter(**{self.lookup_field: token}).first()
        if contract is None:
            raise NotFound({"error": "Contract not found"})
        self.check_object_permissions(self.request, contract)
        return contract


class ConsumptionHistoryOVView(APIView):
    """GET /ov/consumptions/?contract_token=<token>[&date_from=&date_to=&page=&page_size=]

    Historial de consumos del contador del contrato en nomenclatura HF
    (`{any}-{q}T`). Devuelve el envoltorio estándar DRF
    `{count, next, previous, results}` (esquema `ConsumptionHistoryResponse`).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = OVConsumptionPagination

    def get(self, request):
        contract_token = request.query_params.get("contract_token")
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = (
            Contract.objects.select_related("supply_point_default__meter")
            .filter(token=contract_token)
            .first()
        )
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        meter = (
            contract.supply_point_default.meter if contract.supply_point_default else None
        )

        date_from_raw = request.query_params.get("date_from")
        date_to_raw = request.query_params.get("date_to")
        date_from = parse_date(date_from_raw) if date_from_raw else None
        date_to = parse_date(date_to_raw) if date_to_raw else None
        if (date_from_raw and not date_from) or (date_to_raw and not date_to):
            return Response(
                {"error": "Invalid date format (expected YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if date_from and date_to and date_from > date_to:
            return Response(
                {"error": "date_from must be before or equal to date_to"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if meter:
            queryset = Reading.objects.filter(meter=meter)
        else:
            queryset = Reading.objects.none()

        # Només consums facturats: lectures vinculades a almenys una factura
        queryset = queryset.filter(invoices__isnull=False).distinct()

        queryset = (
            queryset.select_related("previous_reading")
            .prefetch_related("invoices")
            .order_by("-reading_date", "-id")
        )
        if date_from:
            queryset = queryset.filter(reading_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(reading_date__lte=date_to)

        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(queryset, request, view=self)
        except NotFound:
            return Response(
                {"error": "Invalid page"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ConsumptionHistoryItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

CONSUMPTION_CSV_COLUMNS = [
    "id",
    "period",
    "reading",
    "previous_reading",
    "consumption",
    "reading_date",
    "is_estimated",
]


def _consumptions_csv(queryset):
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(CONSUMPTION_CSV_COLUMNS)
    rows = ConsumptionHistoryItemSerializer(queryset, many=True).data
    for row in rows:
        writer.writerow([row.get(column) for column in CONSUMPTION_CSV_COLUMNS])
    return out.getvalue().encode("utf-8")


def _pdf_stub_bytes():
    html = "<html><body><h1>Oficina Virtual — stub</h1><p>Generación del PDF pendiente de implementar.</p></body></html>"
    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer)
    return buffer.getvalue()


def _zip_stub_bytes():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr(
            "README.txt", "OV stub: descarga ZIP pendiente de implementar."
        )
    return buffer.getvalue()


def _download_response(payload, content_type, filename):
    return FileResponse(
        BytesIO(payload),
        content_type=content_type,
        as_attachment=True,
        filename=filename,
    )


class ConsumptionDownloadOVView(APIView):
    """GET /ov/consumption/{id}/download/?contract_token=<token>[&format=pdf|csv]

    Descarga el fichero de una única lectura del historial de consumos. El `id`
    es el `Reading.id` expuesto por `GET /ov/consumptions/`. CSV real; PDF es
    un stub mientras no se implemente la maquetación.
    """

    permission_classes = [IsAuthenticated]
    allowed_formats = ("pdf", "csv")

    def get(self, request, id):
        contract_token = request.query_params.get("contract_token")
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        export_format = request.query_params.get("format", "pdf")
        if export_format not in self.allowed_formats:
            return Response(
                {"error": "Invalid format (expected pdf or csv)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = (
            Contract.objects.select_related("supply_point_default__meter")
            .filter(token=contract_token)
            .first()
        )
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        meter = (
            contract.supply_point_default.meter if contract.supply_point_default else None
        )
        reading = None
        if meter:
            reading = (
                Reading.objects.filter(
                    pk=id, meter=meter, invoices__isnull=False
                )
                .select_related("previous_reading")
                .prefetch_related("invoices")
                .first()
            )

        if not reading:
            return Response(
                {"error": "Reading not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if export_format == "csv":
            payload = _consumptions_csv([reading])
            return _download_response(
                payload, "text/csv", f"consumption_{id}.csv"
            )

        payload = _pdf_stub_bytes()
        return _download_response(
            payload, "application/pdf", f"consumption_{id}.pdf"
        )


class ConsumptionsDownloadOVView(APIView):
    """POST /ov/consumptions/download/

    Descarga el historial de consumos del contrato: solo las lecturas de
    `reading_ids` (filas marcadas) o, si no se indican, todo el conjunto
    filtrado por `date_from`/`date_to` (botón «Seleccionar todo»). CSV real;
    PDF y ZIP son stubs.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConsumptionDownloadRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        contract_token = data["contract_token"]
        contract = (
            Contract.objects.select_related("supply_point_default__meter")
            .filter(token=contract_token)
            .first()
        )
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        meter = (
            contract.supply_point_default.meter if contract.supply_point_default else None
        )
        export_format = data.get("format", "pdf")

        if data.get("reading_ids"):
            if not meter:
                return Response(
                    {"reading_ids": ["ID de lectura desconocido"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = Reading.objects.filter(meter=meter, pk__in=data["reading_ids"])
            found_ids = set(queryset.values_list("pk", flat=True))
            missing_ids = [
                reading_id
                for reading_id in data["reading_ids"]
                if reading_id not in found_ids
            ]
            if missing_ids:
                return Response(
                    {
                        "reading_ids": [
                            f"ID de lectura desconocido: {reading_id}"
                            for reading_id in missing_ids
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            queryset = Reading.objects.filter(meter=meter) if meter else Reading.objects.none()
            if data.get("date_from"):
                queryset = queryset.filter(reading_date__gte=data["date_from"])
            if data.get("date_to"):
                queryset = queryset.filter(reading_date__lte=data["date_to"])

        # Només consums facturats: les lectures no facturades s'ometen del fitxer
        queryset = (
            queryset.filter(invoices__isnull=False)
            .distinct()
            .select_related("previous_reading")
            .prefetch_related("invoices")
            .order_by("-reading_date", "-id")
        )

        if export_format == "csv":
            payload = _consumptions_csv(queryset)
            return _download_response(
                payload, "text/csv", f"consumptions_{contract_token}.csv"
            )
        if export_format == "zip":
            payload = _zip_stub_bytes()
            return _download_response(
                payload, "application/zip", f"consumptions_{contract_token}.zip"
            )

        payload = _pdf_stub_bytes()
        return _download_response(
            payload, "application/pdf", f"consumptions_{contract_token}.pdf"
        )


def _contract_biller(contract):
    """Facturador del contrato (el de la ruta del seu punt de subministrament);
    `None` si algun enllaç de la cadena no existeix."""
    route = effective_route(contract.supply_point_default)
    return route.biller if route else None


class BillingPeriodsOVView(APIView):
    """GET /ov/billing-periods/?contract_token=<token>

    Devuelve los periodos de facturación disponibles para el contrato (ciclos
    definidos por su facturador: `period_type` + `initial_month`), para el
    selector de «Primera domiciliación» del frontal. Devuelve el ciclo en curso
    (`is_current=true`, primero) y el siguiente, calculados a partir de la
    fecha actual. Sin facturador en la ruta se aplican los valores por defecto
    del modelo `Biller` (trimestral desde enero). El contrato se valida igual
    que en el resto de endpoints (`404` si no existe).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        contract_token = request.query_params.get("contract_token")
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = (
            Contract.objects.select_related(
                "supply_point_default__route_position__route__biller",
                "supply_point_default__property__route_position__route__biller",
            )
            .filter(token=contract_token)
            .first()
        )
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        biller = _contract_biller(contract)
        cycles = current_and_next_cycles(timezone.localdate(), biller)
        serializer = BillingPeriodItemSerializer(cycles, many=True)
        return Response(serializer.data)


class SepaDocumentUploadView(APIView):
    """POST /ov/procedures/{contract_token}/upload-sepa-signed/

    Sube y archiva el mandato SEPA firmado de un contrato. Valida que el
    contrato exista (404 si no) y que el `iban` enviado coincida con el IBAN
    activo de la cuenta de domiciliación (400 si no coincide); archiva el
    documento en el gestor documental y lo vincula a la forma de pago del
    contrato (`GeneralPaymentSepaDocument`), devolviendo 201 con
    {"contract_token", "success": true}.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @staticmethod
    def _normalize_iban(value):
        if not value:
            return ""
        return "".join(str(value).split()).upper()

    def post(self, request, contract_token):
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = SepaDocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_iban = serializer.validated_data["iban"]
        uploaded_file = serializer.validated_data["sepa"]
        service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")

        with transaction.atomic():
            general_payment = None
            if contract.payment_id:
                general_payment = GeneralPayment.objects.select_for_update().get(
                    pk=contract.payment_id
                )
            active_iban = None
            if general_payment and general_payment.IBAN:
                active_iban = general_payment.IBAN.iban
            if self._normalize_iban(uploaded_iban) != self._normalize_iban(active_iban):
                return Response(
                    {
                        "error": "The IBAN does not match the contract's current active account."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            person_bank = general_payment.IBAN or general_payment.company_iban
            folder_name = "SEPA"
            if person_bank:
                if hasattr(person_bank, "name") and person_bank.name:
                    folder_name = person_bank.name
                elif hasattr(person_bank, "person") and person_bank.person:
                    folder_name = (
                        f"{person_bank.person.name} {person_bank.person.surname or ''}"
                    ).strip()
                elif hasattr(person_bank, "company") and person_bank.company:
                    folder_name = person_bank.company.name
                elif hasattr(person_bank, "iban") and person_bank.iban:
                    folder_name = person_bank.iban
            folder_name = folder_name.replace(" ", "_").upper()

            document = upload_document(
                uploaded_file,
                "SEPA",
                "CONTRACT",
                general_payment.id,
                general_payment.token or "",
                folder_name,
                service,
                uploaded_file.name,
                hdd_subfolder=str(general_payment.id),
            )
            GeneralPaymentSepaDocument.objects.filter(
                general_payment=general_payment
            ).delete()
            GeneralPaymentSepaDocument.objects.create(
                general_payment=general_payment, file=document, checked=True
            )

        logger.info(
            "Archived signed SEPA mandate for contract %s (document %s)",
            contract_token,
            document.id,
        )

        return Response(
            {"contract_token": contract_token, "success": True},
            status=status.HTTP_201_CREATED,
        )


class SepaDocumentDownloadView(APIView):
    """GET /ov/procedures/{contract_token}/sepa-signed/

    Devuelve el mandato SEPA firmado archivado para la forma de pago del
    contrato. Responde 404 si el contrato no existe o si no hay mandato
    archivado.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, contract_token):
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        sepa_document = None
        if contract.payment:
            sepa_document = (
                GeneralPaymentSepaDocument.objects.filter(
                    general_payment=contract.payment, file__isnull=False
                )
                .select_related("file")
                .first()
            )

        if not sepa_document or not sepa_document.file:
            return Response(
                {"error": "SEPA document not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = download_document(sepa_document.file)
        if response is None:
            return Response(
                {"error": "SEPA document not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return response


class CancelDirectDebitView(APIView):
    """POST /ov/procedures/{contract_token}/cancel-direct-debit/

    Revoca el mandat SEPA i canvia la forma de pagament del contracte.
    Valida `period`, `role` i `new_payment_type` (opcional), comprova que el
    contracte tingui forma de pagament i resol el `PaymentType` objectiu
    (`new_payment_type` si ve, sinó `BANK_TRANSFER`). La trucada és
    idempotent: si el contracte ja té el tipus objectiu no escriu res i
    respon «already cancelled». La migració de tipus, el `ContractLog` i
    l'`ContractObservation` es fan dins d'un `transaction.atomic()`.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, contract_token):
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = CancelDirectDebitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not contract.payment:
            return Response(
                {"error": "Contract has no payment method"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_payment_type = serializer.validated_data.get("new_payment_type")
        if requested_payment_type:
            target_payment_type = PaymentType.objects.filter(
                token=requested_payment_type
            ).first()
            if not target_payment_type:
                return Response(
                    {"error": "Invalid payment type token"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target_payment_type = PaymentType.objects.filter(
                token="BANK_TRANSFER"
            ).first()
            if not target_payment_type:
                return Response(
                    {"error": "Default payment type BANK_TRANSFER not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        current_payment_token = (
            contract.payment.type.token if contract.payment.type else None
        )
        if current_payment_token == target_payment_type.token:
            return Response(
                {
                    "contract_token": contract_token,
                    "success": True,
                    "message": "Direct debit already cancelled.",
                },
                status=status.HTTP_200_OK,
            )

        with transaction.atomic():
            previous_payment_type = contract.payment.type

            contract.payment.type = target_payment_type
            contract.payment.save()

            ContractLog.objects.create(
                contract=contract,
                field_name="payment_type",
                old_value=(
                    previous_payment_type.token if previous_payment_type else "None"
                ),
                new_value=target_payment_type.token,
                operation_token=(
                    f"LOG_{contract.token}_"
                    f"{ContractLog.objects.filter(contract=contract).count() + 1}"
                ),
                user=request.user,
            )

            ContractObservation.objects.create(
                contract=contract,
                observation=(
                    "Cancelación de domiciliación solicitada desde la Oficina Virtual:\n"
                    f"period = {serializer.validated_data['period']}\n"
                    f"role = {serializer.validated_data['role']}"
                ),
                user=request.user,
            )

        logger.info(
            f"Direct debit cancelled for contract {contract_token}: "
            f"period={serializer.validated_data['period']}, "
            f"role={serializer.validated_data['role']}, "
            f"new_payment_type={target_payment_type.token}"
        )

        return Response(
            {
                "contract_token": contract_token,
                "success": True,
                "message": "Direct debit cancelled successfully.",
            },
            status=status.HTTP_200_OK,
        )


class ContactDataOVView(APIView):
    """GET /ov/contact-data/?contract_token=<token>

    Configuración del perfil: devuelve los datos de facturación y
    contacto del contrato (igual que `/ov/billing-data/`) más
    `holder_address`, la dirección postal del titular del contracte.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)

        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = ContactDataOVSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BatchInvoiceDownloadView(APIView):
    """POST /ov/invoices/download/?contract_token=<token>

    Descarga en lote: cos JSON `{"invoice_tokens": [...]}` → ZIP amb un PDF
    per factura. Reutilitza el PDF arxivat i, si no està disponible,
    `generate_report_invoice_pdf` (el mateix servei que `/ov/invoice-pdf/`)
    amb `save_pdf=False`, sense registrar documents ni tocar `invoice_file`.
    Seguretat IDOR: totes les fitxes han de pertanyer al contracte indicat
    i han de ser definitives
    (`type_final`), mateix filtre que la descàrrega individual.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        contract_token = request.query_params.get("contract_token", None)

        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response(
                {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = BatchInvoiceDownloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file_type_value = ConfigProject.objects.filter(
            token="invoice_type_invoice_token"
        ).first().value
        tokens = serializer.validated_data["invoice_tokens"]

        invoices = Invoice.objects.filter(
            token__in=tokens,
            contract__token=contract_token,
            type_final=file_type_value,
        )
        found = {invoice.token for invoice in invoices}
        missing = [token for token in tokens if token not in found]
        if missing:
            # Missatge genèric: no revela si la fitxa existeix en un altre contracte.
            return Response(
                {
                    "invoice_tokens": [
                        f"Invoice not found for this contract: {token}"
                        for token in missing
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        by_token = {invoice.token: invoice for invoice in invoices}
        ordered = [by_token[token] for token in tokens]

        buffer = BytesIO()
        try:
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                used_names = set()
                for invoice in ordered:
                    pdf_bytes = None
                    if invoice.invoice_file:
                        try:
                            response = download_document(invoice.invoice_file)
                            if response is not None:
                                pdf_bytes = response.content
                        except Exception:
                            logger.warning(
                                "Could not retrieve stored PDF for invoice %s", invoice.id
                            )
                    if pdf_bytes is None:
                        _, _, pdf_buffer = generate_report_invoice_pdf(
                            invoice,
                            request,
                            context={"request": request},
                            save_pdf=False,
                        )
                        pdf_bytes = pdf_buffer.getvalue()
                    raw_name = str(
                        invoice.serie_final or invoice.token or invoice.id
                    )
                    # Noms nets dins del ZIP: cap barra (el `serie_final` pot
                    # portar «/» com a separador de camps) ni contrabarra,
                    # perquè no es creïn subcarpetes ni risc de zip-slip.
                    safe_name = (
                        raw_name.replace("/", "-").replace("\\", "-").strip("-")
                        or str(invoice.id)
                    )
                    name = f"factura_{safe_name}.pdf"
                    if name in used_names:
                        name = f"factura_{safe_name}_{invoice.id}.pdf"
                    used_names.add(name)
                    zip_file.writestr(name, pdf_bytes)
        except Exception as e:
            logger.exception("Error inesperat")
            return Response(
                {"error": "Failed to retrieve invoice PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return _download_response(buffer.getvalue(), "application/zip", "facturas.zip")


class ContractStatusDictionaryOVView(APIView):
    """GET /ov/dictionary/contract-statuses/

    Diccionari d'estats de contracte perquè el frontal extern reompli
    selectors i tradueixi tokens sense hardcodejar-los. Retorna `token` i
    `name` de cada estat, ordenats per `position` (ordre de presentació del
    PA).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        statuses = ContractStatus.objects.all().order_by("position")
        return Response(
            ContractStatusDictionarySerializer(statuses, many=True).data
        )


class PaymentTypeDictionaryOVView(APIView):
    """GET /ov/dictionary/payment-types/

    Diccionari de formes de pagament (`token`, `name`), ordenat per
    `position`.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment_types = PaymentType.objects.all().order_by("position")
        return Response(
            PaymentTypeDictionarySerializer(payment_types, many=True).data
        )


class InvoiceStatusDictionaryOVView(APIView):
    """GET /ov/dictionary/invoice-statuses/

    Diccionari d'estats de factura (`token`, `name`), ordenat per
    `position`. Els tokens són els mateixos que accepta el filtre `statuses`
    de `/ov/unpayed-invoices/`.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        statuses = InvoiceStatus.objects.all().order_by("position")
        return Response(
            InvoiceStatusDictionarySerializer(statuses, many=True).data
        )


class ContractRequestTypeDictionaryOVView(APIView):
    """GET /ov/dictionary/contract-request-types/

    Diccionari de tipus de sol·licitud de contracte: només els actius,
    ordenats alfabèticament per `name`. Per cada tipus retorna `token`,
    `name`, `has_persons` i les tarifes actives associades
    (`registration_tariffs`, `water_tariffs`, `change_of_name_tariffs`, cada
    una amb `token` i `name`; `[]` si no n'hi ha). El `token` és el que cal
    enviar com a `procedure_type_token` en sol·licitar un tràmit.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Mateixa resolució que `PriceRateDictionarySerializer.get_name`:
        # nom genèric ("GENERAL") o buit -> nom del producte; així l'ordre
        # coincideix amb el nom que es mostra.
        """Return active request types ordered by name and ID, with active tariffs.

        Each tariff list is ordered by its display name and ID and is empty
        when no active tariffs are associated with that request type.
        """
        resolved_rate_name = Case(
            When(
                Q(name__isnull=True)
                | Q(name__regex=r"^\s*$")
                | Q(name__iregex=r"^\s*general\s*$"),
                then=F("product__name"),
            ),
            default=F("name"),
        )

        def active_rates(relation, to_attr):
            """Prefetch active tariffs from relation into the list named by to_attr,
            ordered by display name and ID."""
            return Prefetch(
                relation,
                queryset=PriceRate.objects.filter(is_active=True)
                .select_related("product")
                .annotate(display_name=resolved_rate_name)
                .order_by("display_name", "id"),
                to_attr=to_attr,
            )

        request_types = (
            ContractRequestType.objects.filter(is_active=True)
            .order_by("name", "id")
            .prefetch_related(
                active_rates(
                    "registration_price_rates", "active_registration_tariffs"
                ),
                active_rates("price_rates", "active_water_tariffs"),
                active_rates(
                    "change_of_name_registration_price_rates",
                    "active_change_of_name_tariffs",
                ),
            )
        )
        return Response(
            ContractRequestTypeDictionarySerializer(
                request_types, many=True
            ).data
        )


# Tokens d'origen (`ProductOrigin.token`) dels productes de tràmit/d'altes
# (drets d'alta, connexió, comptador, pòlissa, dipòsit...). Exclou els orígens
# de serveis periòdics recurrents (`aigua`, `subministrament`).
PROCEDURE_TARIFF_ORIGIN_TOKENS = ("contracte",)


class ProcedureTariffDictionaryOVView(APIView):
    """GET /ov/dictionary/procedure-tariffs/

    Catàleg de tarifes de tràmit actives (`is_active=True`) amb el seu cost
    per calcular els tràmits: `type_price` (`fixed`/`variable`), `price`
    (suma dels components fixos), `price_table` (taula de trams per calibre o
    consum) i `components` amb el desglossament complet. Ordenat per `name`.

    La consulta parteix de `Product`, restringit als orígens de tràmit
    (`contracte`, `escomesa`, `altres`), i recull les seves tarifes actives:
    no inclou serveis periòdics recurrents (`aigua`, `subministrament`) ni
    tarifes sense producte associat.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_rates = PriceRate.objects.filter(is_active=True).select_related(
            "billing_range_active"
        ).prefetch_related(
            "billing_range_active__line_item_types__price_interval"
            "__price_interval_stretches",
            "billing_range_active__line_item_types__price_variable"
            "__price_variable_interval_stretches",
        )
        products = Product.objects.filter(
            origin__token__in=PROCEDURE_TARIFF_ORIGIN_TOKENS
        ).prefetch_related(Prefetch("price_rates", queryset=active_rates))
        tariffs = sorted(
            (rate for product in products for rate in product.price_rates.all()),
            key=lambda rate: rate.name or "",
        )
        return Response(
            ProcedureTariffDictionarySerializer(tariffs, many=True).data
        )


_PROPERTY_SEARCH_SPLIT = re.compile(r"[\s,.;/]+")


def _property_search_tokens(search):
    return [token for token in _PROPERTY_SEARCH_SPLIT.split(search) if token]


class PropertiesOVView(APIView):
    """GET /ov/properties/?search=<text>[&page=<n>&limit=<n>]

    Autocompletat d'adreces de propietats existents perquè l'abonat pugui
    iniciar tràmits. `search` és obligatori i ha de tenir com a mínim 3
    caràcters (400 si no) per evitar escanejos complets a cada tecla. La
    puntuació (espais, `, . ; /`) es tracta com a separador: cada paraula
    ha de coincidir amb algun camp (carrer, número, ciutat, codi postal,
    nom o cadastral). Així `CR.` troba les propietats del tipus de carrer
    `CR` i `CR. Major 33` combina tots els termes amb AND. Els resultats
    es retornen paginats amb l'embolcall habitual de l'OV.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = OVLimitPagination
    min_search_length = 3

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        if not search:
            return Response(
                {"error": "Search is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(search) < self.min_search_length:
            return Response(
                {"error": "Search must be at least 3 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tokens = _property_search_tokens(search)
        if not tokens:
            return Response(
                {"error": "Search must contain at least one valid term"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = Q()
        for token in tokens:
            token_filters = (
                Q(address_street__name__icontains=token)
                | Q(address_street__name_2__icontains=token)
                | Q(address_street__type__abbreviation__icontains=token)
                | Q(address_city__name__icontains=token)
                | Q(address_postal_code__code__icontains=token)
                | Q(name__icontains=token)
                | Q(cadastral__icontains=token)
            )
            try:
                token_filters |= Q(address_street_number__number=int(token))
            except ValueError:
                pass
            filters &= token_filters

        properties = (
            Property.objects.filter(is_active=True)
            .filter(filters)
            .select_related(
                "address_street",
                "address_street_number",
                "address_postal_code",
                "address_city",
            )
            .order_by("address_street__name", "address_street_number__number")
        )

        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(properties, request, view=self)
        except NotFound:
            return Response(
                {"error": "Invalid page"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PropertyItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


_PERSON_DNI_SEPARATORS = re.compile(r"[\s.\-]+")


def _normalize_person_dni(value):
    """Normalitza un DNI/NIF per comparar-lo amb les dades heretades de la BD:
    ignora espais, guions i punts i el passa a majúscules."""
    return _PERSON_DNI_SEPARATORS.sub("", value or "").upper()


def _normalized_dni_expression(field):
    """Expressió SQL equivalent a `_normalize_person_dni` per al camp indicat:
    `UPPER(REPLACE(REPLACE(REPLACE(field, '-', ''), '.', ''), ' ', ''))`."""
    expression = Replace(field, Value("-"), Value(""))
    expression = Replace(expression, Value("."), Value(""))
    expression = Replace(expression, Value(" "), Value(""))
    return Upper(expression)


class PersonDataOVView(APIView):
    """GET /ov/person-data/?dni=<DNI>

    Dades de contacte de la persona identificada pel DNI: telèfons, correus
    i adreces, incloent-hi les files inactives (amb `is_active` a cada
    element). No depèn de cap contracte perquè el frontal OV el fa servir
    globalment (preomplert de formularis, verificació per SMS OTP, etc.).

    L'aplicació OV autentica un únic compte de servei, així que la persona
    s'identifica amb el paràmetre `dni` (igual que `/ov/contracts/`). El DNI
    es normalitza ignorant espais, guions i punts (i passant-lo a
    majúscules), perquè a la BD hi ha tokens heretats en minúscules o amb
    guions.

    La resolució és: primer `Person.token`; si no hi ha cap coincidència, el
    DNI de la compte bancària (`PersonBank.dni`), que és com s'identifiquen
    els pagadors. El token de la persona també ha de coincidir amb el DNI.
    Quan diverses persones comparteixen token, es prefereix la que té més
    contactes (útil per a l'OTP) i, a igualtat, la de menor `id`.
    Retorna `400` si falta el DNI i `404` si no es troba cap persona.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [PersonDataThrottle]

    def get(self, request):
        dni = _normalize_person_dni(request.query_params.get("dni"))
        if not dni:
            return Response(
                {"error": "DNI is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        person_id = (
            Person.objects.annotate(
                normalized_token=_normalized_dni_expression("token"),
                contact_count=Count("contacts"),
            )
            .filter(normalized_token=dni)
            .order_by("-contact_count", "id")
            .values_list("id", flat=True)
            .first()
        )

        if person_id is None:
            person_id = (
                PersonBank.objects.annotate(
                    normalized_dni=_normalized_dni_expression("dni"),
                    normalized_token=_normalized_dni_expression("person__token"),
                    contact_count=Count("person__contacts"),
                )
                .filter(normalized_dni=dni, normalized_token=dni, person__isnull=False)
                .order_by("-contact_count", "id")
                .values_list("person_id", flat=True)
                .first()
            )

        if person_id is None:
            return Response(
                {"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND
            )

        person = (
            Person.objects.filter(pk=person_id)
            .prefetch_related(
                Prefetch(
                    "contacts",
                    queryset=PersonContact.objects.order_by("-is_default", "id"),
                ),
                Prefetch(
                    "addresses",
                    queryset=PersonAddress.objects.select_related(
                        "address__street",
                        "address__street_number",
                        "address__city",
                    ).order_by("-is_billing", "-is_active", "id"),
                ),
            )
            .first()
        )

        serializer = PersonDataSerializer(person)
        return Response(serializer.data, status=status.HTTP_200_OK)


QUICK_PAY_NON_PAYABLE_STATUS_CONFIG_TOKENS = [
    "invoice_status_paid_token",
    "invoice_status_pending_token",
    "invoice_status_cancelled_token",
    "invoice_status_dropped_token",
    "invoice_status_payoff_token",
    "invoice_status_irrecoverable_token",
    "invoice_status_part_irrecoverable_token",
]


def _quick_pay_non_payable_status_tokens(paid_payment_status_token):
    configured_values = dict(
        ConfigProject.objects.filter(
            token__in=QUICK_PAY_NON_PAYABLE_STATUS_CONFIG_TOKENS
        )
        .values_list("token", "value")
    )
    if (
        not configured_values.get("invoice_status_paid_token")
        or not paid_payment_status_token
        or not PaymentStatus.objects.filter(token=paid_payment_status_token).exists()
    ):
        return None
    return {value for value in configured_values.values() if value}


class QuickPayOVView(APIView):
    """Resolve an invoice from the three printed data points without writes.

    The external OV collects the contract number, the invoice number
    (`Invoice.serie_final`) and the exact printed total (`Invoice.total_final`),
    charges the card with its own TPV and then confirms the payment through the
    existing `POST /ov/invoice/paid/` endpoint. This view only looks the invoice
    up: it never creates or updates `Payment` rows.

    A mismatch on any of the three fields (or a non-definitive document type)
    returns the same 404 so the endpoint cannot be used as a partial-match
    oracle. Once all three fields match, a non-payable status returns 409 with
    the current status so the frontend can explain the situation.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [QuickPayThrottle]

    def post(self, request):
        serializer = QuickPayRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        invoice_type_token = (
            ConfigProject.objects.filter(token="invoice_type_invoice_token")
            .values_list("value", flat=True)
            .first()
        )

        invoice = (
            Invoice.objects.select_related("contract", "status")
            .filter(
                contract__token=data["contract_number"],
                serie_final=data["invoice_number"],
                type_final=invoice_type_token,
                total_final=data["amount"],
            )
            .first()
        )

        if invoice is None:
            return Response(
                {"error": "Invoice not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        status_payload = (
            {"token": invoice.status.token, "name": invoice.status.name}
            if invoice.status is not None
            else None
        )

        paid_payment_status_token = (
            ConfigProject.objects.filter(token="payment_status_paid_token")
            .values_list("value", flat=True)
            .first()
        )
        non_payable_status_tokens = _quick_pay_non_payable_status_tokens(
            paid_payment_status_token
        )
        payable = (
            non_payable_status_tokens is not None
            and invoice.status is not None
            and invoice.status.token not in non_payable_status_tokens
            and (invoice.left_to_pay or 0) > 0
            and invoice.payments.exclude(status__token=paid_payment_status_token).exists()
        )

        if not payable:
            return Response(
                {
                    "error": "Invoice is not payable",
                    "status": status_payload,
                    "left_to_pay": invoice.left_to_pay,
                },
                status=status.HTTP_409_CONFLICT,
            )

        payload = {
            "contract_token": invoice.contract.token,
            "invoice_token": invoice.token,
            "invoice_number": invoice.serie_final,
            "issue_date": invoice.issue_date,
            "due_date": invoice.due_date,
            "invoice_amount": invoice.total_final,
            "left_to_pay": invoice.left_to_pay,
            "status": status_payload,
            "payable": True,
        }

        return Response(
            QuickPayResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )


def _resolve_payment_receipt_language(request):
    """Language for the OV payment receipt: `?lang=` wins over the request's
    `Accept-Language`, and both fall back to Catalan. Values may carry a region
    or a different case (`ES`, `es-ES`, `es_ES` → `es`). Admin/ERP callers of
    `render_payment_proof_pdf` do not go through here and keep the template's
    Catalan default.
    """
    supported = {code.lower() for code, _name in settings.LANGUAGES}
    requested = (request.query_params.get("lang") or "").strip().lower()
    for candidate in (
        requested,
        translation.get_language_from_request(request),
    ):
        if not candidate:
            continue
        normalized = candidate.replace("_", "-").split("-")[0]
        if normalized in supported:
            return normalized
    return "ca"


class PaymentReceiptOVView(APIView):
    """GET /ov/payment-receipt/?contract_token=&payment_token=&dni=

    Returns the in-memory PDF proof of payment ("Justificant de pagament") for
    a cash or physical-POS payment made at the office, base64-encoded inside a
    JSON payload (`pdf_base64`). Online payments
    (`TPV_ONLINE`) are excluded because the OV issues its own receipts, and
    direct debit/bank payments have no receipt at all.

    Only invoice-backed payments with a definitive invoice (`type_final`) are
    accepted. The payment must belong to the given contract and the supplied
    DNI must match the payer, the customer, the contract holder or the
    direct-debit account holder. Every mismatch returns the same 404 so the
    endpoint cannot be used to probe which payment tokens exist.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentReceiptThrottle]

    @staticmethod
    def _payment_dni_candidates(payment):
        candidates = {
            payment.payer_token_final,
            payment.customer_token_final,
        }
        invoice = payment.invoice
        contract = invoice.contract if invoice else None
        if contract:
            if contract.holder:
                candidates.add(contract.holder.token)
            general_payment = contract.payment
            if general_payment and general_payment.IBAN:
                iban = general_payment.IBAN
                candidates.add(iban.dni)
                if iban.person:
                    candidates.add(iban.person.token)
        return {
            _normalize_person_dni(candidate)
            for candidate in candidates
            if candidate
        }

    def get(self, request):
        contract_token = (request.query_params.get("contract_token") or "").strip()
        payment_token = (request.query_params.get("payment_token") or "").strip()
        dni = _normalize_person_dni(request.query_params.get("dni"))

        if not contract_token or not payment_token:
            return Response(
                {"error": "Contract token and payment token are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not dni:
            return Response(
                {"error": "DNI is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paid_status_token = (
            ConfigProject.objects.filter(token="payment_status_paid_token")
            .values_list("value", flat=True)
            .first()
        )
        invoice_type_token = (
            ConfigProject.objects.filter(token="invoice_type_invoice_token")
            .values_list("value", flat=True)
            .first()
        )

        if not paid_status_token or not invoice_type_token:
            return Response(
                {"error": "Payment receipt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = (
            Payment.objects.select_related(
                "status",
                "invoice",
                "invoice__contract",
                "invoice__contract__holder",
                "invoice__contract__payment__IBAN__person",
                "invoice__exploitation",
                "invoice__exploitation__company",
            )
            .filter(
                token=payment_token,
                payment_type_token__in=("CASH", "CARD"),
                status__token=paid_status_token,
                is_active=True,
                is_excluded=False,
                is_duplicate=False,
                payment_date__isnull=False,
                invoice__isnull=False,
                invoice__contract__token=contract_token,
                invoice__type_final=invoice_type_token,
            )
            .first()
        )

        if payment is None or dni not in self._payment_dni_candidates(payment):
            return Response(
                {"error": "Payment receipt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment_type_name = (
            PaymentType.objects.filter(token=payment.payment_type_token)
            .values_list("name", flat=True)
            .first()
        )

        from billing.utils.payment_proof_service import render_payment_proof_pdf

        language = _resolve_payment_receipt_language(request)

        try:
            with translation.override(language):
                method_name = {
                    "CASH": _("Efectiu"),
                    "CARD": _("Targeta (TPV Físic)"),
                }.get(payment.payment_type_token)
                if not method_name:
                    method_name = (
                        payment_type_name or payment.payment_type_token or ""
                    )
                observation = f"{_('Forma de pagament')}: {method_name}"
                pdf_buffer, _filename = render_payment_proof_pdf(
                    [payment],
                    request,
                    payment_date=payment.payment_date.strftime("%Y-%m-%d"),
                    observation=observation,
                    language=language,
                )
        except ValueError:
            return Response(
                {"error": "Payment receipt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            logger.exception("Error generating payment receipt PDF")
            return Response(
                {"error": "PDF generation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        pdf_buffer.seek(0)
        pdf_base64 = base64.b64encode(pdf_buffer.read()).decode("ascii")
        response = Response({"pdf_base64": pdf_base64})
        response["Cache-Control"] = "no-store"
        response["Content-Language"] = language
        return response


RETURN_REQUEST_INCIDENT_NAME = "Sol·licitud de devolució"


class InvoiceReturnRequestOVView(APIView):
    """POST /ov/invoice/return-request/

    Opens an automatic incident ("incidencia") so customer service can track a
    return requested by the customer. It deliberately does **not** change the
    invoice status, `left_to_pay` or any payment: the invoice only goes back to
    confirmed/expired days later when the bank processes the return file, which
    is handled by the existing `manage_rejection_payments` flow.

    The request is accepted only for a definitive invoice that belongs to the
    supplied contract and whose status is paid. The paid status token is the
    single source of truth: `left_to_pay` is not used to decide, because the
    payment signal updates the status when the invoice is settled but
    deliberately leaves `left_to_pay` untouched, so it can be stale (or NULL)
    on genuinely paid invoices. The same `404` is returned for a
    missing invoice, a proforma and a wrong contract, so the endpoint cannot be
    used as a partial-match oracle.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ReturnRequestThrottle]

    def post(self, request):
        serializer = ReturnRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        invoice_token = data["invoice_token"]
        contract_token = data["contract_token"]
        reason = data["reason"]

        config = dict(
            ConfigProject.objects.filter(
                token__in=(
                    "invoice_status_paid_token",
                    "invoice_type_invoice_token",
                    "payment_status_returned_token",
                )
            ).values_list("token", "value")
        )
        paid_status_token = config.get("invoice_status_paid_token")
        invoice_type_token = config.get("invoice_type_invoice_token")
        returned_status_token = config.get("payment_status_returned_token")

        if not paid_status_token or not invoice_type_token:
            return Response(
                {"error": "Invoice not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        invoice = (
            Invoice.objects.select_related("contract", "status")
            .filter(
                token=invoice_token,
                contract__token=contract_token,
                type_final=invoice_type_token,
            )
            .exclude(status__token="1")
            .first()
        )

        if invoice is None:
            return Response(
                {"error": "Invoice not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        status_payload = (
            {"token": invoice.status.token, "name": invoice.status.name}
            if invoice.status is not None
            else None
        )

        if returned_status_token and invoice.payments.filter(
            status__token=returned_status_token,
            is_active=True,
        ).exists():
            return Response(
                {
                    "error": "Invoice already returned",
                    "status": status_payload,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if (
            invoice.status is None
            or invoice.status.token != paid_status_token
        ):
            return Response(
                {
                    "error": "Invoice is not paid",
                    "status": status_payload,
                },
                status=status.HTTP_409_CONFLICT,
            )

        open_incident = (
            Incident.objects.filter(
                invoice=invoice,
                type__token="reclamacio",
                name=RETURN_REQUEST_INCIDENT_NAME,
                is_active=True,
            )
            .exclude(status__token="2")
            .first()
        )
        if open_incident is not None:
            return Response(
                {
                    "error": "Return request already exists",
                    "incident_token": open_incident.token,
                },
                status=status.HTTP_409_CONFLICT,
            )

        default_status = IncidentStatus.objects.filter(
            is_default=True
        ).first()
        incident_type = IncidentType.objects.filter(token="reclamacio").first()
        if default_status is None or incident_type is None:
            logger.error(
                "Return request cannot be created: incident dictionaries missing"
            )
            return Response(
                {"error": "Return request could not be created"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        with transaction.atomic():
            incident = Incident.objects.create(
                token=check_token_exists(generate_token(Incident), Incident),
                name=RETURN_REQUEST_INCIDENT_NAME,
                description=reason,
                contract=invoice.contract,
                invoice=invoice,
                status=default_status,
                type=incident_type,
                is_active=True,
            )
            LogIncidentStatusChange.objects.create(
                object=incident,
                current_status=default_status,
                observation=reason,
                user=request.user,
            )

        payload = {
            "incident_token": incident.token,
            "invoice_token": invoice.token,
            "contract_token": invoice.contract.token,
            "status": {
                "token": default_status.token,
                "name": default_status.name,
            },
            "type": {
                "token": incident_type.token,
                "name": incident_type.name,
            },
            "created_at": incident.created_at,
        }
        return Response(
            ReturnRequestResponseSerializer(payload).data,
            status=status.HTTP_201_CREATED,
        )


CONTRACT_PROCEDURE_CLOSED_STATUS_TOKENS = ("-1", "3")
CONTRACT_PROCEDURE_REQUIRED_PAYMENT_FIELDS = (
    "iban",
    "iban_holder_name",
    "iban_holder_dni",
    "iban_holder_swift",
)


def _resolve_contract_procedure_person(dni):
    """Resol una persona a partir del DNI normalitzat.

    Replica la resolució de `PersonDataOVView`: primer `Person.token` i, si no
    hi ha coincidència, el DNI de la compte bancària (`PersonBank.dni`), que és
    com s'identifiquen els pagadors. El token de la persona també ha de coincidir
    amb el DNI. Així l'OV rep el mateix resultat que en el preomplert de
    `GET /ov/person-data/`.
    """
    person_id = (
        Person.objects.annotate(
            normalized_token=_normalized_dni_expression("token"),
            contact_count=Count("contacts"),
        )
        .filter(normalized_token=dni)
        .order_by("-contact_count", "id")
        .values_list("id", flat=True)
        .first()
    )

    if person_id is None:
        person_id = (
            PersonBank.objects.annotate(
                normalized_dni=_normalized_dni_expression("dni"),
                normalized_token=_normalized_dni_expression("person__token"),
                contact_count=Count("person__contacts"),
            )
            .filter(normalized_dni=dni, normalized_token=dni, person__isnull=False)
            .order_by("-contact_count", "id")
            .values_list("person_id", flat=True)
            .first()
        )

    if person_id is None:
        return None
    return Person.objects.filter(pk=person_id).first()


def _generate_contract_request_token(is_change_of_name=False):
    """Return a contract request token using the back office generation rules.

    is_change_of_name is passed to the personalized generator when installed;
    otherwise it has no effect on the standard token generation service.
    """
    using_personalized = getattr(
        name_utils_module.generate_token, "__module__", ""
    ).endswith("name_utils_personalized")
    if using_personalized:
        return check_token_exists(
            generate_token(
                ContractRequest,
                use_type_id=None,
                client_type_id=None,
                company_id=None,
                is_change_of_name=is_change_of_name,
            ),
            ContractRequest,
        )
    return generate_contract_request_token()


def _create_procedure_payment(holder, payment_type, bank_fields):
    """Crea la forma de pagament d'un tràmit d'alta: `PersonBank` (només si
    s'han informat dades bancàries) i `GeneralPayment`. S'ha de cridar dins la
    transacció del tràmit. Retorna `(person_bank, general_payment)`."""
    person_bank = None
    if any(bank_fields.values()):
        person_bank = PersonBank.objects.create(
            token=check_token_exists(generate_token(PersonBank), PersonBank),
            person=holder,
            iban=bank_fields["iban"] or None,
            swift=bank_fields["iban_holder_swift"] or None,
            name=bank_fields["iban_holder_name"] or None,
            dni=bank_fields["iban_holder_dni"] or None,
            is_default=True,
            is_active=True,
        )
    general_payment = GeneralPayment.objects.create(
        token=check_token_exists(generate_token(GeneralPayment), GeneralPayment),
        type=payment_type,
        IBAN=person_bank,
        is_active=True,
    )
    return person_bank, general_payment


class ContractProcedureOVView(APIView):
    """POST /ov/procedures/contract/

    Creates a **contract request** (`ContractRequest`) for a new supply
    contract, to be finalized by customer service. It deliberately does not
    create a `Contract`, approve anything, or generate orders: the request is
    left in the default (draft) status so CS completes the remaining data
    (meter, registration date, billing address, ...) and finalizes it through
    the existing flow.

    The tariff (`tariff_token`) is the one the Virtual Office showed and
    charged to the customer, so it is authoritative for the request. We do not
    let the procedure type derive it: `ContractRequestType.price_rates` is an
    M2M that may hold zero, one or many tariffs and is unrelated to the active
    tariff catalogue the OV exposes, so deriving it would risk billing
    mismatches. `registration_price_rates` and `order_types` remain
    type-driven, which is the correct behaviour for them.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ContractProcedureThrottle]

    def post(self, request):
        """Create a request in the default status with payment and tariff records.

        Return 201 with request details and a masked IBAN. Invalid input or an
        ambiguous supply point returns 400; missing people, properties, supply
        points, or dictionary entries return 404. An existing open request for
        the supply point returns 409; a missing default status
        returns 500. Exceptions during creation propagate and roll back the
        transaction's writes.
        """
        serializer = ContractProcedureRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        holder_dni = _normalize_person_dni(data["holder_dni"])
        if not holder_dni:
            return Response(
                {"error": "DNI is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        holder = _resolve_contract_procedure_person(holder_dni)
        if holder is None:
            return Response(
                {"error": "Person not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        prop = Property.objects.filter(
            token=data["property_token"], is_active=True
        ).first()
        if prop is None:
            return Response(
                {"error": "Property not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        supply_points = SupplyPoint.objects.filter(
            property=prop, is_active=True
        )
        supply_point_token = data.get("supply_point_token")
        if supply_point_token:
            supply_points = supply_points.filter(token=supply_point_token)
        supply_points = list(supply_points[:2])
        if not supply_points:
            return Response(
                {"error": "Supply point not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if len(supply_points) > 1:
            return Response(
                {"error": "supply_point_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        supply_point = supply_points[0]

        procedure_type = ContractRequestType.objects.filter(
            token=data["procedure_type_token"], is_active=True
        ).first()
        if procedure_type is None:
            return Response(
                {"error": "Procedure type not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        tariff = PriceRate.objects.filter(
            token=data["tariff_token"], is_active=True
        ).first()
        if tariff is None:
            return Response(
                {"error": "Tariff not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment_type = PaymentType.objects.filter(
            token=data["payment_type_token"]
        ).first()
        if payment_type is None:
            return Response(
                {"error": "Payment type not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if payment_type.token == "DIRECT_DEBIT":
            missing = {
                field: "This field is required for direct debit."
                for field in CONTRACT_PROCEDURE_REQUIRED_PAYMENT_FIELDS
                if not data.get(field)
            }
            if missing:
                return Response(
                    {"error": missing}, status=status.HTTP_400_BAD_REQUEST
                )

        existing_request = (
            ContractRequest.objects.filter(
                supply_point_default=supply_point,
                is_active=True,
            )
            .exclude(status__token__in=CONTRACT_PROCEDURE_CLOSED_STATUS_TOKENS)
            .order_by("-created_at")
            .first()
        )
        if existing_request is not None:
            return Response(
                {
                    "error": "Contract request already exists",
                    "contract_request_token": existing_request.token,
                },
                status=status.HTTP_409_CONFLICT,
            )

        default_status = ContractRequestStatus.objects.filter(
            is_default=True
        ).first()
        if default_status is None:
            logger.error(
                "Contract procedure cannot be created: default "
                "ContractRequestStatus missing"
            )
            return Response(
                {"error": "Contract procedure could not be created"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        bank_fields = {
            field: data.get(field)
            for field in CONTRACT_PROCEDURE_REQUIRED_PAYMENT_FIELDS
        }

        with transaction.atomic():
            person_bank, general_payment = _create_procedure_payment(
                holder, payment_type, bank_fields
            )

            contract_request = ContractRequest.objects.create(
                token=_generate_contract_request_token(),
                language=data.get("language") or settings.LANGUAGE,
                supply_point_default=supply_point,
                person=holder,
                holder=holder,
                type=procedure_type,
                payment=general_payment,
                status=default_status,
                requested_at=timezone.now(),
                is_active=True,
            )
            contract_request.supply_points.set([supply_point])

            contract_price_rate = ContractPriceRate.objects.filter(
                supply_point=supply_point, price_rate=tariff, is_active=True
            ).first()
            if contract_price_rate is None:
                contract_price_rate = ContractPriceRate.objects.create(
                    supply_point=supply_point, price_rate=tariff, is_active=True
                )
            contract_request.price_rates.set([contract_price_rate])
            contract_request.registration_price_rates.set(
                procedure_type.registration_price_rates.all()
            )
            contract_request.order_types.set(
                procedure_type.order_types.all()
            )

            LogContractRequestStatus.objects.create(
                object=contract_request,
                previous_status=None,
                current_status=default_status,
                observation=data.get("observation") or None,
                user=request.user,
            )

        payload = {
            "contract_request_token": contract_request.token,
            "status": {
                "token": default_status.token,
                "name": default_status.name,
            },
            "type": {
                "token": procedure_type.token,
                "name": procedure_type.name,
            },
            "person": {
                "token": holder.token,
                "name": holder.name,
            },
            "supply_point": {"token": supply_point.token},
            "payment": {
                "iban": mask_iban(person_bank.iban) if person_bank else "",
            },
            "created_at": contract_request.created_at,
        }
        return Response(
            ContractProcedureResponseSerializer(payload).data,
            status=status.HTTP_201_CREATED,
        )


class ContractRequestStatusOVView(APIView):
    """GET /ov/procedures/contract/<contract_request_token>/

    Estat de la sol·licitud d'alta de contracte per al seguiment des del
    frontal OV. `contract_token` és `null` mentre la sol·licitud estigui
    pendent (o sense contracte associat); un cop atenció al client l'ha
    aprovada i existeix el `Contract` enllaçat (`contract_request_id`)
    retorna el `token` del contracte. Respon 404 si la sol·licitud no
    existeix o no està activa.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ContractProcedureThrottle]

    def get(self, request, contract_request_token):
        contract_request = (
            ContractRequest.objects.select_related(
                "status", "type", "supply_point_default", "person"
            )
            .prefetch_related("contract")
            .filter(token=contract_request_token, is_active=True)
            .first()
        )
        if contract_request is None:
            raise NotFound({"error": "Contract request not found"})

        contract = next(iter(contract_request.contract.all()), None)
        payload = {
            "contract_request_token": contract_request.token,
            "status": (
                {
                    "token": contract_request.status.token,
                    "name": contract_request.status.name,
                }
                if contract_request.status
                else None
            ),
            "type": (
                {
                    "token": contract_request.type.token,
                    "name": contract_request.type.name,
                }
                if contract_request.type
                else None
            ),
            "contract_token": contract.token if contract else None,
            "created_at": contract_request.created_at,
            "supply_point": (
                {"token": contract_request.supply_point_default.token}
                if contract_request.supply_point_default
                else None
            ),
            "person": (
                {
                    "token": contract_request.person.token,
                    "name": contract_request.person.name,
                }
                if contract_request.person
                else None
            ),
        }
        return Response(ContractRequestStatusSerializer(payload).data)


# Fallbacks dels tokens d'estat de baixa tancada (finalitzada / cancel·lada)
# si el ConfigProject no els té definits: són els valors de les dades inicials.
CONTRACT_TERMINATION_CLOSED_STATUS_FALLBACKS = {
    "contract_termination_completed_token": "3",
    "contract_termination_cancelled_token": "-1",
}


def _config_project_value(token, default=None):
    """Return the first matching configuration value, or default if absent,
    null, or empty. Whitespace-only values are returned unchanged."""
    value = (
        ConfigProject.objects.filter(token=token)
        .values_list("value", flat=True)
        .first()
    )
    return value if value not in (None, "") else default


def _closed_contract_termination_status_tokens():
    """Tokens d'estat que donen una baixa per tancada (finalitzada i
    cancel·lada), llegits del ConfigProject amb fallback als valors inicials.
    Qualsevol altre estat (esborrany, pendent o sense estat) és una baixa
    oberta."""
    return [
        _config_project_value(token, default)
        for token, default in CONTRACT_TERMINATION_CLOSED_STATUS_FALLBACKS.items()
    ]


class ContractTerminationProcedureOVView(APIView):
    """POST /ov/procedures/contract-termination/

    Sol·licitud de baixa d'un contracte des de l'OV. Només crea una
    `ContractTerminationRequest` en l'estat per defecte (esborrany). El tipus
    (el "Motiu" del PA) és el `reason_token` si s'indica i, si no, el tipus
    per defecte de petició del client. El text lliure (`observation`) es desa
    com a observació de la baixa. Atenció al client la valida,
    organitza la lectura de tall i la finalitza des del PA. Per això:

    - no toca l'estat ni la data de baixa del contracte;
    - no recull lectures, fotos ni estimacions;
    - no es bloqueja per deute pendent ni emet factura de tancament.

    Només el titular pot demanar la baixa: el contracte ha d'estar actiu i el
    `holder_dni` ha de coincidir (normalitzat) amb el token del titular. Si no,
    es respon el mateix 404 que quan el contracte no existeix, perquè l'endpoint
    no serveixi per esbrinar quines combinacions són vàlides.

    El contracte es bloqueja (`select_for_update`) abans de comprovar si ja hi
    ha una baixa oberta, de manera que dues peticions simultànies no en poden
    crear dues.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ContractTerminationProcedureThrottle]

    def post(self, request):
        """Create a termination request and optional observation in the default status.

        Return 201 with the request token, contract token, status, type, and
        creation time. Invalid input returns 400; an unavailable contract or
        holder DNI mismatch returns 404. A terminated contract or an existing
        open termination returns 409. Missing default configuration returns
        500. Exceptions during creation propagate and roll back its writes.
        """
        serializer = ContractTerminationProcedureRequestSerializer(
            data=request.data
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        dni = _normalize_person_dni(data["holder_dni"])
        if not dni:
            return Response(
                {"error": "DNI is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        default_status = ContractTerminationStatus.objects.filter(
            is_default=True
        ).first()
        # Tipus triat pel caller (`reason_token`, sense restringir per
        # `is_change_of_name`); si no n'hi ha, el tipus per defecte de petició
        # del client (mai el de canvi de nom).
        termination_type = data["termination_type"]
        if termination_type is None:
            termination_type = ContractTerminationType.objects.filter(
                is_default=True, is_change_of_name=False
            ).first()
        if default_status is None or termination_type is None:
            logger.error(
                "OV contract termination: missing default %s",
                "status" if default_status is None else "type",
            )
            return Response(
                {"error": "Contract termination could not be created"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        terminated_status_token = _config_project_value(
            "contract_terminated_status"
        )
        closed_tokens = _closed_contract_termination_status_tokens()
        not_found = Response(
            {"error": "Contract not found"}, status=status.HTTP_404_NOT_FOUND
        )

        with transaction.atomic():
            # `of=("self",)`: només es bloqueja la fila del contracte (els joins
            # opcionals de titular i estat no admeten FOR UPDATE a PostgreSQL).
            contract = (
                Contract.objects.select_for_update(of=("self",))
                .select_related("holder", "status")
                .filter(token=data["contract_token"], is_active=True)
                .first()
            )
            if (
                contract is None
                or contract.holder is None
                or _normalize_person_dni(contract.holder.token) != dni
            ):
                return not_found

            if (
                terminated_status_token
                and contract.status is not None
                and contract.status.token == terminated_status_token
            ):
                return Response(
                    {"error": "Contract already terminated"},
                    status=status.HTTP_409_CONFLICT,
                )

            existing = (
                ContractTerminationRequest.objects.filter(
                    contract=contract, is_active=True
                )
                .exclude(status__token__in=closed_tokens)
                .order_by("-id")
                .first()
            )
            if existing is not None:
                return Response(
                    {
                        "error": "Contract termination already exists",
                        "contract_termination_token": existing.token,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            termination = ContractTerminationRequest.objects.create(
                token=check_token_exists(
                    generate_token(ContractTerminationRequest),
                    ContractTerminationRequest,
                ),
                contract=contract,
                person=contract.holder,
                type=termination_type,
                status=default_status,
                requested_at=timezone.now(),
                is_active=True,
            )
            observation_text = (data.get("observation") or "").strip()
            if observation_text:
                ContractTerminationRequestObservation.objects.create(
                    contract_termination=termination,
                    observation=observation_text,
                    status_name=default_status.name,
                    user=request.user,
                )

        logger.info(
            "OV contract termination request %s created", termination.token
        )
        payload = {
            "contract_termination_token": termination.token,
            "contract_token": contract.token,
            "status": {"token": default_status.token, "name": default_status.name},
            "type": {"token": termination_type.token, "name": termination_type.name},
            "created_at": termination.created_at,
        }
        return Response(
            ContractTerminationProcedureResponseSerializer(payload).data,
            status=status.HTTP_201_CREATED,
        )


class ContractChangeProcedureOVView(APIView):
    """POST /ov/procedures/contract-change/

    Canvi de nom (subrogació) des de l'OV. En una sola transacció crea, en
    estat per defecte (esborrany):

    - una `ContractTerminationRequest` del contracte actual (titular sortint),
      amb el tipus indicat a `outgoing.reason_token`;
    - una `ContractRequest` del nou titular amb `is_change_of_name=True` i
      `keep_same_code=False`, al mateix punt de subministrament, enllaçada a la
      baixa (`contract_termination_requests`).

    Com al PA, la sol·licitud hereta les tarifes periòdiques actives del
    contracte actual, rep les tarifes d'alta i tipus d'ordre de canvi de nom del
    tipus de tràmit i copia les variables traspassables. Atenció al client la
    valida i la finalitza; en crear el nou contracte, la baixa passa a pendent
    (`check_contract_terminations`) i el contracte actual es dona de baixa en
    finalitzar-la.

    Només el titular actual la pot demanar: contracte inexistent, inactiu,
    sense titular o d'un altre titular retornen el mateix 404. El contracte es
    bloqueja abans de comprovar conflictes; qualsevol error desfà tots els
    registres creats.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ContractChangeProcedureThrottle]

    def post(self, request):
        """Create linked termination and incoming holder requests atomically.

        Copy the contract's active tariffs and transferable variables, and
        create payment records and a status log. An omitted termination reason
        uses the change-of-name type ordered first by position (nulls last),
        then ID. Return 201 with both request tokens and their status details.
        Invalid input returns 400, missing people or a contract/holder mismatch
        returns 404, conflicts return 409, and missing default statuses or a
        fallback termination type returns 500. Exceptions during creation
        propagate and roll back the transaction's writes.
        """
        serializer = ContractChangeProcedureRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        outgoing = serializer.validated_data["outgoing"]
        incoming = serializer.validated_data["incoming"]

        outgoing_dni = _normalize_person_dni(outgoing["holder_dni"])
        incoming_dni = _normalize_person_dni(incoming["holder_dni"])
        dni_errors = {}
        if not outgoing_dni:
            dni_errors["outgoing"] = {"holder_dni": ["DNI is required."]}
        if not incoming_dni:
            dni_errors["incoming"] = {"holder_dni": ["DNI is required."]}
        if not dni_errors and outgoing_dni == incoming_dni:
            dni_errors["incoming"] = {
                "holder_dni": [
                    "The incoming holder must be different from the current holder."
                ]
            }
        if dni_errors:
            return Response(dni_errors, status=status.HTTP_400_BAD_REQUEST)

        incoming_holder = _resolve_contract_procedure_person(incoming_dni)
        if incoming_holder is None:
            return Response(
                {"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND
            )

        request_status = ContractRequestStatus.objects.filter(
            is_default=True
        ).first()
        termination_status = ContractTerminationStatus.objects.filter(
            is_default=True
        ).first()
        # Sense `reason_token`, el tipus de baixa és el de canvi de nom.
        # (`ContractTerminationType` no té `is_active`: qualsevol tipus marcat
        # com a canvi de nom és vàlid; si n'hi ha més d'un, el de menor
        # `position` i `id`.)
        termination_type = outgoing["termination_type"]
        if termination_type is None:
            termination_type = (
                ContractTerminationType.objects.filter(is_change_of_name=True)
                .order_by(F("position").asc(nulls_last=True), "id")
                .first()
            )
        if (
            request_status is None
            or termination_status is None
            or termination_type is None
        ):
            if request_status is None:
                missing = "default contract request status"
            elif termination_status is None:
                missing = "default termination status"
            else:
                missing = "change-of-name termination type"
            logger.error("OV contract change: missing %s", missing)
            return Response(
                {"error": "Contract change could not be created"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        terminated_status_token = _config_project_value(
            "contract_terminated_status"
        )
        closed_termination_tokens = _closed_contract_termination_status_tokens()
        procedure_type = incoming["procedure_type"]

        with transaction.atomic():
            contract = (
                Contract.objects.select_for_update(of=("self",))
                .select_related("holder", "status", "supply_point_default")
                .filter(token=outgoing["contract_token"], is_active=True)
                .first()
            )
            if (
                contract is None
                or contract.holder is None
                or _normalize_person_dni(contract.holder.token) != outgoing_dni
            ):
                return Response(
                    {"error": "Contract not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            conflict = self._conflict(
                contract, terminated_status_token, closed_termination_tokens
            )
            if conflict is not None:
                return Response(conflict, status=status.HTTP_409_CONFLICT)

            now = timezone.now()
            termination = ContractTerminationRequest.objects.create(
                token=check_token_exists(
                    generate_token(ContractTerminationRequest),
                    ContractTerminationRequest,
                ),
                contract=contract,
                person=contract.holder,
                type=termination_type,
                status=termination_status,
                requested_at=now,
                is_active=True,
            )
            if outgoing.get("observation"):
                ContractTerminationRequestObservation.objects.create(
                    contract_termination=termination,
                    observation=outgoing["observation"],
                    status_name=termination_status.name,
                    user=request.user,
                )

            _, general_payment = _create_procedure_payment(
                incoming_holder,
                incoming["payment_type"],
                {
                    field: incoming.get(field)
                    for field in CONTRACT_PROCEDURE_REQUIRED_PAYMENT_FIELDS
                },
            )

            supply_point = contract.supply_point_default
            contract_request = ContractRequest.objects.create(
                token=_generate_contract_request_token(is_change_of_name=True),
                language=incoming.get("language") or settings.LANGUAGE,
                supply_point_default=supply_point,
                person=incoming_holder,
                holder=incoming_holder,
                type=procedure_type,
                payment=general_payment,
                status=request_status,
                requested_at=now,
                is_change_of_name=True,
                keep_same_code=False,
                use_general_price_rates=contract.use_general_price_rates,
                is_active=True,
            )
            contract_request.supply_points.set(
                list(contract.supply_points.all()) or [supply_point]
            )
            # Tarifes periòdiques actives heretades del contracte actual; les
            # d'alta i els tipus d'ordre, els de canvi de nom del tipus de tràmit.
            # Còpies pròpies (no les mateixes files) de les tarifes actives del
            # contracte actual: així canviar-les a la sol·licitud o al nou
            # contracte (p. ex. la referència BOP) no altera l'historial del
            # contracte anterior.
            contract_request.price_rates.set(
                ContractPriceRate.objects.bulk_create(
                    [
                        ContractPriceRate(
                            token=source.token,
                            supply_point=source.supply_point,
                            price_rate=source.price_rate,
                            is_bop_reference=source.is_bop_reference,
                            is_active=True,
                        )
                        for source in contract.price_rates.filter(
                            is_active=True, price_rate__is_active=True
                        ).order_by("id")
                    ]
                )
            )
            contract_request.registration_price_rates.set(
                procedure_type.get_registration_price_rates(is_change_of_name=True)
            )
            contract_request.order_types.set(
                procedure_type.get_order_types(is_change_of_name=True)
            )
            from contract.utils.contract_service import (
                copy_change_of_name_variables,
            )

            copy_change_of_name_variables(contract_request)
            contract_request.contract_termination_requests.add(termination)

            LogContractRequestStatus.objects.create(
                object=contract_request,
                previous_status=None,
                current_status=request_status,
                observation=incoming.get("observation") or None,
                user=request.user,
            )

        logger.info(
            "OV contract change requested: contract request %s, termination %s",
            contract_request.token,
            termination.token,
        )
        payload = {
            "contract_request_token": contract_request.token,
            "contract_termination_token": termination.token,
            "contract_token": contract.token,
            "contract_request_status": {
                "token": request_status.token,
                "name": request_status.name,
            },
            "contract_termination_status": {
                "token": termination_status.token,
                "name": termination_status.name,
            },
            "procedure_type": {
                "token": procedure_type.token,
                "name": procedure_type.name,
            },
            "termination_type": {
                "token": termination_type.token,
                "name": termination_type.name,
            },
            "created_at": contract_request.created_at,
        }
        return Response(
            ContractChangeProcedureResponseSerializer(payload).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _conflict(contract, terminated_status_token, closed_termination_tokens):
        """Cos del 409 si el contracte no admet un canvi de nom; si no, `None`."""
        if (
            terminated_status_token
            and contract.status is not None
            and contract.status.token == terminated_status_token
        ):
            return {"error": "Contract already terminated"}

        open_termination = (
            ContractTerminationRequest.objects.filter(
                contract=contract, is_active=True
            )
            .exclude(status__token__in=closed_termination_tokens)
            .order_by("-id")
            .first()
        )
        if open_termination is not None:
            return {
                "error": "Contract termination already exists",
                "contract_termination_token": open_termination.token,
            }

        if contract.supply_point_default is None:
            return {"error": "Contract has no supply point"}

        open_request = (
            ContractRequest.objects.filter(
                Q(supply_point_default=contract.supply_point_default)
                | Q(supply_points=contract.supply_point_default),
                is_active=True,
            )
            .exclude(status__token__in=CONTRACT_PROCEDURE_CLOSED_STATUS_TOKENS)
            .order_by("-id")
            .first()
        )
        if open_request is not None:
            return {
                "error": "Contract request already exists",
                "contract_request_token": open_request.token,
            }
        return None

from django.http import FileResponse
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
import csv
import zipfile
import logging
from io import BytesIO, StringIO
from billing.views.invoice_pdf_view import generate_report_invoice_pdf
from coredata.utils.pdf_utils import merge_pdfs
from coredata.models import ConfigProject
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from contract.models import Contract, ContractLog, ContractObservation, PaymentType
from billing.models import Invoice, InvoiceStatus, Reading
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
    InvoiceFullDetailSerializer,
    MeterDetailSerializer,
    ConsumptionHistoryItemSerializer,
    ConsumptionDownloadRequestSerializer,
    BillingPeriodItemSerializer,
    SepaDocumentUploadSerializer,
    CancelDirectDebitSerializer,
    ContactDataOVSerializer,
)
from pagination.ov_pagination import OVLimitPagination, OVConsumptionPagination
from ov.throttles import DniEnumerationThrottle

logger = logging.getLogger(__name__)


class ContractOVView(APIView):
    """Alias legacy de `GET /ov/contract-detail/`.

    Redirige (302) al endpoint por token `contract-detail-by-token-ov`
    (`/ov/contract/{token}/`), conservando el resto de parámetros de query
    (p. ej. `dni`). No consulta la base de datos: la vista destino devuelve
    `404` si el contrato no existe.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        contract_token = request.query_params.get("contract_token", None)
        if not contract_token:
            return Response(
                {"error": "Contract token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query = request.query_params.copy()
        query.pop("contract_token", None)
        target = reverse("contract-detail-by-token-ov", kwargs={"token": contract_token})
        query_string = query.urlencode()
        if query_string:
            target = f"{target}?{query_string}"
        return redirect(target)


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
            return Response(
                {"error": f"Failed to update billing data: {str(e)}"},
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
            return Response(
                {"error": f"Failed to update IBAN: {str(e)}"},
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
        invoices = Invoice.objects.filter(contract=contract).exclude(
            status__token="1"
        )  # excluïm les factures de pre-factura

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

        # Validate statuses parameter (required)
        qp_statuses = request.query_params.get("statuses", None)
        if not qp_statuses:
            return Response(
                {"error": "Statuses are required"}, status=status.HTTP_400_BAD_REQUEST
            )

        status_tokens = [
            token.strip() for token in qp_statuses.split(",") if token.strip()
        ]
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
        )

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

        file_type_value = (
            ConfigProject.objects.filter(token="invoice_type_invoice_token")
            .first()
            .value
        )
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

        """ if not invoice.invoice_file:
            return Response(
                {"error": "Invoice PDF file not found"},
                status=status.HTTP_404_NOT_FOUND,
            ) """

        from documentmanager.utils.main_utils import download_document

        try:

            """http_response = download_document(invoice.invoice_file)

            pdf_bytes = http_response.content

            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")"""

            _, _, pdf_buffer = generate_report_invoice_pdf(
                invoice, request, context={"request": request}
            )
            pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")

            filename = (
                f"invoice_{invoice.serie_final}_{invoice.id}.pdf"
                if invoice.serie_final
                else f"invoice_{invoice.token}_{invoice.id}.pdf"
            )

            return Response(
                {
                    "pdf": pdf_base64,  # Base64-encoded PDF content
                    "filename": filename,  # Suggested filename for download
                    "document_name": invoice.invoice_file.document_name,  # Original document name
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            # Step 12: Handle any errors during document retrieval or conversion
            return Response(
                {"error": f"Failed to retrieve invoice PDF: {str(e)}"},
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
        queryset = Invoice.objects.exclude(status__token="1").select_related(
            "contract", "status"
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
                Reading.objects.filter(pk=id, meter=meter)
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

        queryset = queryset.select_related("previous_reading").prefetch_related(
            "invoices"
        ).order_by("-reading_date", "-id")

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


MOCK_BILLING_PERIODS = [
    {"year": 2026, "period_code": "1T", "months_label": "enero-marzo", "is_current": False},
    {"year": 2026, "period_code": "2T", "months_label": "abril-junio", "is_current": True},
]


class BillingPeriodsOVView(APIView):
    """GET /ov/billing-periods/?contract_token=<token>

    Devuelve los periodos de facturación disponibles para el contrato (ciclos
    definidos por el PA), para el selector de «Primera domiciliación» del
    frontal. Lista mock fija de 2 periodos mientras no se integre con el PA;
    el contrato se valida igual que en el resto de endpoints (`404` si no
    existe).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        contract_token = request.query_params.get("contract_token")
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

        serializer = BillingPeriodItemSerializer(MOCK_BILLING_PERIODS, many=True)
        return Response(serializer.data)


class SepaDocumentUploadView(APIView):
    """POST /ov/procedures/{contract_token}/upload-sepa-signed/

    Sube y archiva el mandato SEPA firmado de un contrato. Mock ligero:
    valida que el contrato exista (404 si no) y que el `iban` enviado
    coincida con el IBAN activo de la cuenta de domiciliación (400 si no
    coincide); archiva el documento de forma placeholder y devuelve 201
    con {"contract_token", "success": true}.
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
        active_iban = None
        if contract.payment and contract.payment.IBAN:
            active_iban = contract.payment.IBAN.iban
        if self._normalize_iban(uploaded_iban) != self._normalize_iban(active_iban):
            return Response(
                {
                    "error": "The IBAN does not match the contract's current active account."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        _ = serializer.validated_data["sepa"]

        logger.info(f"Mock archived signed SEPA mandate for contract {contract_token}")

        return Response(
            {"contract_token": contract_token, "success": True},
            status=status.HTTP_201_CREATED,
        )


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

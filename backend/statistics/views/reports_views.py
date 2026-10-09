# contract/views/contract_request_finalize_view.py
import datetime
from contextlib import contextmanager
from contextvars import ContextVar
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import F, Count, Sum, Q, Max
from django.db.models import Window
from django.db.models.functions import RowNumber
from billing.models import InvoiceLineItem
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.styles import PatternFill, Font
from openpyxl.styles.borders import Border, Side
from openpyxl.utils import get_column_letter
import os
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from billing.models import Billing, Invoice, Payment, PaymentRemittance
import string

from contract.models import Contract, PaymentType
from coredata.models import Bank, ConfigProject, Person
from documentmanager.utils.main_utils import upload_document
from django.utils.translation import gettext as _
from documentmanager.utils.export_jobs import enqueue_export, export_job_response
from order.models import Operator, Order, OrderReport
from pricing.models import LineItemType, Product
from pricing.serializers.product_serializer import ProductSerializer
from service.models import Company, SupplyPointType, Exploitation
from statistics.models import GeneralReport, ReportType
from statistics.permissions import ReportViewPermission
from statistics.tasks import *


row_letters = list(string.ascii_uppercase)
black_fill = PatternFill(start_color="000000", end_color="000000", fill_type="solid")
white_bold_font = Font(color="FFFFFF", bold=True)
light_gray_fill = PatternFill(start_color="ebebeb", end_color="ebebeb", fill_type="solid")
thin_border = Border(
    left=Side(style='thin', color='d3d3d3'),
    right=Side(style='thin', color='d3d3d3'),
    top=Side(style='thin', color='d3d3d3'),
    bottom=Side(style='thin', color='d3d3d3')
)

def column_to_excel_letter(column_index):
    letter = ""
    while column_index >= 0:
        letter = chr(column_index % 26 + ord('A')) + letter
        column_index = column_index // 26 - 1
    return letter

def add_row(sheet, row, items, fill=None, font=None, colored=None):
    row += 1
    for i, item in enumerate(items):
        column_letter = column_to_excel_letter(i)
        cell = sheet[f'{column_letter}{row}']
        cell.value = item
        if fill:
            cell.fill = fill
        if font:
            cell.font = font
        if colored:
            if i in colored:
                cell.fill = light_gray_fill
        if not fill:
            cell.border = thin_border
    return row
            
def jump_row(row):
    row+=2
    return row

def adjust_column_widths(sheet):
    for col in sheet.columns:
        max_length = 0
        # Find the first non-merged cell to get column letter
        column_letter = None
        for cell in col:
            try:
                if not isinstance(cell, openpyxl.cell.cell.MergedCell):
                    column_letter = cell.column_letter
                    break
            except:
                continue
        
        if not column_letter:
            continue
            
        for cell in col:
            try:
                if not isinstance(cell, openpyxl.cell.cell.MergedCell) and cell.value:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
            except:
                pass
                
        adjusted_width = (max_length + 5)
        sheet.column_dimensions[column_letter].width = adjusted_width

def filter_pending_invoices(invoices_queryset, request):
    """
    Filter out invoices with status.token equal to invoice_status_pending_token,
    unless include_preinvoices=true is in the request body.
    Also applies exclude_billing_id / exclude_billing_ids and serie_ids when present.
    """
    from statistics.utils.report_filters import apply_exclude_billing_ids, apply_serie_final_range, apply_serie_ids

    include_preinvoices = False
    data_value = request.data.get('include_preinvoices', False)
    if isinstance(data_value, bool):
        include_preinvoices = data_value
    elif isinstance(data_value, str):
        include_preinvoices = data_value.lower() == 'true'
    
    print("include_preinvoices: ", include_preinvoices)
    
    if not include_preinvoices:
        try:
            status_pending_token = ConfigProject.objects.get(token="invoice_status_pending_token").value
            invoices_queryset = invoices_queryset.filter(payments__is_active=True).exclude(status__token=status_pending_token).distinct()
        except ConfigProject.DoesNotExist:
            pass  # If config doesn't exist, don't filter
    
    # Always exclude invoices marked as is_excluded
    invoices_queryset = invoices_queryset.filter(is_excluded=False)

    # Exclude invoices belonging to specific billing(s), if requested
    invoices_queryset = apply_exclude_billing_ids(
        invoices_queryset, request.data, field='billing_id'
    )

    # Keep invoices whose serie_final starts with a selected InvoiceSequence prefix
    invoices_queryset = apply_serie_ids(
        invoices_queryset, request.data, field='serie_final'
    )

    # Rang de numero de factura (bloc "Filtres extra" de billing/reports/add, el
    # mateix filtre que billing/reports/general-billing-summary): nomes actua si el
    # payload porta serie_final_from/serie_final_to.
    invoices_queryset = apply_serie_final_range(invoices_queryset, request.data)

    return invoices_queryset

class ReportBillingActiveProducts(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def get(self, request, id):
        try:
            if not id:
                return Response({"error": "billing id is required."}, status=status.HTTP_400_BAD_REQUEST)
            billing = get_object_or_404(Billing, id=id)
            
            products = Product.objects.filter(line_items__invoice__billing=billing).distinct()
            serialized_products = ProductSerializer(products, many=True)
            return Response(serialized_products.data, status=status.HTTP_200_OK)
     
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportBillingSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            
            task = run_report_task.delay('get_report_billing_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ReportAccountingValuesSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('accounting_values_report', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportAquaRemittanceSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            
            task = run_report_task.delay('aqua_remittance_report', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportBailsReport(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            
            task = run_report_task.delay('bails_report', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportIncasolLiquidation(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:

            task = run_report_task.delay('incasol_liquidation_report', request.data)

            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)


        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportACASummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            version = request.data.get('version', 1)
            task = run_report_task.delay('aca_summary_report' if version == 1 else 'aca_summary_report_second_ver', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportWalletSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class ReportWalletBankList(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_bank_list', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class ReportWalletBankSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_bank_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ReportWalletBankDetailedSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_bank_detailed_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportWalletCashDetailedSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_cash_detailed_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportWalletUnpaidDetailedSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_unpaid_detailed_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ReportWalletUnpaidSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_unpaid_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportWalletAllUnpaidSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Payment.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('wallet_all_unpaid_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportOrderTimeSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Order.objects.all()
    def post(self, request):
        try:
            
            task = run_report_task.delay('order_time_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportRecaptacioSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('recaptacio_excel_report', request.data)
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportCobramentsSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('cobraments_excel_report', request.data)
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportRecaptacioConceptesSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('recaptacio_conceptes_report', request.data)
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def enqueue_report_export(request, generator_func_name, default_name):
    """
    Llança `run_report_task` a través de la cua de descàrregues de l'usuari
    (ExportJob), perquè l'informe es pugui recuperar encara que marxi de la pàgina.
    La resposta manté `task_id` (compatible amb /task-progress/) i hi afegeix
    `export_job_id`. `export_name` (opcional, al cos) és el nom visible a la cua.
    """
    data = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
    name = data.pop("export_name", None) or str(default_name)
    job = enqueue_export(
        request, run_report_task,
        kind=f"report:{generator_func_name}", name=name,
        args=[generator_func_name, data], params=data,
    )
    return Response(export_job_response(job), status=status.HTTP_202_ACCEPTED)


class ReportRegisterBillingSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            return enqueue_report_export(request, 'register_billing_summary', _("Padró de facturació"))
            
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportMiniRegisterBillingSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            return enqueue_report_export(request, 'mini_register_billing_summary', _("Padró de facturació reduït"))
            
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportDetailedBillingSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('detailed_billing_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ReportBillingSummaryBySupplyType(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('billing_summary_by_supply_type', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportBillingSummaryByPerson(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('report_billing_total_by_person', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportBillingSummaryByRates(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('billing_summary_by_rates', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ReportBillingTaxesSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('billing_taxes_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportBillingTaxesDetailedSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('billing_taxes_detailed_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ReportBillingModel347(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('report_billing_347', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ReportBillingDetailedConsumptionSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Billing.objects.all()
    def post(self, request):
        try:
            task = run_report_task.delay('billing_detailed_consumption_summary', request.data)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportContractsExport(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Contract.objects.all()

    def post(self, request):
        try:
            task = run_report_task.delay('contracts_export_report', request.data)
            return Response(
                {
                    'task_id': task.id,
                    'status': 'pending',
                    'message': 'Report generation started. Use the task_id to check the status.',
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            return Response(
                {'error': f'Ha ocorregut un error inesperat: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ReportContractInvoiceReadingSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Contract.objects.all()

    def post(self, request):
        try:
            task = run_report_task.delay(
                'contracts_invoice_reading_summary_report', request.data
            )
            return Response(
                {
                    'task_id': task.id,
                    'status': 'pending',
                    'message': 'Report generation started. Use the task_id to check the status.',
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            return Response(
                {'error': f'Ha ocorregut un error inesperat: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ReportContractTariffsExport(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Contract.objects.all()

    def post(self, request):
        try:
            task = run_report_task.delay('contracts_tariffs_export_report', request.data)
            return Response(
                {
                    'task_id': task.id,
                    'status': 'pending',
                    'message': 'Report generation started. Use the task_id to check the status.',
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            return Response(
                {'error': f'Ha ocorregut un error inesperat: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ReportContractTerminationExport(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    queryset = Contract.objects.all()

    def post(self, request):
        try:
            task = run_report_task.delay('contracts_termination_export_report', request.data)
            return Response(
                {
                    'task_id': task.id,
                    'status': 'pending',
                    'message': 'Report generation started. Use the task_id to check the status.',
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            return Response(
                {'error': f'Ha ocorregut un error inesperat: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


_skip_general_report = ContextVar("skip_general_report", default=False)


@contextmanager
def without_general_report():
    token = _skip_general_report.set(True)
    try:
        yield
    finally:
        _skip_general_report.reset(token)


def save_report(content, filename, name, type_id, start_date=None, end_date=None):
    try:
        buffer = BytesIO()

        if hasattr(content, "save"):
            content.save(buffer)
        elif isinstance(content, bytes):
            buffer.write(content)
        elif isinstance(content, str):
            buffer.write(content.encode("utf-8"))
        elif hasattr(content, "read"):
            buffer.write(content.read())
        else:
            raise ValueError("Unsupported content type for save_report")

        buffer.seek(0)
        excel_file = ContentFile(buffer.getvalue(), name=filename)
        service = settings.DOCUMENT_MANAGER_SERVICES.get("statistics")
        
        print("creating report")
        report_type = None
        if type_id:
            try:
                report_type = ReportType.objects.get(id=type_id)
            except ReportType.DoesNotExist:
                # Si el frontend envia un type_id que no existeix a DB,
                # igualment generem el document sense categoritzar pel ReportType.
                report_type = None
        
        skip_general_report = _skip_general_report.get()
        general_report = None
        if not skip_general_report:
            general_report = GeneralReport.objects.create(
                start_date=start_date,
                end_date=end_date,
                type=report_type,
                token=filename.split('.')[0],
                name=name
            )
        
        title = (report_type.name).upper() if report_type and report_type.name else "Informe"
        
        document = upload_document(
            excel_file,
            "TEMPLATES",
            "BILLING",
            general_report.id if general_report else 0,
            title,
            "",
            service,
            filename, 
            general_report.created_at if general_report else timezone.now(),
        )
        
        if general_report:
            general_report.document = document
            general_report.save()
        
        return document.id
        
    except Exception as e:
        raise Exception("Error while saving report: ", e)


class ReportGeneralBillingSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('general_billing_summary_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportDetailedTypologyPeriodicity(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('detailed_typology_periodicity_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportDetailedConcept(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('detailed_concept_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportNoRegisterAcaBilling(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            return enqueue_report_export(request, 'no_register_aca_contracts_report', _("Resum de contractes sense ACA"))
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportNonTariffIncome(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('non_tariff_income_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportSubscriberEvolution(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('subscriber_evolution_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportSocialTariffEvolution(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('social_tariff_evolution_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportPendingInvoicesValuesReport(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('pending_invoices_values_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportClaimResponseTime(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('claim_response_time_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportManagementVolume(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('management_volume_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportClavegueramInvoicesSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('clavegueram_invoices_report', request.data)
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportTotalCustomersDebtSummary(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('total_customers_debt_report', request.data)
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Report generation started. Use the task_id to check the status."
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportSgtTxt(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('sgt_txt_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportGeneralAccounting(views.APIView):
    permission_classes = [IsAuthenticated, ReportViewPermission]
    def post(self, request):
        try:
            task = run_report_task.delay('general_accounting_report', request.data)
            return Response({"task_id": task.id, "status": "pending"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
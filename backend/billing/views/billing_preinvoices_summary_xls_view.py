# contract/views/contract_request_finalize_view.py
import datetime
from django.http import HttpResponse
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django.db.models import Count, Sum
from django.utils.translation import gettext as _
import openpyxl
import os

from coredata.utils.language_utils import use_default_language
from billing.models import Billing, Invoice
from billing.serializers.invoice_serializer import InvoiceMinimalListSerializer
from django.shortcuts import get_object_or_404

def simple_row(row, sheet, dict):
    for i, (key, value) in enumerate(dict.items()):
        row+=1
        sheet[f'A{row}'] = key
        sheet[f'B{row}'] = value
    return row
            
def complex_row(row, sheet, dict):
    for i, (key, value) in enumerate(dict.items()):
        row+=1
        sheet[f'A{row}'] = key
        for j, (key2, value2) in enumerate(value.items()):
            sheet[f'B{row}'] = key2
            sheet[f'C{row}'] = value2
    return row
            
def jump_row(row):
    row+=3
    return row

class BillingPreInvoicesSummaryXLSViewSet(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    @use_default_language
    def get(self, request, id):
        try:
            if not id:
                return Response({"error": "billing id is required."}, status=status.HTTP_400_BAD_REQUEST)
            billing = get_object_or_404(Billing, id=id)

            invoices = Invoice.objects.filter(billing = billing)
            
            payment_type_counts = invoices.values('payment_type_final').annotate(count=Count('id')).order_by()
            payment_type_dict = {item['payment_type_final']: item['count'] for item in payment_type_counts}
            
            use_type_counts = invoices.values('contract__use_type__name').annotate(count=Count('id'), sum=Sum('consumption')).order_by()
            use_type_dict = {item['contract__use_type__name']: {item['count']: f"{item['sum']}"} for item in use_type_counts}
            
            line_items_counts = invoices.values('line_items__name', 'line_items__price_rate_name').annotate(count=Count('id'), sum=Sum('line_items__price')).order_by()
            line_items_dict = {f"{item['line_items__name']} - {item['line_items__price_rate_name']}": {item['count']: f"{ round(item['sum'], 2)}"}  for item in line_items_counts}
            
            tax_counts = invoices.values('line_items__tax_percent').annotate(count=Count('id'), sum=Sum('line_items__tax_price')).order_by()
            tax_dict = {f"{item['line_items__tax_percent']} %": {item['count']: f"{ round(item['sum'], 2)}"}  for item in tax_counts}
            
            bonifications_counts = invoices.values('contract__bonifications__bonification_type__name').annotate(count=Count('id')).order_by()
            bonifications_dict = {f"{item['contract__bonifications__bonification_type__name']}": f"{item['count']}" for item in bonifications_counts}
            
            variables_counts = invoices.values('contract__variables__type__name').annotate(count=Count('id')).order_by()
            variables_dict = {f"{item['contract__variables__type__name']}": f"{item['count']}" for item in variables_counts}
            
            messages_counts = invoices.values('messages__title').annotate(count=Count('id')).order_by()
            messages_dict = {f"{item['messages__title']}": f"{item['count']}" for item in messages_counts}
            
            # Create an Excel file
            wb = openpyxl.Workbook()

            # Select the first sheet
            sheet = wb.active

            # Write the data to the sheet
            sheet.title = _("Facturació")

            # Write the payment types
            
            row = 1
            
            sheet['A1'] = _("Payment Types")
            sheet['B1'] = _("Invoices / Line items")
            sheet['C1'] = _("Totals")
            
            row = simple_row(row, sheet, payment_type_dict)
            row = jump_row(row)
            
            sheet[f'A{row}'] = _("Use types")
            
            row = complex_row(row, sheet, use_type_dict)
            row = jump_row(row)
            
            sheet[f'A{row}'] = _("Line items")
            
            row = complex_row(row, sheet, line_items_dict)
            row = jump_row(row)
            
            sheet[f'A{row}'] = _("Taxes")
            row = complex_row(row, sheet, tax_dict)
            row = jump_row(row)
            
            sheet[f'A{row}'] = _("Bonifications")
            row = simple_row(row, sheet, bonifications_dict)
            row = jump_row(row)
            
            sheet[f'A{row}'] = _("Variables")
            row = simple_row(row, sheet, variables_dict)
            row = jump_row(row)
            
            sheet[f'A{row}'] = _("Messages")
            row = simple_row(row, sheet, messages_dict)
            row = jump_row(row)
           
            filename = f"billing_{datetime.datetime.now().strftime('%m_%y')}.xlsx"
           
            wb.save(filename)

            # Send the file as a response
            with open(filename, "rb") as f:
                response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                response["Content-Disposition"] = f"attachment; filename={filename}"
            
            os.remove(filename)
            return response
            
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
import datetime
import math
import os
import threading
from django.core.files.base import ContentFile
from django.db.models import F, Count, Sum, Q, Max, Case, When, Value, CharField, DecimalField, Subquery
from decimal import Decimal
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

from billing.models import Billing, Invoice
from coredata.models import ConfigProject
from pricing.utils.accounting_service import generate_general_accounting
from statistics.views.reports_views import add_row, adjust_column_widths, save_report, jump_row



def generate_general_accounting_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        
        if not date_range:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        
        end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
        invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
        invoices = Invoice.objects.filter(issue_date=end_date.date(), type_final=invoice_type)
        
        content_file = generate_general_accounting(invoices)
        
        filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        response = HttpResponse(content_file.getvalue(), content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        document_id = save_report(
            content=content_file.getvalue(), filename=filename, name=name, type_id=type_id,
            start_date=end_date, end_date=end_date,
        )

        return response, document_id, None
        
    except Exception as e:
        import traceback
        print("Error in generate_no_register_aca_contracts_report: ", e)
        traceback.print_exc()
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
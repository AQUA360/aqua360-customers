# contract/views/contract_request_finalize_view.py
from django.http import FileResponse
from rest_framework import status, views
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter, SearchFilter
import itertools

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import Billing, Invoice, Reading
from billing.serializers.invoice_serializer import InvoiceMinimalListSerializer
from communication.models import CommunicationProcess
from django.shortcuts import get_object_or_404
from django.db.models import Exists, OuterRef, Q

from coredata.models import ConfigProject
from coredata.utils.pdf_utils import merge_pdfs


class BillingInvoicesViewSet(generics.ListAPIView):  # Changed to generics.ListAPIView
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    serializer_class = InvoiceMinimalListSerializer  # Added serializer_class
    pagination_class = PageNumberPagination  # Added pagination_class
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]  # Added filter_backends
    filterset_class = InvoiceFilter  # Added filterset_class
    search_fields = ['token','title_final', 'number', 'contract__token', 'contract_request__token', 'customer_final', 'customer_token_final']
    ordering_fields = ['token','name','total_final', 'left_to_pay', 'consumption', 'consumption_days']

    def get_queryset(self):
        id = self.kwargs.get('id')  # Get the ID from the URL
        if not id:
            return Invoice.objects.none() # Return an empty queryset

        billing = get_object_or_404(Billing, id=id)
        queryset = Invoice.objects.filter(billing=billing, is_active=True).order_by('-created_at')
        if 'is_excluded' not in self.request.query_params:
            queryset = queryset.filter(is_excluded=False)
        return queryset

    def list(self, request, *args, **kwargs):
        billing_id = self.kwargs.get('id')
        billing_invoices = Invoice.objects.filter(billing_id=billing_id, is_active=True) if billing_id else Invoice.objects.none()
        if 'is_excluded' not in request.query_params:
            billing_invoices = billing_invoices.filter(is_excluded=False)
        has_possible_leak_comm = str(request.query_params.get('has_possible_leak_comm', '')).strip().lower() in ('true', '1', 'yes')
        # Calculate global median for this billing (consistent with summary)
        all_values = list(billing_invoices.values_list('consumption_days', flat=True))
        all_values = sorted([v for v in all_values if v is not None])
        n_all = len(all_values)
        median = 0
        global_count_above_margin = 0
        if n_all > 0:
            if n_all % 2 == 1:
                median = float(all_values[n_all // 2])
            else:
                median = float(all_values[n_all // 2 - 1] + all_values[n_all // 2]) / 2
            
            margin_high = median * 1.25
            margin_low = median * 0.75
            global_count_above_margin = sum(1 for v in all_values if float(v) > margin_high or float(v) < margin_low)

        # Apply filters (Note: InvoiceFilter returns all if alert=warning_date_range)
        queryset = self.filter_queryset(self.get_queryset())

        # Manually filter by date range if requested
        alert_val = request.query_params.get('alert')
        if alert_val == 'warning_date_range' and n_all > 0:
            margin_high = median * 1.25
            margin_low = median * 0.75
            queryset = queryset.filter(Q(consumption_days__gt=margin_high) | Q(consumption_days__lt=margin_low))
        
        if has_possible_leak_comm:
            cancelled_token = ConfigProject.objects.get(token='communication_process_status_cancelled_token').value
            active_processes = CommunicationProcess.objects.filter(
                readings=OuterRef('pk')
            ).exclude(status__token=cancelled_token)
            readings_with_active_process = Reading.objects.filter(
                invoices=OuterRef('pk'),
                is_control=False,
            ).filter(Exists(active_processes))
            queryset = queryset.filter(Exists(readings_with_active_process))

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['date_range_median'] = median
            response.data['date_range_above_margin_count'] = global_count_above_margin
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
            'date_range_median': median,
            'date_range_above_margin_count': global_count_above_margin
        })
        
class BillingInvoicesSummaryViewSet(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    def get(self, request, id):
        try:
            print('id', id)
            if not id:
                return Response({"error": "billing id is required."}, status=status.HTTP_400_BAD_REQUEST)
            billing = get_object_or_404(Billing, id=id)

            invoices = Invoice.objects.filter(billing = billing)
            
            counters = { }
            counters['total'] = invoices.filter(is_excluded=False).count()
            counters['excluded'] = invoices.filter(is_excluded=True).count()
            
            warning_invoices = invoices.filter(warning__isnull=False, is_excluded=False)
            warning_invoices_list = sorted(warning_invoices, key=lambda x: x.warning.name)
            warnings = itertools.groupby(warning_invoices_list, key=lambda x: x.warning.name)
            
            # Count grouped by warning name
            for name, group in warnings:
                counters[name] = len(list(group))

            try:
                high_amount_token = ConfigProject.objects.get(token='invoice_warning_high_amount').value
                if invoices.filter(warning__token=high_amount_token).exists() and not any(k for k in counters.keys() if k != 'total'):
                    # Only calculate if it didn't get caught by the grouping (safeguard)
                    counters['high_billing_amount'] = invoices.filter(warning__token=high_amount_token).count()
                elif 'high_billing_amount' not in counters.keys():
                    # explicitly add it even if it duplicates? Actually the user says "don't show the same invoice in each warning".
                    # Let's just calculate total correctly to avoid duplicate math.
                    pass
            except ConfigProject.DoesNotExist:
                pass

            counters['total_warnings'] = warning_invoices.count()
            counters['total_correct'] = counters['total'] - counters['total_warnings']

            # Calculate median and count for date range (consumption_days)
            # Only consider non-excluded invoices for the median and alerts
            active_invoices = invoices.filter(is_excluded=False)
            values = list(active_invoices.values_list('consumption_days', flat=True))
            values = sorted([v for v in values if v is not None])
            n = len(values)
            median = 0
            count_above_margin = 0
            if n > 0:
                if n % 2 == 1:
                    median = float(values[n // 2])
                else:
                    median = float(values[n // 2 - 1] + values[n // 2]) / 2
                
                margin_high = median * 1.25
                margin_low = median * 0.75
                count_above_margin = sum(1 for v in values if float(v) > margin_high or float(v) < margin_low)
            
            counters['date_range_median'] = median
            counters['date_range_above_margin_count'] = count_above_margin
            
            return Response({'counters': counters}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BillingInvoicesPdfViewSet(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    def get(self, request, id):
        try:
            if not id:
                return Response({"error": "billing id is required."}, status=status.HTTP_400_BAD_REQUEST)
            billing = get_object_or_404(Billing, id=id)

            invoices = Invoice.objects.filter(billing = billing)
       
            if not invoices.exists():
                return Response({"error": "No invoices found for this billing."}, status=status.HTTP_404_NOT_FOUND)

            merged_pdf = merge_pdfs(*invoices)

            response = FileResponse(open(merged_pdf.name, 'rb'), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="billing_{billing.id}_invoices.pdf"'
            return response
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from datetime import date
import datetime
import calendar
import re
from django.utils import timezone
from rest_framework import views, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, OuterRef, Subquery, F, Min, Max
from django.db.models.functions import Coalesce

from auth.permissions import PermissionManager
from billing.utils.billing_service import generate_invoice_budgets_from_billing, get_billed_invoices_without_billing, move_budget_to_billing_pre_invoice, move_invoice_to_billing
from contract.models import Contract, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from coredata.models import ConfigProject
from service.models import Exploitation, Meter, Route, SupplyPoint
from service.serializers.route_serializer import RouteListSerializer
from service.utils.route_positions_service import route_count_total_readings
from django.contrib.auth.models import Group
from billing.tasks import create_billings
from pricing.models import ProductOrigin

from billing.filter.billing_batch_filter import BillingBatchFilter
from billing.filter.billing_filter import BillingFilter
from billing.models import (
    Biller,
    Billing,
    BillingStatus,
    Invoice,
    ReadingBatch,
    ReadingBatchStatus,
    Reading
)
from billing.serializers.billing_serializer import BillingListSerializer, BillingSerializer

class BillingViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = Billing.objects.all().order_by('-created_at').filter(is_active=True)
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = BillingFilter
  search_fields = ['token','name']
  ordering_fields = ['id','token','name', 'created_at', 'send_at']
  ordering = ['-created_at']

  def get_queryset(self):
    invoices_send_at = Invoice.objects.filter(
        billing=OuterRef('pk'), 
        send_at__isnull=False
    ).order_by('send_at').values('send_at')[:1]
    
    return Billing.objects.filter(is_active=True).annotate(
        effective_send_at=Coalesce('send_at', Subquery(invoices_send_at))
    )

  def filter_queryset(self, queryset):
      queryset = super().filter_queryset(queryset)
      ordering = self.request.query_params.get('ordering')
      if ordering:
          if 'send_at' in ordering:
              is_desc = ordering.startswith('-')
              field_name = 'effective_send_at'
              if is_desc:
                  queryset = queryset.order_by(F(field_name).desc(nulls_last=True))
              else:
                  queryset = queryset.order_by(F(field_name).asc())
      return queryset
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return BillingListSerializer
        elif self.action == 'retrieve':
            return BillingSerializer
    return BillingSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=True, methods=['get'], url_path='billed-invoices')
  def get_billed_invoices_outside_billing(self, request, pk=None):
    
    detailed = request.query_params.get('detailed', 'false').strip().lower() == 'true'
    billed_type = request.query_params.get('type', '').strip().lower()
    
    response = get_billed_invoices_without_billing(pk, detailed, billed_type)
    return Response(response, status=status.HTTP_200_OK)
  
  @action(detail=True, methods=['put'], url_path='update-pre-invoices')
  def move_budget_to_billing(self, request, pk=None):
    
    budget_ids = request.data.get('budget_ids', [])
    
    response = move_budget_to_billing_pre_invoice(pk, budget_ids)
    return Response(response, status=status.HTTP_200_OK)
  
  @action(detail=True, methods=['put'], url_path='move-invoice-to-billing')
  def move_invoice_to_billing(self, request, pk=None):
    
    invoice_ids = request.data.get('invoice_ids', [])
    
    response = move_invoice_to_billing(pk, invoice_ids)
    return Response(response, status=status.HTTP_200_OK)
  
  @action(detail=True, methods=['put'], url_path='generate-invoice-budget')
  def generate_invoice_budgets(self, request, pk=None):
    
    budget_ids = request.data.get('budget_ids', [])
    
    response = generate_invoice_budgets_from_billing(pk, budget_ids)
    return Response(response, status=status.HTTP_200_OK)
  
  
  @action(detail=True, methods=['get'], url_path='check-missing')
  def check_missing(self, request, pk=None):
      billing = self.get_object()
      filter_type = (request.query_params.get('type') or '').strip()  # missing_by_route, missing_by_exploitation, all
      get_csv = ((request.query_params.get('is_csv') or '').strip()).upper() == "TRUE"  # true, false
      valid_filter_types = {'', 'all', 'missing_by_route', 'missing_by_exploitation', 'all_contracts'}
      if filter_type not in valid_filter_types:
        return Response(
          {"error": f"Invalid type filter '{filter_type}'. Use one of: all, missing_by_route, missing_by_exploitation."},
          status=status.HTTP_400_BAD_REQUEST
        )

      biller = billing.biller
      exploitations = list(billing.invoices.values_list('exploitation__id', flat=True).distinct())
      total_exploitations = Exploitation.objects.count()

      new_contracts = 0
      no_readings = 0
      no_batches = 0
      no_route = 0
      no_billing = 0
      new_termination = 0
      no_price_rate = 0
      excluded_billing = 0
      block_billing = 0
      unprocessed_invoice = 0
      no_meter = 0

      # Rang de dates del periode de facturacio, calculat a partir de la periodicitat
      # del facturador (period_type + initial_month) i del periode que aquest Billing
      # representa realment.
      PERIOD_TYPE_INTERVAL = {
        'mensual': 1,
        'bimestral': 2,
        'trimestral': 3,
        'quadrimestral': 4,
        'semestral': 6,
        'anual': 12,
      }
      interval = PERIOD_TYPE_INTERVAL.get(biller.period_type, 3)
      today = timezone.now().date()

      # El token/name de `create_billings` (billing/tasks.py) porta el mes/any en que
      # es va CREAR el lot (`current_month`/`current_year` del moment d'execucio), no
      # el periode de consum que factura -- son la mateixa data que `created_at`, no
      # una alternativa. Quan el Billing ja te lectures assignades, la data real del
      # periode es la `reading_date` mes recent d'aquestes lectures (poden ser molt
      # anteriors a `created_at`/token si el lot es va crear amb retard, p.ex. periode
      # gener-marc processat al maig). Nomes es cau al token/`created_at` si el
      # Billing encara no te cap lectura vinculada (lot nou, encara sense processar).
      latest_own_reading_date = Reading.objects.filter(
        billing=billing, is_control=False
      ).aggregate(max_date=Max('reading_date'))['max_date']

      # if latest_own_reading_date:
      #   end_month = latest_own_reading_date.month
      #   end_year = latest_own_reading_date.year
      # else:
      period_month_year_match = re.search(r'-\s*(\d{1,2})(\d{4})\s*$', billing.token or '') or \
        re.search(r'-\s*(\d{1,2})(\d{4})\s*$', billing.name or '')
      end_month = int(period_month_year_match.group(1)) if period_month_year_match else None
      end_year = int(period_month_year_match.group(2)) if period_month_year_match else None
      if not end_month or not (1 <= end_month <= 12):
        period_reference = billing.created_at.date() if billing.created_at else today
        end_month = period_reference.month
        end_year = period_reference.year
      start_month = end_month - interval + 1
      start_year = end_year
      if start_month <= 0:
        start_month += 12
        start_year -= 1

      first_start_reading = datetime.date(start_year, start_month, 1)
      last_day_of_end_month = calendar.monthrange(end_year, end_month)[1]
      last_end_reading = datetime.date(end_year, end_month, last_day_of_end_month)
      # No es poden generar factures amb dates futures.
      last_end_reading = min(last_end_reading, today)
      response_end_date = last_end_reading

      active_contract_status = ContractStatus.objects.get(token=ConfigProject.objects.get(token='contract_active_token').value)
      termination_contract_status = ContractStatus.objects.get(token=ConfigProject.objects.get(token='contract_terminated_status').value)
      termination_finished_status = ContractTerminationStatus.objects.get(token=ConfigProject.objects.get(token='contract_termination_completed_token').value)
      pending_invoice_token = ConfigProject.objects.get(token='invoice_status_pending_token').value

      terminated_qs = ContractTerminationRequest.objects.filter(
        is_active=True,
        status=termination_finished_status
      )
      if first_start_reading:
        terminated_qs = terminated_qs.filter(requested_at__date__gte=first_start_reading)
      terminated_contract_ids = terminated_qs.values_list('contract_id', flat=True)

      billable_status_filter = (
        Q(status=active_contract_status) |
        Q(status=termination_contract_status, id__in=terminated_contract_ids)
      )

      # Missing = contractes de la ruta/explotació creats abans que acabi el periode
      # i que no tenen cap factura que cobreixi aquest periode (a QUALSEVOL facturacio,
      # no només l'actual), ja sigui per lectures dins del rang o, si no en té, per
      # data d'emissió dins del rang.
      route_contracts = Contract.objects.filter(
        supply_points__property__route_position__route__biller=biller,
        created_at__date__lte=last_end_reading,
      ).filter(billable_status_filter).distinct()

      if len(exploitations) == 1 and total_exploitations > 1:
        exploitation_contracts = Contract.objects.filter(
          supply_points__connection__exploitation__id=exploitations[0],
          created_at__date__lte=last_end_reading,
        ).filter(billable_status_filter).distinct()
      else:
        exploitation_contracts = Contract.objects.none()

      candidate_contract_ids = Contract.objects.filter(
        Q(id__in=route_contracts.values('id')) |
        Q(id__in=exploitation_contracts.values('id'))
      ).values_list('id', flat=True)

      invoiced_in_period_contract_ids = set(Invoice.objects.filter(
        contract_id__in=candidate_contract_ids
      ).filter(
        Q(readings__reading_date__range=(first_start_reading, last_end_reading)) |
        Q(readings__isnull=True, issue_date__range=(first_start_reading, last_end_reading))
      ).values_list('contract_id', flat=True).distinct())

      missing_by_route = route_contracts.exclude(id__in=invoiced_in_period_contract_ids).distinct()
      missing_by_exploitation = exploitation_contracts.exclude(id__in=invoiced_in_period_contract_ids).distinct()
      all_missing_contracts = Contract.objects.filter(
          Q(id__in=route_contracts.values('id')) |
          Q(id__in=exploitation_contracts.values('id'))
        ).exclude(
          id__in=invoiced_in_period_contract_ids
        ).distinct()

      missing_contracts_with_reason = []

      filtered_contracts = (
        missing_by_route if filter_type == 'missing_by_route'
        else missing_by_exploitation if filter_type == 'missing_by_exploitation'
        else all_missing_contracts
      ).select_related(
        'status',
        'supply_point_default__property__route_position__route__biller'
      )

      filtered_contract_ids = list(filtered_contracts.values_list('id', flat=True))

      # Motius a partir de l'última lectura elegible sense factura (sense restricció de rang de dates).
      contract_reading_stats = {}
      latest_readings = Reading.objects.filter(
        contract_id__in=filtered_contract_ids,
        is_initial=False,
        is_control=False,
        reading_date__gte=F('contract__created_at'),
        invoices__isnull=True,
      ).filter(
        reading_date__gte=first_start_reading
        ).order_by('contract_id', '-reading_date', '-id').values('contract_id', 'batch_id', 'billing_id', 'reading_date')
      
      for reading in latest_readings:
        contract_id = reading['contract_id']
        if contract_id in contract_reading_stats:
          continue
        contract_reading_stats[contract_id] = {
          'reading_count': 1,
          'reading_with_batch_count': 1 if reading['batch_id'] else 0,
          'reading_with_billing_count': 1 if reading['billing_id'] else 0,
        }

      excluded_billing_contract_ids = set(Invoice.objects.filter(
        contract_id__in=filtered_contract_ids,
        billing=None,
        readings__billing=billing,
        status__token=pending_invoice_token
      ).values_list('contract_id', flat=True).distinct())

      related_termination_qs = ContractTerminationRequest.objects.filter(
        contract_id__in=filtered_contract_ids,
      )
      if first_start_reading:
        related_termination_qs = related_termination_qs.filter(requested_at__date__gte=first_start_reading)
      related_termination_contract_ids = set(related_termination_qs.values_list('contract_id', flat=True).distinct())

      no_route_contract_ids = set(Contract.objects.filter(
        id__in=filtered_contract_ids
      ).exclude(
        supply_points__isnull=True
      ).filter(
        Q(supply_points__property__isnull=True) |
        Q(supply_points__property__route_position__isnull=True) |
        Q(supply_points__property__route_position__route__isnull=True)
      ).values_list('id', flat=True).distinct())

      contract_ids_with_price_rates = set(Contract.objects.filter(
        id__in=filtered_contract_ids,
        price_rates__isnull=False
      ).values_list('id', flat=True).distinct())

      contract_ids_with_meters = set(Contract.objects.filter(
          id__in=filtered_contract_ids,
          supply_points__meter__isnull=False
      ).values_list('id', flat=True).distinct())

      for contract in filtered_contracts:
        missing_reasons = self._get_missing_contracts_with_reason(
          contract=contract,
          billing=billing,
          first_start_reading=first_start_reading,
          termination_contract_status=termination_contract_status,
          contract_reading_stats=contract_reading_stats,
          excluded_billing_contract_ids=excluded_billing_contract_ids,
          related_termination_contract_ids=related_termination_contract_ids,
          no_route_contract_ids=no_route_contract_ids,
          contract_ids_with_price_rates=contract_ids_with_price_rates,
          contract_ids_with_meters=contract_ids_with_meters
        )
        if 'new_contract' in missing_reasons:
          new_contracts += 1
        if 'new_termination' in missing_reasons:
          new_termination += 1
        if 'no_reading' in missing_reasons:
          no_readings += 1
        if 'no_batch' in missing_reasons:
          no_batches += 1
        if 'no_route' in missing_reasons:
          no_route += 1
        if 'no_billing' in missing_reasons:
          no_billing += 1
        if 'no_price_rate' in missing_reasons:
          no_price_rate += 1
        if 'excluded_billing' in missing_reasons:
          excluded_billing += 1
        if 'block_billing' in missing_reasons:
          block_billing += 1
        if 'unprocessed_invoice' in missing_reasons:
          unprocessed_invoice += 1
        if 'no_meter' in missing_reasons:
          no_meter += 1

        missing_contracts_with_reason.append({
          'contract_id': contract.id,
          'contract_token': contract.token,
          'contract_status_token': contract.status.token,
          'contract_status_name': contract.status.name,
          'contract_holder_name': str(contract.holder),
          'contract_holder_token': contract.holder.token,
          'start_date': first_start_reading,
          'end_date': response_end_date,
          'missing_reasons': missing_reasons
        })

      if get_csv:
        from billing.utils.billing_service import generate_billing_missing_contracts_report
        return generate_billing_missing_contracts_report(missing_contracts_with_reason, billing, first_start_reading, last_end_reading)

      if filter_type and filter_type != 'all':
        return Response({'results': missing_contracts_with_reason}, status=status.HTTP_200_OK)

      info_data = {
        'missing_contracts': all_missing_contracts.count(),
        'missing_by_route': missing_by_route.count(),
        'missing_by_exploitation': missing_by_exploitation.count(),
        'missing_contracts_with_reason': missing_contracts_with_reason,
        'new_contracts': new_contracts,
        'no_readings': no_readings,
        'no_batches': no_batches,
        'new_termination': new_termination,
        'no_route': no_route,
        'no_billing': no_billing,
        'no_price_rate': no_price_rate,
        'excluded_billing': excluded_billing,
        'block_billing': block_billing,
        'unprocessed_invoice': unprocessed_invoice,
        'no_meter': no_meter,
        'start_date': first_start_reading,
        'end_date': response_end_date,
      }

      return Response(info_data, status=status.HTTP_200_OK)

  def _get_missing_contracts_with_reason(
    self,
    contract,
    billing,
    first_start_reading,
    termination_contract_status,
    contract_reading_stats,
    excluded_billing_contract_ids,
    related_termination_contract_ids,
    no_route_contract_ids,
    contract_ids_with_price_rates,
    contract_ids_with_meters
  ):
    contract_stats = contract_reading_stats.get(contract.id, {})
    has_readings = bool(contract_stats.get('reading_count', 0))
    has_batch = bool(contract_stats.get('reading_with_batch_count', 0))
    has_billing = bool(contract_stats.get('reading_with_billing_count', 0))
    has_excluded_invoices = contract.id in excluded_billing_contract_ids

    missing_reasons = []
    if first_start_reading and contract.created_at.date() > first_start_reading:
      missing_reasons.append('new_contract')
    if contract.status.token == termination_contract_status.token and contract.id in related_termination_contract_ids:
      missing_reasons.append('new_termination')
    if has_excluded_invoices:
      missing_reasons.append('excluded_billing')
    else:
      if contract.block_billing:
        missing_reasons.append('block_billing')
      else:
        if not has_readings:
          missing_reasons.append('no_reading')
        else:
          if not has_batch:
            missing_reasons.append('no_batch')
          else:
            if not has_billing:
              missing_reasons.append('no_billing')
            else:
              missing_reasons.append('unprocessed_invoice')
    if contract.id in no_route_contract_ids:
      missing_reasons.append('no_route')
    if contract.supply_point_default and contract.supply_point_default.property and contract.supply_point_default.property.route_position and contract.supply_point_default.property.route_position.route and contract.supply_point_default.property.route_position.route.biller and contract.supply_point_default.property.route_position.route.biller != billing.biller:
      missing_reasons.append({'current_route': contract.supply_point_default.property.route_position.route.biller.name})
    if contract.id not in contract_ids_with_price_rates:
      missing_reasons.append('no_price_rate')
    if contract.id not in contract_ids_with_meters:
      missing_reasons.append('no_meter')

    return missing_reasons

    
  @action(detail=False, methods=['post'], url_path='missing-contracts')
  def manage_missing_contracts(self, request):
      try:
        billing_id = request.data.get('billing_id', None)
        contract_ids = request.data.get('contract_ids', None)
        start_date = request.data.get('start_date', None)
        end_date = request.data.get('end_date', None)
        
        billing = Billing.objects.get(id=billing_id)
        contracts = Contract.objects.filter(id__in=contract_ids)
        
        supply_point_ids = [sp.id for contract in contracts for sp in contract.supply_points.all()]
        meters = Meter.objects.filter(supply_points__id__in=supply_point_ids)
        print('\n\n')
        print(meters.count(), 'meters')
        
        if isinstance(start_date, str):
          start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
          end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        
        new_reading_batch = ReadingBatch.objects.create(
          token=billing.token,
          name=billing.name,
          include_telecontrol=True,
          include_manual=True,
          status=ReadingBatchStatus.objects.get(is_default=True),
          billing_missing=billing,
          missing_start=start_date,
          missing_end=end_date,
        )
        new_reading_batch.fix_meters.set(meters)
        
        try:
          readings = Reading.objects.filter(
            contract__in=contracts,
            # meter__in=meters,
            reading_date__range=(start_date, end_date),
            reading_date__gte=F('contract__created_at'),
            is_control=False,
            is_initial=False,
            invoices__isnull=True,
          ).order_by('contract_id', '-reading_date', '-id').distinct()

          last_reading_ids_by_contract = {}
          for reading in readings:
            if reading.contract_id not in last_reading_ids_by_contract:
              last_reading_ids_by_contract[reading.contract_id] = reading.id

          readings = Reading.objects.filter(id__in=last_reading_ids_by_contract.values())
          for reading in readings:
            print(reading.meter.code, 'meter', reading.id, reading.contract.token)
          readings.update(batch=new_reading_batch, billing=None)
        except Exception as e:
          print(e)
        
        new_reading_batch.save()
      
        return Response({'new_reading_batch': new_reading_batch.id}, status=status.HTTP_200_OK)
      except Exception as e:
        return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
  @action(detail=True, methods=['put'], url_path='cancel')
  def cancel(self, request, pk=None):
      from django.db import transaction
      from billing.models import InvoiceLineItem, InvoiceLog, Payment

      billing = self.get_object()
      
      try:
          cancelled_status = BillingStatus.objects.get(token="-1")
      except BillingStatus.DoesNotExist:
          return Response({"error": "BillingStatus 'Cancel·lat' (token '-1') not found in database."}, status=status.HTTP_404_NOT_FOUND)

      try:
          pending_invoice_token = ConfigProject.objects.get(token='invoice_status_pending_token').value
      except ConfigProject.DoesNotExist:
          pending_invoice_token = "1"

      # Identify pre-invoices to delete
      pre_invoices = Invoice.objects.filter(
          billing=billing
      ).filter(
          Q(is_confirmed=False) | Q(status__token=pending_invoice_token)
      )
      
      invoice_ids = list(pre_invoices.values_list('id', flat=True))

      with transaction.atomic():
          if invoice_ids:
              # Cascade delete pre-invoices
              InvoiceLog.objects.filter(invoice_id__in=invoice_ids).delete()
              InvoiceLineItem.objects.filter(invoice_id__in=invoice_ids).delete()
              Payment.objects.filter(invoice_id__in=invoice_ids).delete()
              
              # Unlink ManyToMany and other references
              for invoice in pre_invoices:
                  invoice.readings.clear()
                  invoice.general_contracts.clear()
                  if invoice.invoice_file:
                      invoice.invoice_file.delete()
              
              # Posar parent_invoice a NULL per a factures filles si n'hi hagués
              Invoice.objects.filter(parent_invoice_id__in=invoice_ids).update(parent_invoice=None)
              
              # Delete the invoices
              pre_invoices.delete()

          # Unlink readings so they can be billed again
          Reading.objects.filter(billing=billing).update(billing=None)
          
          # Unlink other relationships
          billing.routes.clear()
          ReadingBatch.objects.filter(billing_missing=billing).update(billing_missing=None)
          Billing.objects.filter(excluded_from=billing).update(excluded_from=None)
          
          # Update billing status to Cancelled
          billing.status = cancelled_status
          billing.save()

      return Response({"message": "Billing process cancelled successfully and pre-invoices deleted."}, status=status.HTTP_200_OK)

  @action(detail=False, methods=['get'], url_path='permissions')
  def permissions(self, request):
      pk = request.query_params.get('id')
      if pk:
          user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
          if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
              return Response( None, status=status.HTTP_403_FORBIDDEN )
          group = Group.objects.filter(id=pk).first()
          if not group:
              return Response( None, status=status.HTTP_404_NOT_FOUND )
          group_permissions = PermissionManager.get_model_group_permissions(group, 'billing')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'billing', 'billing')
      return Response(permissions, status=status.HTTP_200_OK)
      
  @action(detail=True, methods=['post'], url_path='add-estimated-reading')
  def add_estimated_reading(self, request, pk=None):
      billing = self.get_object()
      contract_id = request.data.get('contract_id')
      if not contract_id:
          return Response({"error": "contract_id is required."}, status=status.HTTP_400_BAD_REQUEST)
      
      try:
          contract = Contract.objects.get(id=contract_id)
      except Contract.DoesNotExist:
          return Response({"error": "Contract not found."}, status=status.HTTP_404_NOT_FOUND)

      # Get the supply point
      supply_point = contract.supply_point_default
      if not supply_point:
          supply_point = contract.supply_points.first()
      if not supply_point:
          return Response({"error": "Supply point not found for this contract."}, status=status.HTTP_400_BAD_REQUEST)

      # Determine dates (same logic as check_missing)
      PERIOD_MONTHS_MAP = {
          'trimestral': 90,
          'semestral': 180,
          'bimestral': 60,
          'quadrimestral': 120,
          'anual': 360,
          'mensual': 30,
      }
      biller = billing.biller
      billing_period_days = PERIOD_MONTHS_MAP.get(biller.period_type, 90)

      try: 
          limit = int(ConfigProject.objects.get(token='reading_estimate_limit_percentage').value)
      except Exception:
          limit = 33

      reading_dates = billing.readings.aggregate(
          min_reading=Min('reading_date'),
          min_previous=Min('previous_reading__reading_date'),
          max_reading=Max('reading_date')
      )

      # Find or create ReadingBatch for billing_missing
      ref_batch = ReadingBatch.objects.filter(billing_missing=billing).first()
      if not ref_batch:
          first_billing_reading = billing.readings.select_related('batch').first()
          if first_billing_reading and first_billing_reading.batch:
              ref_batch = first_billing_reading.batch
          else:
              try:
                  default_status = ReadingBatchStatus.objects.get(is_default=True)
              except ReadingBatchStatus.DoesNotExist:
                  default_status = ReadingBatchStatus.objects.first()

              start_date = reading_dates['min_previous'] or reading_dates['min_reading'] or (datetime.date.today() - datetime.timedelta(days=billing_period_days))
              end_date = reading_dates['max_reading'] or datetime.date.today()

              ref_batch = ReadingBatch.objects.create(
                  token=billing.token,
                  name=billing.name,
                  include_telecontrol=True,
                  include_manual=True,
                  status=default_status,
                  billing_missing=billing,
                  missing_start=start_date,
                  missing_end=end_date,
              )

      first_start_reading = ref_batch.missing_start if ref_batch and ref_batch.missing_start else (reading_dates['min_previous'] or reading_dates['min_reading'])
      last_end_reading = (ref_batch.missing_end - datetime.timedelta(days=(billing_period_days * (limit/100)))) if ref_batch and ref_batch.missing_end else reading_dates['max_reading']

      target_date = ref_batch.missing_end if ref_batch and ref_batch.missing_end else last_end_reading
      if not target_date:
          target_date = datetime.date.today()
      if isinstance(target_date, datetime.datetime):
          target_date = target_date.date()

      from billing.utils.reading_service import get_estimated_reading_minimal_object
      reading = get_estimated_reading_minimal_object(
          supply_point=supply_point,
          contract=contract,
          date=target_date,
          batch=ref_batch,
          offset_days=billing_period_days,
          max_day_limit=datetime.date.today(),
          create_reading=True
      )

      if not reading:
          return Response({"error": "Failed to generate estimated reading (min days limit or other constraint)."}, status=status.HTTP_400_BAD_REQUEST)

      return Response({"id": reading.id, "message": "Estimated reading created successfully."}, status=status.HTTP_201_CREATED)

  @action(detail=True, methods=['post'], url_path='add-to-batch')
  def add_to_batch(self, request, pk=None):
      billing = self.get_object()
      contract_id = request.data.get('contract_id')
      if not contract_id:
          return Response({"error": "contract_id is required."}, status=status.HTTP_400_BAD_REQUEST)

      try:
          contract = Contract.objects.get(id=contract_id)
      except Contract.DoesNotExist:
          return Response({"error": "Contract not found."}, status=status.HTTP_404_NOT_FOUND)

      # Determine dates and batch
      PERIOD_MONTHS_MAP = {
          'trimestral': 90,
          'semestral': 180,
          'bimestral': 60,
          'quadrimestral': 120,
          'anual': 360,
          'mensual': 30,
      }
      biller = billing.biller
      billing_period_days = PERIOD_MONTHS_MAP.get(biller.period_type, 90)

      try:
          limit = int(ConfigProject.objects.get(token='reading_estimate_limit_percentage').value)
      except Exception:
          limit = 33

      reading_dates = billing.readings.aggregate(
          min_reading=Min('reading_date'),
          min_previous=Min('previous_reading__reading_date'),
          max_reading=Max('reading_date')
      )

      ref_batch = ReadingBatch.objects.filter(billing_missing=billing).first()
      if not ref_batch:
          first_billing_reading = billing.readings.select_related('batch').first()
          if first_billing_reading and first_billing_reading.batch:
              ref_batch = first_billing_reading.batch
          else:
              try:
                  default_status = ReadingBatchStatus.objects.get(is_default=True)
              except ReadingBatchStatus.DoesNotExist:
                  default_status = ReadingBatchStatus.objects.first()

              start_date = reading_dates['min_previous'] or reading_dates['min_reading'] or (datetime.date.today() - datetime.timedelta(days=billing_period_days))
              end_date = reading_dates['max_reading'] or datetime.date.today()

              ref_batch = ReadingBatch.objects.create(
                  token=billing.token,
                  name=billing.name,
                  include_telecontrol=True,
                  include_manual=True,
                  status=default_status,
                  billing_missing=billing,
                  missing_start=start_date,
                  missing_end=end_date,
              )

      first_start_reading = ref_batch.missing_start if ref_batch and ref_batch.missing_start else (reading_dates['min_previous'] or reading_dates['min_reading'])
      last_end_reading = (ref_batch.missing_end - datetime.timedelta(days=(billing_period_days * (limit/100)))) if ref_batch and ref_batch.missing_end else (reading_dates['max_reading'] if reading_dates and reading_dates['max_reading'] else datetime.date.today())

      # Find reading (lectura vigent de facturació)
      reading = Reading.objects.filter(
          contract=contract,
          is_initial=False,
          is_control=False,
          is_active=True,
          invoices__isnull=True,
      ).filter(
          reading_date__gte=contract.created_at.date() if contract.created_at else contract.registration_date
      )
      
      if first_start_reading and last_end_reading:
          margin_days = datetime.timedelta(days=(billing_period_days * (limit/100)))
          reading = reading.filter(
              reading_date__range=(first_start_reading, last_end_reading + margin_days)
          )

      reading = reading.order_by('-reading_date', '-id').first()

      if not reading:
          return Response({"error": "No eligible active reading found for this contract in the billing period."}, status=status.HTTP_404_NOT_FOUND)

      # Associate reading with batches
      reading.batch = ref_batch
      reading.billing = billing
      reading.save()

      return Response({"message": "Reading successfully associated with reading batch and billing."}, status=status.HTTP_200_OK)

  @action(detail=True, methods=['post'], url_path='process-contract')
  def process_contract(self, request, pk=None):
      billing = self.get_object()
      contract_id = request.data.get('contract_id')
      if not contract_id:
          return Response({"error": "contract_id is required."}, status=status.HTTP_400_BAD_REQUEST)

      try:
          contract = Contract.objects.get(id=contract_id)
      except Contract.DoesNotExist:
          return Response({"error": "Contract not found."}, status=status.HTTP_404_NOT_FOUND)

      from billing.utils.reading_service import fanout_general_meter_readings
      fanout_general_meter_readings(billing)

      # Find readings for this contract under current billing
      contract_readings = list(billing.readings.filter(
          contract=contract,
          is_control=False,
          is_active=True,
          is_close=False
      ).select_related('contract', 'contract__status', 'supply_point', 'meter', 'batch', 'billing').exclude(
          invoices__type_final='F'
      ).order_by('reading_date').distinct())

      if not contract_readings:
          return Response({"error": "No active readings associated with this billing lot for the contract."}, status=status.HTTP_400_BAD_REQUEST)

      # Deduplicate to avoid more than 1 reading for the same contract & meter
      set_added_readings = set()
      filtered_readings = []
      for reading in contract_readings:
          if (contract.token, reading.meter.code) in set_added_readings:
              continue
          set_added_readings.add((contract.token, reading.meter.code))
          filtered_readings.append(reading)

      period_type = billing.biller.period_type
      PERIOD_MONTHS_MAP = {
          'trimestral': 90,
          'semestral': 180,
          'bimestral': 60,
          'quadrimestral': 120,
          'anual': 360,
          'mensual': 30,
      }
      period_days = PERIOD_MONTHS_MAP.get(period_type, 90)
      period_months = period_days / 30

      # Generate invoice
      from billing.utils.invoice_service import generate_consumption_invoice_multiple
      from billing.models import InvoiceWarning
      from statistics.utils.billing_amount_average import is_high_amount_for_period

      billing_batch = billing.billing_batches.first()
      invoice = generate_consumption_invoice_multiple(
          contract=contract,
          readings=filtered_readings,
          title=billing.name,
          billing=billing,
          billing_batch=billing_batch,
          period_months=period_months
      )

      if not invoice:
          return Response({"error": "Failed to generate invoice (no meter or date mismatch)."}, status=status.HTTP_400_BAD_REQUEST)

      # Set general contracts if general invoice exists
      if contract.general_invoice:
          general_invoice = contract.general_invoice
          general_contracts = list(Contract.objects.filter(general_invoice=general_invoice))
          invoice.general_contracts.set(general_contracts)

      # Apply warning checks
      try:
          invoice_warning_negative = InvoiceWarning.objects.filter(token=ConfigProject.objects.get(token='invoice_warning_negative').value).first()
          invoice_warning_zero = InvoiceWarning.objects.filter(token=ConfigProject.objects.get(token='invoice_warning_zero').value).first()
          invoice_warning_bank_missing = InvoiceWarning.objects.filter(token=ConfigProject.objects.get(token='invoice_warning_bank_missing').value).first()
          invoice_warning_payment_missing = InvoiceWarning.objects.filter(token=ConfigProject.objects.get(token='invoice_warning_payment_missing').value).first()
          invoice_warning_simplified_over_400 = InvoiceWarning.objects.filter(token=ConfigProject.objects.get(token='invoice_warning_simplified_over_400').value).first()
          invoice_warning_high_amount = InvoiceWarning.objects.filter(token=ConfigProject.objects.get(token='invoice_warning_high_amount').value).first()
      except Exception:
          invoice_warning_negative = None
          invoice_warning_zero = None
          invoice_warning_bank_missing = None
          invoice_warning_payment_missing = None
          invoice_warning_simplified_over_400 = None
          invoice_warning_high_amount = None

      warning = None
      if invoice.total_final <= 0:
          warning = invoice_warning_negative
      elif invoice.total_final == 0:
          warning = invoice_warning_zero
      elif invoice.payment_type is None:
          warning = invoice_warning_payment_missing
      elif invoice.payment_type.token == 'DIRECT_DEBIT' and invoice.payment_bank is None:
          warning = invoice_warning_bank_missing
      elif invoice.simplified and invoice.total_final >= 400:
          warning = invoice_warning_simplified_over_400
      elif invoice.total_final and invoice_warning_high_amount:
          if is_high_amount_for_period(invoice.total_final, [contract], invoice.billing_period_year, invoice.billing_period_month, exclude_invoice_id=invoice.id):
              warning = invoice_warning_high_amount

      if warning:
          invoice.warning = warning
          invoice.save(update_fields=['warning'])

      # Double check it is associated to billing
      invoice.billing = billing
      invoice.save()

      return Response({"id": invoice.id, "message": "Contract processed individually and invoice created."}, status=status.HTTP_200_OK)

  @action(detail=True, methods=['post'], url_path='process-selected')
  def process_selected(self, request, pk=None):
      billing = self.get_object()
      contract_ids = request.data.get('contract_ids')
      if not contract_ids or not isinstance(contract_ids, list):
          return Response({"error": "contract_ids list is required."}, status=status.HTTP_400_BAD_REQUEST)

      from billing.tasks import process_selected_contracts_task
      task = process_selected_contracts_task.delay(billing.id, contract_ids)

      return Response({
          "task_id": task.id,
          "message": "Batch contract processing started asynchronously."
      }, status=status.HTTP_202_ACCEPTED)

  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()

class BillingRoutesView(views.APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = Billing.objects.all().order_by('-created_at')
  def get(self, request):
    try:
      # Validar les dades rebudes
      billing_id = request.query_params.get('id')
      if not billing_id:
        return Response({"error": "ID is required."}, status=status.HTTP_400_BAD_REQUEST)
      
      billing = Billing.objects.get(id=billing_id)
      
      pending_billing_status_token = ConfigProject.objects.get(token='batch_status_finish_token').value
      pending_billing_status = ReadingBatchStatus.objects.filter(token=pending_billing_status_token).order_by('created_at').first()
      reading_batches = ReadingBatch.objects.filter( status=pending_billing_status).all()
      
      response = []

      if billing.is_excluded:
        
        readings_count = billing.readings.count()
        
        response = [{
          'route': {'name': "Lectures excloses"},
          'batch': None,
          'processed_at': billing.created_at,
          'processed_readings': readings_count,
          'warning': False
        }]
        
        return Response(response, status=status.HTTP_200_OK)
      
      for route in billing.routes.all():
        
        # Find the first batch in reading_batches that has this route
        batch = reading_batches.filter(routes=route).first()
        
        # Count readings in the batch that have supply points in this route
        readings_count = 0
        
        # Get all supply points that belong to this route with active contracts
        contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
        active_contract_status = ContractStatus.objects.get(token=contract_active_token)
        route_supply_points = SupplyPoint.objects.filter(
            property__route_position__route=route
        ).filter(
            Q(contracts__status=active_contract_status) | Q(default_contracts__status=active_contract_status)
        ).distinct()

        # Count readings in the batch that have these supply points
        readings_count = billing.readings.filter(
            supply_point__in=route_supply_points
        ).count()
        
        route_data = RouteListSerializer(route).data
        
        response.append( {
          'route': route_data,
          'batch': batch.id if batch else None,
          'processed_at': batch.processed_at if batch else None,
          'processed_readings': readings_count,
          # 'reading_route': ReadingRouteMinimalSerializer(reading_route).data if reading_route else None,
          'warning': True if readings_count != route_data['num_total_readings'] else False
        })
        
    
      return Response(response, status=status.HTTP_200_OK)
    except Exception as e:
      return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class BillingBadgesView(views.APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = Billing.objects.all().order_by('-created_at')
  def get(self, request):
    try:
      # Validar les dades rebudes
      response = []
      exploitation_id = request.query_params.get('exploitation')
      try:
        exploitation = Exploitation.objects.get(id=exploitation_id)
      except Exception as e:
        print(e)
        pass
        
      
      default_status = BillingStatus.objects.get(is_default=True)
      processed_status_token = ConfigProject.objects.get(token='billing_batch_processed').value
      processed_status = BillingStatus.objects.get(token=processed_status_token)
      default_billings = Billing.objects.filter(status=default_status).exclude(status=processed_status).all()
      
      active_billings = Billing.objects.filter(billiing_archived=False).exclude(status=processed_status).all()
      
      
      
      # Filter by exploitation if provided
      if exploitation_id:
          default_billings = default_billings.filter(
              Q(invoices__exploitation__id=exploitation_id) |
              Q(routes__positions__properties__supply_points__connection__exploitation__id=exploitation_id) |
              Q(routes__positions__properties__supply_points__connection__exploitation__isnull=True)
          ).distinct()
          
          active_billings = active_billings.filter(
              Q(invoices__exploitation__id=exploitation_id) |
              Q(routes__positions__properties__supply_points__connection__exploitation__id=exploitation_id) |
              Q(routes__positions__properties__supply_points__connection__exploitation__isnull=True)
          ).distinct()
      
      if active_billings:
        total = 0
        for billing in active_billings:
          if billing.routes.exists():
            for r in billing.routes.all():
              total += route_count_total_readings(r)
        response.append({
          'token': 'Subministraments a facturar',
          'total': total
        })
        
      if default_billings:
        total = 0
        for billing in default_billings:
          if billing.routes.exists():
            for r in billing.routes.all():
              total += route_count_total_readings(r)
          else:
            for r in billing.routes.all():
              total += route_count_total_readings(r)
        
        response.append({
          'token': 'Pendents',
          'total': total
        })
      
      processing_status_token = ConfigProject.objects.get(token='billing_batch_processing').value
      processing_status = BillingStatus.objects.get(token=processing_status_token)
      processing_billings = Billing.objects.filter(status=processing_status).exclude(status=processed_status).all()
      
      if processing_billings:
        for billing in processing_billings:
          add_badges(response, billing, "processant")
      
      pending_billing_status_token = ConfigProject.objects.get(token='billing_batch_pending').value
      pending_status = BillingStatus.objects.get(token=pending_billing_status_token)
      pending_billings = Billing.objects.filter(status=pending_status).exclude(status=processed_status).all()
      
      if pending_billings:
        for billing in pending_billings:
          add_badges(response, billing, "pre-factures")
              
      processing_documents_status_token = ConfigProject.objects.get(token='billing_batch_processing_documents').value
      processing_documents_status = BillingStatus.objects.get(token=processing_documents_status_token)
      processing_documents_billings = Billing.objects.filter(status=processing_documents_status).exclude(status=processed_status).all()
      
      if processing_documents_billings:
        for billing in processing_documents_billings:
          add_badges(response, billing, "generant documents")
      
      # processed_status_token = ConfigProject.objects.get(token='billing_batch_processed').value
      # processed_status = BillingStatus.objects.get(token=processed_status_token)
      # processed_billings = Billing.objects.filter(status=processed_status).all()
      
      # print(processed_billings.count())
      
      # if processed_billings:
      #   for billing in processed_billings:
      #     add_badges(response, billing, "processades")
      
      return Response(response, status=status.HTTP_200_OK)

    except Exception as e:
      print(f"Error en obtenir les rutes de facturació: {str(e)}")
      return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
def add_badges(response, billing, key):
  token_found = False
  for item in response:
    if item['token'] == key:
      if billing.invoices.exists():
        item['total'] += billing.invoices.count()
      token_found = True
      break  # Exit inner loop after updating
  if not token_found:
    response.append({
      'token': key,
      'total': billing.invoices.count() if billing.invoices.exists() else 0
    })
    
class StartBillingView(views.APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = Billing.objects.all().order_by('-created_at')
  def get(self, request):
    try:

      biller_id = request.query_params.get('biller_id')
      if not biller_id:
        return Response({"error": "Biller ID is required."}, status=status.HTTP_400_BAD_REQUEST)

      # Codi i nom opcionals: si el frontend els envia (des del modal d'"Iniciar
      # facturació"), es fan servir tal qual (validant unicitat). Si no vénen,
      # es manté el comportament anterior de generar-los automàticament.
      custom_token = (request.query_params.get('token') or '').strip()
      custom_name = (request.query_params.get('name') or '').strip()

      current_year = timezone.now().date().year
      current_month = timezone.now().date().month
      biller = Biller.objects.get(id=biller_id)

      default_status = BillingStatus.objects.get(is_default=True)

      if custom_token or custom_name:
        token = custom_token or f"{biller.token}-{current_month}{current_year}"
        name = custom_name or f"Fact. {biller.name} - {current_month}{current_year}"

        if Billing.objects.filter(token=token, is_active=True).exists():
          return Response(
            {"error": f"Ja existeix una facturació amb el codi '{token}'."},
            status=status.HTTP_400_BAD_REQUEST
          )
      else:
        base_token = f"{biller.token}-{current_month}{current_year}"
        base_name = f"Fact. {biller.name} - {current_month}{current_year}"

        token = base_token
        name = base_name
        counter = 1
        while Billing.objects.filter(token=token, is_active=True).exists():
          token = f"{base_token}/{counter}"
          name = f"{base_name}/{counter}"
          counter += 1

      billing = Billing.objects.create(
        status = default_status,
        name = name,
        token = token,
        biller=biller,
        is_active=True)

      if biller.routes.exists():
        routes = biller.routes.all()
        billing.routes.set(routes)
      else:
        routes = Route.objects.filter(is_active = True).all()
        billing.routes.set(routes)
      billing.save()

      return Response({"message": "Billing process started.", "id": billing.id}, status=status.HTTP_200_OK)

    except Exception as e:
      print(f"Error en obtenir les rutes de facturació: {str(e)}")
      return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
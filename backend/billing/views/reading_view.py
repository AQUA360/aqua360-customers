import datetime
from django.db import transaction
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Prefetch, F, CharField, Value
from django.db.models.functions import Concat
from django.utils.translation import gettext as _

from auth.permissions import PermissionManager
from billing.models import Reading, ReadingBatch
from billing.serializers.reading_serializer import ReadingMinimalSerializer, ReadingSaveSerializer, ReadingSerializer, ReadingDetailSerializer, ReadingByBatchSerializer, ReadingByBatchMinimalSerializer
from billing.serializers.reading_serializer import (
    ReadingSerializer,
    ReadingDetailSerializer,
    ReadingByBatchSerializer,
    ReadingByBatchMinimalSerializer
)
from billing.filter.reading_filter import ReadingFilter
from billing.utils.request_initial_reading_service import (
    get_transferable_reading,
    restore_transferred_readings,
    transfer_reading_as_initial,
)
from billing.utils.reading_service import (
    check_billing_period,
    get_estimated_reading_minimal_object,
    get_estimated_reading,
    READING_ESTIMATE_PERIOD_CHOICES,
    READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
    READING_ESTIMATE_STATISTIC_CHOICES,
    READING_ESTIMATE_STATISTIC_MEAN,
    modify_existing_readings,
    recalculate_estimated_readings,
)
from contract.models import Contract, ContractRequest, ContractTerminationRequest
from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, SupplyPoint
from service.serializers.meter_serializer import MeterListSerializer
from billing.tasks import export_readings_task
from documentmanager.utils.export_jobs import enqueue_export, export_job_response
from communication.utils.communication_process_service import add_reading_to_communication_process
class ReadingViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = Reading.objects.all().filter(is_active=True).order_by('-reading_date', 'is_close', '-created_at', '-reading_value')
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = ReadingFilter
  search_fields = ['token', 'contract__token', 'meter__code']
  ordering_fields = [
      'token',
      'calculated_value',
      'reading_value',
      'routeposition_position',
      'routeposition_code',
  ]

  def get_queryset(self):
    qs = super().get_queryset()
    ordering = self.request.query_params.get('ordering', '') if hasattr(self, 'request') else ''
    ordering_fields = {o.lstrip('-') for o in ordering.split(',') if o}

    if 'routeposition_position' in ordering_fields:
      qs = qs.annotate(
          routeposition_position=F('supply_point__property__route_position__position')
      )
    if 'routeposition_code' in ordering_fields:
      qs = qs.annotate(
          routeposition_code=F('supply_point__property__route_position__token')
      )
    return qs

  def get_serializer_class(self):
    if self.action == 'create':
      return ReadingSaveSerializer
    return ReadingSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context

  def filter_queryset(self, queryset):
    queryset = super().filter_queryset(queryset)
    if queryset.ordered:
        ordering = list(queryset.query.order_by)
        if 'contract__token' not in ordering and '-contract__token' not in ordering:
            ordering.append('contract__token')
        if 'id' not in ordering and '-id' not in ordering:
            ordering.append('id')
        return queryset.order_by(*ordering)
    return queryset.order_by('-reading_date', 'contract__token', 'id')
  
  @action(detail=False, methods=['get'], url_path='by-batch')
  def list_by_batch(self, request):
    #GET /api/readings/by-batch/?batch=1
    batch_id = request.query_params.get('batch')
    if not batch_id:
      return Response({"error": "Batch ID is required"}, status=400)
    
    batch_readings = Reading.objects.filter(batch_id=batch_id, is_control=False)
    
    # Calculate global median for this batch
    all_values = list(batch_readings.values_list('consumption_days', flat=True))
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

    queryset = self.filter_queryset(self.get_queryset().filter(batch_id=batch_id, is_control=False).order_by('-reading_date'))
    
    # Manually filter by date range if requested
    alert_val = request.query_params.get('alert')
    if alert_val == 'warning_date_range' and n_all > 0:
        margin_high = median * 1.25
        margin_low = median * 0.75
        queryset = queryset.filter(Q(consumption_days__gt=margin_high) | Q(consumption_days__lt=margin_low))

    paginator = PageNumberPagination()
    paginator.page_size = 50
    result_page = paginator.paginate_queryset(queryset, request)
    serializer = ReadingByBatchSerializer(result_page, many=True)
    
    response = paginator.get_paginated_response(serializer.data)
    response.data['date_range_median'] = median
    response.data['date_range_above_margin_count'] = global_count_above_margin
    return response
  @action(detail=False, methods=['get'], url_path='by-batch-minimal')
  def list_by_batch_minimal(self, request):
    #GET /api/readings/by-batch/?batch=1
    batch_id = request.query_params.get('batch')
    if not batch_id:
      return Response({"error": "Batch ID is required"}, status=400)
    
    batch_readings = Reading.objects.filter(batch_id=batch_id, is_close=False, is_control=False)
    
    # Calculate global median for this batch
    all_values = list(batch_readings.values_list('consumption_days', flat=True))
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

    queryset = self.filter_queryset(
        self.get_queryset()
        .filter(batch_id=batch_id, is_close=False, is_control=False)
        .select_related('supply_point__property__route_position')
        .order_by('-reading_date')
    )

    # Manually filter by date range if requested
    alert_val = request.query_params.get('alert')
    if alert_val == 'warning_date_range' and n_all > 0:
        margin_high = median * 1.25
        margin_low = median * 0.75
        queryset = queryset.filter(Q(consumption_days__gt=margin_high) | Q(consumption_days__lt=margin_low))

    paginator = PageNumberPagination()
    paginator.page_size = 50
    result_page = paginator.paginate_queryset(queryset, request)
    serializer = ReadingByBatchMinimalSerializer(result_page, many=True)
    
    response = paginator.get_paginated_response(serializer.data)
    response.data['date_range_median'] = median
    response.data['date_range_above_margin_count'] = global_count_above_margin
    return response
  
  @action(detail=False, methods=['post'], url_path='estimate')
  def estimate_reading(self, request):
    supply_points = SupplyPoint.objects.filter(id__in=request.data.get('supply_points'))
    reading_date = request.data.get('reading_date', None)
    active_contract = ConfigProject.objects.get(token="contract_active_token").value
    dry = request.data.get('dry', False)

    period = request.data.get('period')
    if period and period not in READING_ESTIMATE_PERIOD_CHOICES:
        return Response(
            {'error': f'Periode invalid "{period}". Opcions: {", ".join(READING_ESTIMATE_PERIOD_CHOICES)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    statistic = request.data.get('statistic')
    if statistic and statistic not in READING_ESTIMATE_STATISTIC_CHOICES:
        return Response(
            {'error': f'Estadistic invalid "{statistic}". Opcions: {", ".join(READING_ESTIMATE_STATISTIC_CHOICES)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    PERIOD_MONTHS_MAP = {
        'trimestral': 90,
        'semestral': 180,
        'bimestral': 60,
        'quadrimestral': 120,
        'anual': 360,
        'mensual': 30,
    }
    
    if isinstance(reading_date, str):
        try:
            reading_date = datetime.datetime.strptime(reading_date, '%Y-%m-%d').date()
        except ValueError:
            reading_date = datetime.datetime.now().date()
    
    print("reading_date", reading_date)
    
    readings = []
    today = datetime.datetime.now().date()
    for supply_point in supply_points:
        try:
          biller = supply_point.property.route_position.route.biller
          period_days = PERIOD_MONTHS_MAP[biller.period_type] if biller else 90
        except Exception as e:
          biller = None
          period_days = 90
          
        for contract in supply_point.contracts.filter(status__token=active_contract):
            if period or statistic:
                # Comportament configurable: només s'activa si el front ha triat explicitament
                # periode/estadistic. Sense aquests parametres es manté el comportament original.
                reading = get_estimated_reading(
                    supply_point, contract, reading_date, batch=None,
                    offset_days=period_days,
                    period=period or READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
                    statistic=statistic or READING_ESTIMATE_STATISTIC_MEAN,
                    create_reading=not dry,
                    max_day_limit=today,
                )
            else:
                reading = get_estimated_reading_minimal_object(supply_point, contract, reading_date, None, offset_days=period_days, max_day_limit = today, create_reading=not dry)
            if reading:
              readings.append(reading)
    
    return Response({
        'readings': ReadingMinimalSerializer(readings, many=True).data if not dry else readings,
        'status': 'ok'
    })
  
  @action(detail=False, methods=['post'], url_path='request-reading')
  def save_initial_reading(self, request):
    contract_request_id = request.data.get('contract_request_id', None)
    meter_id = request.data.get('meter_id', None)
    reading_value = request.data.get('reading_value', None)
    reading_date = request.data.get('reading_date', None)
    leak_value = request.data.get('leak_value', None)

    try:
      contract_request = ContractRequest.objects.get(id=contract_request_id)
    except Exception as e:
      return Response({
        'error': 'Contract request not found',
        'status': 'error'
      }, status=status.HTTP_404_NOT_FOUND)

    try:
      meter = Meter.objects.get(id=meter_id)
      supply_point = meter.supply_points.first()
    except Meter.DoesNotExist:
      if contract_request.meter_mode != 'fictional':
        return Response({
          'error': _('Meter not found'),
          'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)

      supply_point = contract_request.supply_point_default
      if not supply_point:
        return Response({
          'error': _('Supply point not found'),
          'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)

      from contract.utils.contract_service import _create_fictitious_meter
      no_meter_status_token = ConfigProject.objects.get(token='token_meter_status_no_meter').value
      no_meter_status = MeterStatus.objects.get(token=no_meter_status_token)
      meter = _create_fictitious_meter(no_meter_status)
      supply_point.meter = meter
      supply_point.save(update_fields=['meter'])
    
    try:
      # Una lectura del contracte anterior traspassada com a inicial no s'esborra: es
      # retorna al seu contracte.
      restore_transferred_readings(contract_request, supply_point)
      existing_readings = Reading.objects.filter(
        contract_request=contract_request, supply_point=supply_point, is_initial=True
        ).distinct()
      existing_readings.delete()
    except Exception as e:
      pass
    
    reading = Reading.objects.create(
      contract_request=contract_request,
      meter=meter,
      supply_point=supply_point,
      reading_value=reading_value,
      reading_date=reading_date if reading_date else None,
      leak_value=leak_value if leak_value not in (None, '') else None,
      is_initial=True,
      is_active=False,
      consumption_days=0,
    )
    
    return Response({
        'reading': ReadingMinimalSerializer(reading).data,
        'status': 'ok'
    })
  
  @action(detail=False, methods=['get'], url_path='request-transferable-reading')
  def get_request_transferable_reading(self, request):
    """"Facturar període complert": darrera lectura no facturada del contracte anterior."""
    contract_request_id = request.query_params.get('contract_request_id', None)
    supply_point_id = request.query_params.get('supply_point_id', None)
    meter_id = request.query_params.get('meter_id', None)

    contract_request = ContractRequest.objects.filter(id=contract_request_id).first()
    supply_point = SupplyPoint.objects.filter(id=supply_point_id).first()
    meter = Meter.objects.filter(id=meter_id).first()
    if not contract_request:
      return Response({
        'error': 'Contract request not found',
        'status': 'error'
      }, status=status.HTTP_404_NOT_FOUND)

    reading = get_transferable_reading(contract_request, supply_point, meter)
    return Response({
        'reading': ReadingMinimalSerializer(reading).data if reading else None,
        'status': 'ok'
    })

  @action(detail=False, methods=['post'], url_path='request-transfer-reading')
  def transfer_request_reading(self, request):
    """Fa servir la lectura no facturada del contracte anterior com a lectura inicial de l'alta."""
    contract_request_id = request.data.get('contract_request_id', None)
    reading_id = request.data.get('reading_id', None)

    contract_request = ContractRequest.objects.filter(id=contract_request_id).first()
    reading = Reading.objects.filter(id=reading_id).first()
    if not contract_request or not reading:
      return Response({
        'error': 'Contract request or reading not found',
        'status': 'error'
      }, status=status.HTTP_404_NOT_FOUND)

    if not contract_request.bill_full_period:
      return Response({
        'error': _('The contract request does not bill the full period'),
        'status': 'error'
      }, status=status.HTTP_400_BAD_REQUEST)

    # Es torna a comprovar al servidor: la lectura ha de continuar sent la darrera lectura
    # no facturada del contracte anterior.
    transferable = get_transferable_reading(contract_request, reading.supply_point, reading.meter)
    if not transferable or transferable.id != reading.id:
      return Response({
        'error': _('The reading can no longer be used as initial reading'),
        'status': 'error'
      }, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
      reading = transfer_reading_as_initial(contract_request, reading)

    return Response({
        'reading': ReadingMinimalSerializer(reading).data,
        'status': 'ok'
    })

  @action(detail=False, methods=['post'], url_path='filter-export')
  def get_filter_export(self, request):
    batch_id = request.data.get('batch_id', None)
    filter_reading_start_date = request.data.get('filter_reading_start_date', None)
    filter_reading_end_date = request.data.get('filter_reading_end_date', None)
    selected_reader_alerts = request.data.get('selected_reader_alerts', None)
    selected_remote_alerts = request.data.get('selected_remote_alerts', None)
    selected_reading_alert_types = request.data.get('selected_reading_alert_types', None)
    selected_min_consumption = request.data.get('selected_min_consumption', None)
    selected_max_consumption = request.data.get('selected_max_consumption', None)
    select_remote = request.data.get('select_remote', None)
    select_reader = request.data.get('select_reader', None)
    select_estimated = request.data.get('select_estimated', None)
    
    
    filters = Q()
    if batch_id:
      filters &= Q(batch_id=batch_id)
    if filter_reading_start_date:
      filters &= Q(reading_date__gte=filter_reading_start_date)
    if filter_reading_end_date:
      filters &= Q(reading_date__lte=filter_reading_end_date)
    if selected_reader_alerts:
      filters &= Q(reader_alert__id__in=selected_reader_alerts)
    if selected_remote_alerts:
      filters &= Q(remote_alert__id__in=selected_remote_alerts)
    if selected_reading_alert_types:
      filters &= Q(alert__id__in=selected_reading_alert_types)
    if selected_min_consumption:
      filters &= Q(calculated_value__gte=selected_min_consumption)
    if selected_max_consumption:
      filters &= Q(calculated_value__lte=selected_max_consumption)
    if select_remote and not select_reader:
      filters &= Q(meter__has_remote_reading=True, meter__force_manual_reading=False)
    if select_reader and not select_remote:
      filters &= Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True)
    if select_estimated:
      filters &= Q(is_estimated=True)
      
    
    queryset = self.filter_queryset(self.get_queryset().filter(filters))
    reading_ids = queryset.values_list('id', flat=True)
    return Response({
        'reading_ids': list(reading_ids),
        'status': 'ok'
    })
    
  @action(detail=False, methods=['post'], url_path='export-readings')
  def export_readings(self, request):
    reading_ids = request.data.get('reading_ids', None)
    columns_param = request.query_params.get('columns')
    columns = [c.strip() for c in columns_param.split(',') if c.strip()] if columns_param else None

    job = enqueue_export(
        request, export_readings_task, kind="readings",
        name=request.query_params.get('export_name') or str(_("Readings")),
        args=[reading_ids], kwargs={"columns": columns},
        params={"columns": columns, "total": len(reading_ids or [])},
    )
    return Response(export_job_response(job), status=status.HTTP_202_ACCEPTED)
    
  @action(detail=False, methods=['post'], url_path='get-modification-data')
  def get_modification_data(self, request):
    contract_id = request.data.get('contract_id', None)
    supply_point_id = request.data.get('supply_point_id', None)
    reading_batch_billed_token = ConfigProject.objects.get(token='reading_batch_billed_token').value
    billing_batch_cancelled = ConfigProject.objects.get(token='billing_batch_cancelled').value
    active_contract = ConfigProject.objects.get(token='contract_active_token').value
    termination_cancelled_status_token = ConfigProject.objects.get(token='contract_termination_cancelled_token').value
    reading_estimate_limit_percentage = ConfigProject.objects.get(token='reading_estimate_limit_percentage').value  #used as well for periods
    config_status_tokens = [
            "billing_batch_processing_documents",
            "billing_batch_pending",
            "billing_batch_processing"
        ]
    billing_status_pending_token = ConfigProject.objects.filter(token__in=config_status_tokens).values_list('value', flat=True)
        
    mod_contract = Contract.objects.get(id=contract_id)
    mod_supply_point = SupplyPoint.objects.get(id=supply_point_id)
    
    readings = Reading.objects.filter(
      contract__id=contract_id, supply_point__id=supply_point_id,
      # is_control=False, 
      is_active=True
      ).order_by('-reading_date', '-created_at')[:15]
    
    serialized_readings = ReadingSerializer(readings, many=True).data
    meters = Meter.objects.filter(
      Q(id__in=readings.values_list('meter', flat=True)) |
      Q(supply_points__id=supply_point_id)
      ).distinct()
    serialized_meters = MeterListSerializer(meters, many=True).data
    batches = ReadingBatch.objects.filter(
      routes__id__in=readings.values_list('supply_point__property__route_position__route__id', flat=True),
    ).order_by('-created_at').distinct()[:5]
    
    if mod_supply_point.meter:
        contracts_in_meter = Contract.objects.filter(
          supply_points__meter__id=mod_supply_point.meter.id,
          status__token=active_contract
          ).distinct()
    else:
        contracts_in_meter = Contract.objects.none()
    
    contracts_serialized = [{
      'id': contract.id,
      'token': contract.token,
      'holder': str(contract.holder),
      'pending_billing': Reading.objects.filter(
        contract=contract,
        is_control=False,
        billing__status__token__in=billing_status_pending_token
      ).count() > 0,
    } for contract in contracts_in_meter]
    
    batches_serialized =[
      {
        'id': batch.id,
        'name': batch.name,
        'token': batch.token,
        'status': batch.status.name,
        'status_token': batch.status.token,
        'status_color': batch.status.color,
      } for batch in batches
    ]
    PERIOD_MONTHS_MAP = {
        'trimestral': 90,
        'semestral': 180,
        'bimestral': 60,
        'quadrimestral': 120,
        'anual': 360,
        'mensual': 30,
    }
    
    try:
      biller = mod_contract.supply_point_default.property.route_position.route.biller
    except Exception as e:
      biller = None
    
    billing_period_serialized = {
      'limit': reading_estimate_limit_percentage,
      'period_name': biller.period_type if biller else None,
      'period_days': PERIOD_MONTHS_MAP[biller.period_type] if biller else None,
    }
    
    meter_last_reading = None
    if mod_supply_point.meter:
        meter_last_reading = Reading.objects.filter(meter=mod_supply_point.meter, is_active=True).order_by('-reading_date').first()
    meter_last_reading_val = meter_last_reading.reading_value if meter_last_reading else None
    
    termination_reading = None
    
    try:
      termination = ContractTerminationRequest.objects.filter(
        contract__id=contract_id,
        is_active=True
        ).exclude(
        status__token=termination_cancelled_status_token
      ).order_by('-created_at').first()
    except Exception as e:
      termination = None
      print("error getting termination reading", e)
      
    if termination:
      termination_readings = termination.readings.filter(
        is_active=True,
        is_control=False,
        is_close=False,
        is_initial=False,
        contract__id=contract_id,
        supply_point__id=supply_point_id,
      ).distinct()
      latest_termination_reading = termination_readings.order_by('-reading_date').first()
      latest_reading = readings.first()  # already ordered by -reading_date and sliced
      if latest_termination_reading and latest_reading and latest_termination_reading.id == latest_reading.id:
        termination_reading = latest_termination_reading.id
      
    
        
    return Response({
      'readings': serialized_readings,
      'meters': serialized_meters,
      'batches': batches_serialized,
      'contracts': contracts_serialized,
      'period_data': billing_period_serialized,
      'contract_created_at': mod_contract.registration_date if mod_contract.registration_date else mod_contract.created_at,   #IN CASE OF INITIAL READING FOR NEW CONTRACT
      'meter_last_reading': meter_last_reading_val,  #IN CASE OF INITIAL READING FOR NEW CONTRACT
      'termination_reading': termination_reading,  #IN CASE OF TERMINATION READING ALLOW TO EDIT WITHOUT CHECKING BILLING PERIOD
      'status': 'ok'
    })
  
  @action(detail=False, methods=['post'], url_path='modified-readings')
  def modify_readings(self, request):
    readings_data = request.data.get('readings_data', None)
    readings_to_update = request.data.get('readings_to_update', None)
    readings_to_delete = request.data.get('readings_to_delete', None)
    
    if readings_to_delete and not request.user.has_perm('billing.delete_reading'):
        return Response({'error': 'No tens permisos per esborrar lectures'}, status=status.HTTP_403_FORBIDDEN)
    response = modify_existing_readings(readings_data, readings_to_update, readings_to_delete, user=request.user)
    return response
  
  @action(detail=True, methods=['get'], url_path='add-to-communication-process')
  def add_to_communication_process(self, request, pk=None):
    reading = self.get_object()
    user = request.user
    
    reading = add_reading_to_communication_process(reading, user)
    serialized_reading = ReadingByBatchMinimalSerializer(reading).data
    return Response({
      'reading': serialized_reading,
      'status': 'ok'
    })
    
  
  @action(detail=False, methods=['post'], url_path='recalculate-estimated')
  def recalculate_estimated(self, request):
    reading_ids = request.data.get('reading_ids', [])
    if not reading_ids:
      return Response({'error': 'reading_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

    updated_readings = recalculate_estimated_readings(reading_ids)
    return Response({
      'readings': ReadingMinimalSerializer(updated_readings, many=True).data,
      'updated_count': len(updated_readings),
      'status': 'ok'
    })

  @action(detail=False, methods=['post'], url_path='check-allow-period')
  def check_allow_ny_period(self, request):
      previous_reading_id = request.data.get('previous_reading_id', None)
      reading_date = request.data.get('reading_date', None)
      supply_point = request.data.get('supply_point', None)
      contract = request.data.get('contract', None)
      is_control = request.data.get('is_control', None)
      meter = request.data.get('meter', None)
      
      if is_control:
        return Response({'allow': True}, status=status.HTTP_200_OK)
      
      if isinstance(supply_point, int):
        supply_point = SupplyPoint.objects.get(id=supply_point)
      
      reading_date_date = datetime.datetime.strptime(reading_date, '%Y-%m-%d').date()
      
      previous_reading = None
      if previous_reading_id:
          previous_reading = Reading.objects.filter(id=previous_reading_id).first()
      
      if not previous_reading or previous_reading.reading_date > reading_date_date:
          previous_reading = Reading.objects.filter(
              supply_point=supply_point,
              meter=meter,
              contract=contract,
              reading_value__isnull=False,
              reading_date__lt=reading_date_date).exclude(is_control=True).order_by('-reading_date').first()
          if not previous_reading:
            previous_reading = Reading.objects.filter(
                supply_point=supply_point,
                meter=meter,
                reading_value__isnull=False,
                reading_date__lt=reading_date_date).exclude(is_control=True).order_by('-reading_date').first()
          
      print("previous_reading", previous_reading)
      print("supply_point", supply_point)
      print("meter", meter)
      print("reading_date", reading_date_date)
      
      allow_by_period = check_billing_period(reading_date_date, supply_point, meter, contract, previous_reading)
      
      print("allow_by_period", allow_by_period)
      
      return Response({'allow': allow_by_period}, status=status.HTTP_200_OK)
    
    
  @action(detail=False, methods=['get'], url_path='permissions')
  def permissions(self, request):
      pk = request.query_params.get('id')
      if pk:
          from django.contrib.auth.models import Group
          user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
          if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
              return Response( None, status=status.HTTP_403_FORBIDDEN )
          group = Group.objects.filter(id=pk).first()
          if not group:
              return Response( None, status=status.HTTP_404_NOT_FOUND )
          group_permissions = PermissionManager.get_model_group_permissions(group, 'reading')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'reading', 'billing')
      return Response(permissions, status=status.HTTP_200_OK)
      
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()

class ReadingDetailViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = Reading.objects.all().filter(is_active=True).order_by('-reading_date')
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = ReadingFilter
  search_fields = ['token']
  ordering_fields = ['token']
  
  def filter_queryset(self, queryset):
    queryset = super().filter_queryset(queryset)
    if queryset.ordered:
        ordering = list(queryset.query.order_by)
        if 'contract__token' not in ordering and '-contract__token' not in ordering:
            ordering.append('contract__token')
        if 'id' not in ordering and '-id' not in ordering:
            ordering.append('id')
        return queryset.order_by(*ordering)
    return queryset.order_by('-reading_date', 'contract__token', 'id')
  
  def get_serializer_class(self):
    
    return ReadingDetailSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context

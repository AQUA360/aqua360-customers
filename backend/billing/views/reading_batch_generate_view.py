from rest_framework.decorators import action
from decimal import Decimal

from rest_framework import status, views, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from celery.result import AsyncResult

from billing.models import ReadingBatch, ReadingBatchStatus, Reading
from billing.serializers.reading_batch_serializer import ReadingBatchStatusSerializer
from billing.tasks import process_reading_batch, assign_readings_task, assign_smart_metering_task, preview_smart_metering_task
from django.db.models import Count, F, ExpressionWrapper, fields, Q
from billing.permissions import ReadingPermission
from coredata.models import ConfigProject
from service.models import Meter, SupplyPoint
from billing.utils.reading_filters import PENDING_READING_FILTER, BILLED_READING_FILTER
from billing.utils.reading_batch_service import get_setup_filter_supply_point_ids


class ReadingBatchSummaryView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, ReadingPermission]
    queryset = ReadingBatch.objects.all().order_by('-created_at')
    def create(self, request):
        try:
            batch_id = request.data.get('id')

            reading_batch = ReadingBatch.objects.get(id=batch_id)
            
            processing_token = ConfigProject.objects.get(token='reading_batch_processing_token').value
            batch_status = ReadingBatchStatus.objects.get(token=processing_token)
            reading_batch.status = batch_status
            reading_batch.save()

            task = process_reading_batch.delay(reading_batch.id)
            
            reading_batch.task_id = task.id
            reading_batch.save()
            
            return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request):
        try:
            # Validar les dades rebudes
            batch_id = request.query_params.get('batch_id')
            if not batch_id:
                return Response({"error": "Batch ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            # Optimize the initial query with prefetch_related to avoid N+1 queries
            batch = ReadingBatch.objects.select_related('status').prefetch_related(
                'routes__positions__properties__supply_points__contracts__status',
                'fix_meters__supply_points__contracts__status',
                'readings__alert',
                'documents__readings'
            ).get(id=batch_id)
            
            
            # Get config values once
            pending_processing_token = ConfigProject.objects.get(token='reading_batch_pending_processing_token').value
            pending_token = ConfigProject.objects.get(token='reading_batch_pending_token').value
            default_status = ReadingBatchStatus.objects.get(is_default=True)
            active_contract = ConfigProject.objects.get(token='contract_active_token').value
            
            supply_active_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
            supply_cut_token = ConfigProject.objects.get(token='supply_point_status_cut_token').value
            
            include_telecontrol = batch.include_telecontrol
            include_manual = batch.include_manual

            from service.models import SupplyPoint
            # Count supply points without route position in the batch's exploitations
            exploitation_ids = [eid for eid in batch.routes.all().values_list('positions__address_city__exploitations__id', flat=True).distinct() if eid]
            no_route_supply_points_count = 0
            if exploitation_ids:
                 no_route_supply_points_count = SupplyPoint.objects.filter(
                    is_active=True,
                    status__token__in=[supply_active_token, supply_cut_token],
                    meter__is_active=True,
                    contracts__status__token=active_contract,
                    contracts__is_active=True
                ).filter(
                    Q(property__route_position__isnull=True) | Q(property__isnull=True)
                ).filter(
                    Q(property__address_city__exploitations__id__in=exploitation_ids) |
                    Q(address__city__exploitations__id__in=exploitation_ids)
                ).distinct().count()
            
            manual_supplypoints = 0
            manual_supplypoints_contracts = 0
            telecontrol_supplypoints = 0
            telecontrol_supplypoints_contracts = 0
            fix_supplypoints = 0
            fix_supplypoints_contracts = 0
            if include_telecontrol:
                # Telecontrol: count active meters (including sub-meters), not contracts
                telecontrol_supplypoints = batch.routes.aggregate(
                    total=Count(
                        'positions__properties__supply_points__meter',
                        filter=Q(
                            positions__properties__supply_points__meter__has_remote_reading=True,
                            positions__properties__supply_points__meter__force_manual_reading=False,
                            positions__properties__supply_points__meter__is_active=True,
                        ),
                        distinct=True,
                    )
                    + Count(
                        'positions__properties__supply_points__meter__sub_meters',
                        filter=Q(
                            positions__properties__supply_points__meter__sub_meters__has_remote_reading=True,
                            positions__properties__supply_points__meter__sub_meters__force_manual_reading=False,
                            positions__properties__supply_points__meter__sub_meters__is_active=True,
                        ),
                        distinct=True,
                    )
                )['total'] or 0
                telecontrol_supplypoints_contracts = batch.routes.aggregate(
                    total=Count(
                        'positions__properties__supply_points__meter',
                        filter=Q(
                            positions__properties__supply_points__meter__has_remote_reading=True,
                            positions__properties__supply_points__meter__force_manual_reading=False,
                            positions__properties__supply_points__meter__is_active=True,
                            positions__properties__supply_points__contracts__status__token=active_contract,
                            positions__properties__supply_points__contracts__is_active=True,
                        ),
                        distinct=True,
                    )
                    + Count(
                        'positions__properties__supply_points__meter__sub_meters',
                        filter=Q(
                            positions__properties__supply_points__meter__sub_meters__has_remote_reading=True,
                            positions__properties__supply_points__meter__sub_meters__force_manual_reading=False,
                            positions__properties__supply_points__meter__sub_meters__is_active=True,
                            positions__properties__supply_points__contracts__status__token=active_contract,
                            positions__properties__supply_points__contracts__is_active=True,
                        ),
                        distinct=True,
                    )
                )['total'] or 0
            if include_manual:
                # Manual: count active meters (including sub-meters), not contracts
                manual_supplypoints = batch.routes.aggregate(
                    total=Count(
                        'positions__properties__supply_points__meter',
                        filter=Q(
                            positions__properties__supply_points__meter__is_active=True,
                        ) & (
                            Q(positions__properties__supply_points__meter__has_remote_reading=False)
                            | Q(positions__properties__supply_points__meter__force_manual_reading=True)
                        ),
                        distinct=True,
                    )
                    + Count(
                        'positions__properties__supply_points__meter__sub_meters',
                        filter=Q(
                            positions__properties__supply_points__meter__sub_meters__is_active=True,
                        ) & (
                            Q(positions__properties__supply_points__meter__sub_meters__has_remote_reading=False)
                            | Q(positions__properties__supply_points__meter__sub_meters__force_manual_reading=True)
                        ),
                        distinct=True,
                    )
                )['total'] or 0
                manual_supplypoints_contracts = batch.routes.aggregate(
                    total=Count(
                        'positions__properties__supply_points__meter',
                        filter=Q(
                            positions__properties__supply_points__meter__is_active=True,
                            positions__properties__supply_points__contracts__status__token=active_contract,
                            positions__properties__supply_points__contracts__is_active=True,
                        ) & (
                            Q(positions__properties__supply_points__meter__has_remote_reading=False)
                            | Q(positions__properties__supply_points__meter__force_manual_reading=True)
                        ),
                        distinct=True,
                    )
                    + Count(
                        'positions__properties__supply_points__meter__sub_meters',
                        filter=Q(
                            positions__properties__supply_points__meter__sub_meters__is_active=True,
                            positions__properties__supply_points__contracts__status__token=active_contract,
                            positions__properties__supply_points__contracts__is_active=True,
                        ) & (
                            Q(positions__properties__supply_points__meter__sub_meters__has_remote_reading=False)
                            | Q(positions__properties__supply_points__meter__sub_meters__force_manual_reading=True)
                        ),
                        distinct=True,
                    )
                )['total'] or 0
            if batch.fix_meters.exists() and batch.fix_meters.count() > 0:
                fix_supplypoints = batch.fix_meters.aggregate(
                    total=Count('supply_points__id', distinct=True)
                )['total'] or 0
                fix_supplypoints_contracts = SupplyPoint.objects.filter(
                    meter__in=batch.fix_meters.all(),
                    contracts__status__token=active_contract,
                    contracts__is_active=True
                ).distinct().count()
                # print("total fix meters:", batch.fix_meters.count())
                # print("fix_supplypoints_contracts:", fix_supplypoints_contracts)
            total_supplypoints = telecontrol_supplypoints + manual_supplypoints + fix_supplypoints
            total_supplypoints_contracts = telecontrol_supplypoints_contracts + manual_supplypoints_contracts + fix_supplypoints_contracts
            # print("total_supplypoints_contracts:", total_supplypoints_contracts)
            counters = {}
            counters_pending = {}
            
            # Optimize readings count calculation
            non_control_readings = batch.readings.filter(is_control=False)

            pending_filter = PENDING_READING_FILTER

            # Els apartats del pas de lectures pendents es compten amb la mateixa
            # funció que fa servir el llistat del setup (?readings=<filtre>), de
            # manera que el número i el detall que s'obre sempre coincideixen.
            def count_setup_filter(filter_key):
                return len(get_setup_filter_supply_point_ids(batch, filter_key, active_contract))

            counters_pending = {
                "assigned_readings": non_control_readings.filter(PENDING_READING_FILTER).distinct().count(),
                "already_billed": non_control_readings.filter(invoices__type_final='F').distinct().count(),
                "missing_readings": count_setup_filter('missing'),
                "discarded_readings": count_setup_filter('extra'),
                "readings_with_reader_alerts": count_setup_filter('reader_alert'),
                "readings_with_remote_alerts": count_setup_filter('remote_alert'),
                "readings_without_reading_value": count_setup_filter('no_reading_value'),
                "readings_remote_reading": count_setup_filter('remote_reader'),
                "readings_inactive_supplypoints": count_setup_filter('inactive_sp'),
                "no_route_supply_points_count": no_route_supply_points_count,
            }

            # Breakdown per reader alert type (ReaderAlert.name), so the pending
            # steps ("Configuració"/"Lectures") can surface which specific reader
            # alerts are present, not just the aggregate readings_with_reader_alerts count.
            reader_alert_counts_pending = non_control_readings.filter(
                reader_alert__isnull=False
            ).filter(pending_filter).values('reader_alert__name').annotate(
                count=Count('id')
            ).order_by('reader_alert__name')
            counters_pending['reader_alert_breakdown'] = {
                item['reader_alert__name']: item['count'] for item in reader_alert_counts_pending
            }

            # Only process alerts if batch is not pending and has readings
            if (batch.status.token != pending_processing_token and 
                batch.status.token != default_status.token and 
                non_control_readings.exists()):
                
                # Mateixa base que el llistat ReadingViewSet.list_by_batch_minimal
                # (filtres alert=any/null/<nom> i billed=true), perquè cada número
                # coincideixi amb les lectures que es mostren en obrir-lo.
                batch_readings = non_control_readings.filter(is_close=False)
                alert_counts = batch_readings.filter(
                    alert__isnull=False
                ).values('alert__name').annotate(
                    count=Count('id', distinct=True)
                ).order_by('alert__name')
                
                counters['total'] = batch_readings.distinct().count()
                counters['total_billed'] = batch_readings.filter(BILLED_READING_FILTER).distinct().count()
                counters['total_warnings'] = batch_readings.filter(alert__isnull=False).distinct().count()
                counters['total_correct'] = batch_readings.filter(alert__isnull=True).distinct().count()
                
                # Convert to dict format
                for alert in alert_counts:
                    counters[alert['alert__name']] = alert['count']
            
            # Build filters dynamically based on include flags
            meter_filter = Q()
            submeter_filter = Q()
            contract_meter_filter = Q(
                positions__properties__supply_points__contracts__status__token=active_contract,
                positions__properties__supply_points__contracts__is_active=True
            )
            
            
            if include_manual and not include_telecontrol:
                meter_filter = Q(positions__properties__supply_points__meter__has_remote_reading=False) | Q(positions__properties__supply_points__meter__force_manual_reading=True)
                submeter_filter = Q(positions__properties__supply_points__meter__sub_meters__has_remote_reading=False) | Q(positions__properties__supply_points__meter__sub_meters__force_manual_reading=True)
                contract_meter_filter &= Q(positions__properties__supply_points__meter__has_remote_reading=False) | Q(positions__properties__supply_points__meter__force_manual_reading=True)
            elif include_telecontrol and not include_manual:
                meter_filter = Q(positions__properties__supply_points__meter__has_remote_reading=True, positions__properties__supply_points__meter__force_manual_reading=False)
                submeter_filter = Q(positions__properties__supply_points__meter__sub_meters__has_remote_reading=True, positions__properties__supply_points__meter__sub_meters__force_manual_reading=False)
                contract_meter_filter &= Q(positions__properties__supply_points__meter__has_remote_reading=True, positions__properties__supply_points__meter__force_manual_reading=False)
            # If both are True or both are False, no additional filters are needed
            
            token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
            supplies_contracts_data = batch.routes.aggregate(
                num_supplies=(
                    Count('positions__properties__supply_points__meter', filter=meter_filter, distinct=True) + 
                    Count('positions__properties__supply_points__meter__sub_meters', filter=submeter_filter, distinct=True)
                ),
                num_contracts=Count(
                    'positions__properties__supply_points__contracts__id',
                    filter=contract_meter_filter,
                    distinct=True
                ),
                num_no_meter=(
                    Count('positions__properties__supply_points__meter', filter=Q(positions__properties__supply_points__meter__status__token=token_meter_status_no_meter), distinct=True) + 
                    Count('positions__properties__supply_points__meter__sub_meters', filter=Q(positions__properties__supply_points__meter__sub_meters__status__token=token_meter_status_no_meter), distinct=True)
                    )
            )
            fix_supplies_contracts_data = batch.fix_meters.aggregate(
                num_supplies=Count('supply_points__id', distinct=True),
                num_contracts=Count(
                    'supply_points__contracts__id',
                    filter=Q(
                        supply_points__contracts__status__token=active_contract,
                        supply_points__contracts__is_active=True
                    ),
                    distinct=True
                ),
                num_no_meter=(
                    Count('supply_points__meter', filter=Q(supply_points__meter__status__token=token_meter_status_no_meter), distinct=True) + 
                    Count('supply_points__meter__sub_meters', filter=Q(supply_points__meter__sub_meters__status__token=token_meter_status_no_meter), distinct=True)
                )
            )
            
            
            num_supplies = (supplies_contracts_data['num_supplies'] or 0) + (fix_supplies_contracts_data['num_supplies'] or 0)
            num_contracts = (supplies_contracts_data['num_contracts'] or 0) + (fix_supplies_contracts_data['num_contracts'] or 0)
            num_no_meter = (supplies_contracts_data['num_no_meter'] or 0) + (fix_supplies_contracts_data['num_no_meter'] or 0)
            print("num_no_meter:", num_no_meter)
            missing_billing_data = {}
            if batch.billing_missing:
                from billing.serializers.billing_serializer import BillingListSerializer
                billing_missing = BillingListSerializer(batch.billing_missing).data
                missing_billing_data = {
                    "missing_billing": billing_missing,
                    "missing_start": batch.missing_start,
                    "missing_end": batch.missing_end,
                }
            
            allow_force_manual = False
            if batch.include_telecontrol and not batch.include_manual:
                existing_manual_batch = ReadingBatch.objects.filter(
                    include_manual=True,
                    include_telecontrol=False,
                    status__token=pending_token
                )
                if existing_manual_batch.exists():
                    allow_force_manual = True
            
            
            return Response({
                "counters": counters, 
                "counters_pending": counters_pending, 
                "status": ReadingBatchStatusSerializer(batch.status).data, 
                "id": batch.id,
                "name": batch.name,
                "token": batch.token,
                "num_supplies": num_supplies, 
                "num_contracts": num_contracts, 
                "num_no_meter": num_no_meter,
                "no_route_supply_points_count": no_route_supply_points_count,
                "task_id": batch.task_id,
                "assign_readings_task_id": batch.assign_readings_task_id,
                "estimating_task_id": batch.estimating_task_id,
                "missing_billing_data": missing_billing_data,
                "allow_force_manual": allow_force_manual,
                "last_task_status": batch.last_task_status,
                "last_task_errors": batch.last_task_errors,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=True, methods=['post'], url_path='assign-readings')
    def assign_readings(self, request, pk=None):
        reading_batch = ReadingBatch.objects.get(id=pk)
        existing_task_id = reading_batch.assign_readings_task_id
        if existing_task_id:
            task_result = AsyncResult(existing_task_id)
            if task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
                return Response({
                    "task_id": existing_task_id,
                    "detail": "Assign readings task already in progress."
                }, status=status.HTTP_409_CONFLICT)
        
        payload = {
            "reading_files": request.data.get('reading_files') or [],
            "reading_date": request.data.get('reading_date'),
            "not_billed": request.data.get('not_billed'),
            "minimum_date": request.data.get('minimum_date'),
        }
        
        task = assign_readings_task.delay(reading_batch.id, payload)
        reading_batch.assign_readings_task_id = task.id
        reading_batch.save(update_fields=['assign_readings_task_id'])
        
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
        
        
    @action(detail=True, methods=['put'], url_path='update-force-manual')
    def update_force_manual_readings(self, request, pk=None):
        reading_batch = ReadingBatch.objects.get(id=pk)
        active_contract = ConfigProject.objects.get(token='contract_active_token').value
        
        sp_query = SupplyPoint.objects.filter(
            property__route_position__route__reading_batches=reading_batch
        )
        if not reading_batch.include_telecontrol:
            sp_query = sp_query.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True))
        elif not reading_batch.include_manual:
            sp_query = sp_query.filter(meter__has_remote_reading=True, meter__force_manual_reading=False)
        
        batch_supply_points = set(sp_query.values_list('id', flat=True))
        readings_supply_points = set(reading_batch.readings.filter(is_control=False).values_list('supply_point_id', flat=True))
        missing_supply_points = batch_supply_points - readings_supply_points

        if missing_supply_points:
            missing_supply_points_objects = SupplyPoint.objects.select_related(
                'type', 'status', 'property__route_position__route'
            ).filter(id__in=missing_supply_points).order_by('id')

            missing_supply_points_objects = missing_supply_points_objects.filter(contracts__status__token=active_contract).distinct()
            meters = Meter.objects.filter(supply_points__in=missing_supply_points_objects).distinct()
            meters.update(force_manual_reading=True)
        
        
        return Response({"success": True}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='smart-metering/preview')
    def smart_metering_preview(self, request, pk=None):
        reading_batch = ReadingBatch.objects.get(id=pk)
        reading_date = request.query_params.get('reading_date')
        if not reading_date:
            return Response({"error": "reading_date is required."}, status=status.HTTP_400_BAD_REQUEST)

        task = preview_smart_metering_task.delay(reading_batch.id, reading_date)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], url_path='smart-metering/assign')
    def smart_metering_assign(self, request, pk=None):
        reading_batch = ReadingBatch.objects.get(id=pk)
        reading_date = request.data.get('reading_date')
        if not reading_date:
            return Response({"error": "reading_date is required."}, status=status.HTTP_400_BAD_REQUEST)

        existing_task_id = reading_batch.assign_readings_task_id
        if existing_task_id:
            task_result = AsyncResult(existing_task_id)
            if task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
                return Response({
                    "task_id": existing_task_id,
                    "detail": "Assign readings task already in progress."
                }, status=status.HTTP_409_CONFLICT)

        task = assign_smart_metering_task.delay(
            reading_batch.id,
            reading_date,
            request.data.get('preview'),
        )
        reading_batch.assign_readings_task_id = task.id
        reading_batch.save(update_fields=['assign_readings_task_id'])

        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path='no-route-supply-points')
    def no_route_supply_points(self, request):
        try:
            batch_id = request.query_params.get('batch_id')
            if not batch_id:
                return Response({"error": "Batch ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            batch = ReadingBatch.objects.get(id=batch_id)
            active_contract = ConfigProject.objects.get(token='contract_active_token').value
            
            supply_active_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
            supply_cut_token = ConfigProject.objects.get(token='supply_point_status_cut_token').value
            
            exploitation_ids = [eid for eid in batch.routes.all().values_list('positions__address_city__exploitations__id', flat=True).distinct() if eid]

            from service.models import SupplyPoint
            from service.serializers.supply_point_serializer import SupplyPointListSerializer

            no_route_supply_points = SupplyPoint.objects.none()
            if exploitation_ids:
                no_route_supply_points = SupplyPoint.objects.filter(
                    is_active=True,
                    status__token__in=[supply_active_token, supply_cut_token],
                    meter__is_active=True,
                    contracts__status__token=active_contract,
                    contracts__is_active=True
                ).filter(
                    Q(property__route_position__isnull=True) | Q(property__isnull=True)
                ).filter(
                    Q(property__address_city__exploitations__id__in=exploitation_ids) |
                    Q(address__city__exploitations__id__in=exploitation_ids)
                ).distinct()

            serializer = SupplyPointListSerializer(no_route_supply_points, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def serialize_decimal(value):
    """Recursively converts Decimal values to float or str."""
    if isinstance(value, Decimal):
        return float(value)  # or str(value) if you want to keep precision as a string
    elif isinstance(value, dict):
        return {key: serialize_decimal(val) for key, val in value.items()}
    elif isinstance(value, list):
        return [serialize_decimal(item) for item in value]
    return value
        

class ReadingBatchRegenerateView(views.APIView):
    """
    Regenerates a reading batch, similar to BillingBatchRegenerateView but for readings.
    - Deletes all readings associated with the given ReadingBatch.
    - Sets the batch status to *processing*.
    - Enqueues the `process_reading_batch` Celery task.
    """
    permission_classes = [IsAuthenticated, ReadingPermission]
    queryset = ReadingBatch.objects.all().order_by('-created_at')

    def post(self, request, id):
        try:
            # Load the batch
            reading_batch = ReadingBatch.objects.get(id=id)

            # Delete existing readings for this batch
            Reading.objects.filter(batch=reading_batch).delete()

            # Set status to processing
            processing_token = ConfigProject.objects.get(token='reading_batch_processing_token').value
            processing_status = ReadingBatchStatus.objects.get(token=processing_token)

            # Trigger regeneration task
            task = process_reading_batch.delay(reading_batch.id)

            # Update batch with task and status
            reading_batch.task_id = task.id
            reading_batch.status = processing_status
            reading_batch.save()

            return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReadingBatchRevertView(views.APIView):
    """
    Revert protegit d'un ReadingBatch ja finalitzat ('finish' -> 'processing').

    A diferencia de ReadingBatchRegenerateView (que esborra TOTES les Reading
    del lot sense mirar cap factura ni preservar el que no ha canviat), aquesta
    vista NO esborra cap Reading:
    - Bloqueja el revert si alguna Reading del lot te una factura definitiva
      (Invoice.type_final='F') vinculada -> cal gestionar-les manualment abans.
    - Desvincula (invoice.readings.remove) les Reading amb factura esborrany
      (type_final='P'), ja que el seu valor pot canviar en el reprocessament
      i la factura esborrany quedaria desactualitzada.
    - Reseteja processed_at/is_processed i torna a encolar process_reading_batch,
      que ara recalcula cada Reading in-place (get_reading_minimal_object):
      nomes escriu els camps que realment canvien (update_fields) i, si el
      valor calculat d'una lectura estimada canvia, ajusta EstimatedBag i el
      seu EstimatedBagMovement pel diferencial en lloc de recrear-los.
    """
    permission_classes = [IsAuthenticated, ReadingPermission]
    queryset = ReadingBatch.objects.all().order_by('-created_at')

    def post(self, request, id):
        try:
            reading_batch = ReadingBatch.objects.get(id=id)
        except ReadingBatch.DoesNotExist:
            return Response({"error": "Reading batch not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            final_invoiced_readings = Reading.objects.filter(
                batch=reading_batch,
                invoices__type_final='F',
            ).distinct()

            if final_invoiced_readings.exists():
                return Response(
                    {
                        "error": (
                            "No es pot revertir el lot: hi ha lectures amb factura "
                            "definitiva vinculada. Cal gestionar-les manualment abans."
                        ),
                        "blocked_reading_ids": list(final_invoiced_readings.values_list('id', flat=True)),
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            draft_invoiced_readings = Reading.objects.filter(
                batch=reading_batch,
                invoices__type_final='P',
            ).distinct()

            unlinked_draft_invoice_ids = set()
            for reading in draft_invoiced_readings:
                for invoice in reading.invoices.filter(type_final='P'):
                    invoice.readings.remove(reading)
                    unlinked_draft_invoice_ids.add(invoice.id)

            reverted_reading_ids = list(
                Reading.objects.filter(batch=reading_batch)
                .filter(PENDING_READING_FILTER)
                .distinct()
                .values_list('id', flat=True)
            )

            processing_token = ConfigProject.objects.get(token='reading_batch_processing_token').value
            processing_status = ReadingBatchStatus.objects.get(token=processing_token)

            task = process_reading_batch.delay(reading_batch.id)

            reading_batch.task_id = task.id
            reading_batch.status = processing_status
            reading_batch.processed_at = None
            reading_batch.is_processed = False
            reading_batch.save(update_fields=['task_id', 'status', 'processed_at', 'is_processed'])

            return Response(
                {
                    "task_id": task.id,
                    "reverted_reading_ids": reverted_reading_ids,
                    "unlinked_draft_invoice_ids": list(unlinked_draft_invoice_ids),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class TaskProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task_result = AsyncResult(task_id)
        if task_result.state == 'FAILURE':
            response = {'state': task_result.state, 'error': str(task_result.info)}
        elif task_result.state == 'SUCCESS':
            result = task_result.result
            # Dict payloads (e.g. smart metering preview) are not sized like lists.
            if isinstance(result, dict):
                current = total = 1
            elif result is not None and hasattr(result, '__len__'):
                current = total = len(result)
            else:
                current = total = 1 if result is not None else 0
            response = {
                'state': task_result.state,
                'percent': 100,
                'current': current,
                'total': total,
                'result': result,
            }
        else:
            response = {
                'state': task_result.state,
                'percent': serialize_decimal(task_result.info.get('percent', 0) if task_result.info else 0),
                'current': serialize_decimal(task_result.info.get('current', 0) if task_result.info else 0),
                'total': serialize_decimal(task_result.info.get('total', 0) if task_result.info else 0),
            }
        
        return Response(response)

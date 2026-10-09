from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
import datetime
from celery.result import AsyncResult
from billing.models import Reading, ReadingBatch
from billing.serializers.reading_serializer import ReadingMinimalSerializer
from billing.utils.reading_service import (
    classify_reading_processing_error,
    get_estimated_reading_minimal_object,
    get_estimated_reading,
    READING_ESTIMATE_PERIOD_CHOICES,
    READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
    READING_ESTIMATE_STATISTIC_CHOICES,
    READING_ESTIMATE_STATISTIC_MEAN,
    PERIOD_MONTHS_MAP
)
from coredata.models import ConfigProject
from contract.models import ContractStatus
from service.models import SupplyPoint
from billing.permissions import ReadingPermission
from billing.tasks import estimate_readings_task
class ReadingBatchEstimateViewSet(viewsets.ViewSet):

    permission_classes = [IsAuthenticated, ReadingPermission]
    lookup_field = 'id'
    queryset = ReadingBatch.objects.all().order_by('-created_at')
    def estimate_readings(self, request, id=None):
        try:
            reading_batch = ReadingBatch.objects.select_related('status').prefetch_related(
                'routes__positions__properties__supply_points'
            ).get(id=id)
            active_contract = ConfigProject.objects.get(token='contract_active_token').value
            active_contract_id = ContractStatus.objects.get(token=active_contract).id


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

            supply_points_param = request.data.get('supply_points')
            if supply_points_param == 'all':
                existing_task_id = reading_batch.estimating_task_id
                if existing_task_id:
                    task_result = AsyncResult(existing_task_id)
                    if task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
                        return Response(
                            {
                                "task_id": existing_task_id,
                                "detail": "Estimate readings task already in progress."
                            },
                            status=status.HTTP_409_CONFLICT
                        )

                payload = {
                    "extra_filter": request.data.get('extra_filter'),
                    "reading_date": request.data.get('reading_date'),
                    "estimation_type": request.data.get('estimation_type'),
                    "days_from_last": request.data.get('days_from_last'),
                    "period": period,
                    "statistic": statistic,
                }
                task = estimate_readings_task.delay(reading_batch.id, payload)
                reading_batch.estimating_task_id = task.id
                reading_batch.save(update_fields=['estimating_task_id'])

                return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
            else:
                supply_points = SupplyPoint.objects.filter(id__in=request.data.get('supply_points'))
            print(len(supply_points), 'supply_points')
            reading_date = request.data.get('reading_date', None)
            """ 
            try:
                date = reading_batch.readings.order_by('-reading_date').first().reading_date
            except:
                date = None """
            date = None
            avg_batch_date = None
            if not date:
                # Get average reading_date from all readings in the batch
                reading_dates = reading_batch.readings.exclude(reading_date__isnull=True).values_list('reading_date', flat=True)
                if reading_dates:
                    total_days = sum((d - datetime.date(1970, 1, 1)).days for d in reading_dates)
                    avg_days = total_days // len(reading_dates)
                    avg_batch_date = datetime.date(1970, 1, 1) + datetime.timedelta(days=avg_days)
                    date = avg_batch_date
                elif reading_date:
                    date = reading_date
                else:
                    date = datetime.datetime.now().date()
            
            if isinstance(date, str):
                try:
                    date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
                except ValueError:
                    date = datetime.datetime.now().date()
                        
            readings = []
            today = datetime.datetime.now().date()
            estimation_type = request.data.get('estimation_type')
            days_from_last = request.data.get('days_from_last')

            reading_date_param = request.data.get('reading_date', None)
            if reading_date_param and isinstance(reading_date_param, str):
                try:
                    reading_date_param = datetime.datetime.strptime(reading_date_param, '%Y-%m-%d').date()
                except ValueError:
                    reading_date_param = None

            errors = []
            for supply_point in supply_points:
                try:
                    offset_days = 90
                    biller = supply_point.property.route_position.route.biller if supply_point.property.route_position.route and supply_point.property.route_position and supply_point.property else None
                    if biller:
                        try:
                            offset_days = PERIOD_MONTHS_MAP[biller.period_type]
                        except:
                            offset_days = 90

                    for contract in supply_point.contracts.filter(status_id=active_contract_id):
                        try:
                            target_date = date

                            if avg_batch_date and abs((contract.created_at.date() - avg_batch_date).days) < 30:
                                target_date = reading_date_param if reading_date_param else today
                            elif estimation_type == 'days_from_last' and days_from_last:
                                last_real_reading = Reading.objects.filter(
                                    supply_point=supply_point,
                                    contract=contract,
                                    reading_value__isnull=False
                                ).order_by('-reading_date').first()

                                if last_real_reading:
                                    target_date = last_real_reading.reading_date + datetime.timedelta(days=int(days_from_last))
                                else:
                                    # Fallback if no real reading found
                                    target_date = date

                            if period or statistic:
                                # Comportament configurable: només s'activa si el front ha triat
                                # explícitament periode/estadístic. Sense aquests parametres es
                                # manté el comportament original (get_estimated_reading_minimal_object).
                                reading = get_estimated_reading(
                                    supply_point, contract, target_date, batch=reading_batch,
                                    period=period or READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
                                    statistic=statistic or READING_ESTIMATE_STATISTIC_MEAN,
                                    max_day_limit=today,
                                )
                            else:
                                reading = get_estimated_reading_minimal_object(supply_point, contract, target_date, reading_batch, max_day_limit = today, offset_days = offset_days)
                            if reading:
                                readings.append(reading)
                        except Exception as e:
                            classification = classify_reading_processing_error(e)
                            errors.append({
                                'supply_point_id': supply_point.id,
                                'contract_id': contract.id,
                                'error': str(e),
                                'type': type(e).__name__,
                                **classification,
                            })
                            continue
                except Exception as e:
                    classification = classify_reading_processing_error(e)
                    errors.append({
                        'supply_point_id': supply_point.id,
                        'error': str(e),
                        'type': type(e).__name__,
                        **classification,
                    })
                    continue

            return Response({
                'readings': ReadingMinimalSerializer(readings, many=True).data,
                'status': 'partial' if errors else 'ok',
                'errors': errors,
            })

        except ReadingBatch.DoesNotExist:
            return Response(
                {"error": "el lot de lectura no existeix"},
                status=status.HTTP_404_NOT_FOUND
            )

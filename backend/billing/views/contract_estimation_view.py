from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Max, Q, Exists, OuterRef
from django.utils import timezone
from datetime import timedelta
import logging

from billing.models import Reading, ReadingBatch, Invoice
from contract.models import Contract, ContractTerminationRequest
from billing.utils.reading_service import (
    get_estimated_reading_minimal_object,
    get_estimated_reading,
    READING_ESTIMATE_PERIOD_CHOICES,
    READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
    READING_ESTIMATE_STATISTIC_CHOICES,
    READING_ESTIMATE_STATISTIC_MEAN,
)
from coredata.utils.name_utils import generate_token
from coredata.models import ConfigProject

logger = logging.getLogger(__name__)

class ContractEstimationView(APIView):
    """
    Vista per gestionar l'estimació de lectures de contractes des del frontend.
    """

    def get(self, request, *args, **kwargs):
        """
        Retorna llistes de contractes dividides entre els que necessiten estimació 
        i els que tenen lectura recent.
        """
        batch_template_id = request.query_params.get('batch_template_id')
        last_invoice_date_start = request.query_params.get('last_invoice_date_start')
        last_invoice_date_end = request.query_params.get('last_invoice_date_end')
        
        # Obtenim els tokens de configuració per als estats a ometre
        terminated_token = ConfigProject.objects.filter(token='contract_terminated_status').values_list('value', flat=True).first()
        cancelled_token = ConfigProject.objects.filter(token='contract_termination_cancelled_token').values_list('value', flat=True).first()
        completed_token = ConfigProject.objects.filter(token='contract_termination_completed_token').values_list('value', flat=True).first()

        queryset = Contract.objects.filter(is_active=True)

        # Ometem els contractes que tenen l'estat de "Donat de baixa"
        if terminated_token:
            queryset = queryset.exclude(status__token=terminated_token)

        # Ometem els contractes que tenen una sol·licitud de baixa activa (no cancel·lada ni finalitzada)
        exclude_termination_tokens = [t for t in [cancelled_token, completed_token] if t]
        
        active_termination_exists = Exists(
            ContractTerminationRequest.objects.filter(contract=OuterRef('pk')).exclude(
                status__token__in=exclude_termination_tokens
            )
        )
        queryset = queryset.annotate(has_active_termination=active_termination_exists).filter(has_active_termination=False)
        
        batch_template_ids = request.query_params.getlist('batch_template_id')
        if not batch_template_ids:
            # Fallback per si es passen separats per coma en un sol paràmetre
            batch_template_id_str = request.query_params.get('batch_template_id')
            if batch_template_id_str:
                batch_template_ids = batch_template_id_str.split(',')

        if batch_template_ids:
            queryset = queryset.filter(
                supply_points__property__route_position__route__reading_batch_template__id__in=batch_template_ids
            ).distinct()
            
        # Annotate with last invoice date and last reading date for initial filtering
        queryset = queryset.annotate(
            last_invoice_issue_date=Max('invoices__issue_date'),
            last_reading_date=Max('reading__reading_date')
        ).select_related('holder', 'use_type', 'client_type')
        
        if last_invoice_date_start:
            queryset = queryset.filter(last_invoice_issue_date__gte=last_invoice_date_start)
        if last_invoice_date_end:
            queryset = queryset.filter(last_invoice_issue_date__lte=last_invoice_date_end)
            
        # Ordenem per data de factura per defecte (més antigues primer)
        queryset = queryset.order_by('last_invoice_issue_date')
            
        needs_estimation = []
        has_recent_reading = []

        for contract in queryset:
            # Busquem les dues últimes lectures actives
            last_readings = Reading.objects.filter(
                contract=contract, 
                is_active=True,
                is_control=False
            ).order_by('-reading_date', '-id')[:2]

            r1 = last_readings[0] if len(last_readings) > 0 else None
            r2 = last_readings[1] if len(last_readings) > 1 else None

            # Un contracte té lectura recent si l'última lectura és igual o posterior a l'última factura
            # PERÒ si la lectura és del mateix dia i és estimada, la considerem pendent d'estimació real
            is_recent = False
            if r1 and contract.last_invoice_issue_date:
                if r1.reading_date > contract.last_invoice_issue_date:
                    is_recent = True
                elif r1.reading_date == contract.last_invoice_issue_date:
                    if not r1.is_estimated:
                        is_recent = True

            contract_data = {
                'id': contract.id,
                'token': contract.token,
                'holder_name': f"{contract.holder.name} {contract.holder.surname}" if contract.holder else "Sense titular",
                'use_type_name': contract.use_type.name if contract.use_type else "-",
                'use_type_id': contract.use_type.id if contract.use_type else None,
                'use_type_token': contract.use_type.token if contract.use_type else None,
                'client_type_name': contract.client_type.name if contract.client_type else "-",
                'last_invoice_date': contract.last_invoice_issue_date,
                'last_reading': {
                    'date': r1.reading_date if r1 else None,
                    'value': r1.reading_value if r1 else None,
                    'consumption': r1.calculated_value if r1 else None,
                },
                'penultimate_reading': {
                    'date': r2.reading_date if r2 else None,
                    'value': r2.reading_value if r2 else None,
                    'consumption': r2.calculated_value if r2 else None,
                }
            }

            if is_recent:
                has_recent_reading.append(contract_data)
            else:
                needs_estimation.append(contract_data)
            

        default_days = 90
        try:
            config_days = ConfigProject.objects.get(token='reading_estimation_default_days').value
            default_days = int(config_days)
        except (ConfigProject.DoesNotExist, ValueError):
            pass

        return Response({
            'needs_estimation': needs_estimation,
            'has_recent_reading': has_recent_reading,
            'settings': {
                'default_days': default_days,
                'period_choices': list(READING_ESTIMATE_PERIOD_CHOICES),
                'default_period': READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
                'statistic_choices': list(READING_ESTIMATE_STATISTIC_CHOICES),
                'default_statistic': READING_ESTIMATE_STATISTIC_MEAN,
            }
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """
        Crea lectures estimades per a una llista de contractes.
        Body: {
            "has_recent_reading_ids": [1, 2],
            "needs_estimation_ids": [3, 4],
            "contract_ids": [1, 2, 3, 4], # Retrocompatible
            "days": 60,
            "dry_run": false,
            "period": "same_period_previous_year", # opcional: last_reading | last_year | same_period_previous_year | historic
            "statistic": "mean" # opcional: mean | median
        }
        """
        has_recent_ids = request.data.get('has_recent_reading_ids', [])
        needs_estimation_ids = request.data.get('needs_estimation_ids', [])

        # Combinem totes les IDs si ve en el nou format, o usem contract_ids si és l'antic
        contract_ids = list(set(has_recent_ids + needs_estimation_ids))
        if not contract_ids:
            contract_ids = request.data.get('contract_ids', [])

        days_str = request.data.get('days')
        batch_id = request.data.get('batch_id')
        dry_run = request.data.get('dry_run', False)

        observation = request.data.get('observation')

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

        if not days_str:
            return Response({'error': 'Falta el paràmetre "days"'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            days = int(days_str)
        except ValueError:
            return Response({'error': 'El paràmetre "days" ha de ser un número'}, status=status.HTTP_400_BAD_REQUEST)

        if not contract_ids:
            return Response({'error': 'No s\'han enviat IDs de contractes'}, status=status.HTTP_400_BAD_REQUEST)

        batch = None
        if batch_id:
            batch = ReadingBatch.objects.filter(id=batch_id).first()

        summary = {
            'processed': 0,
            'created': 0,
            'skipped': 0,
            'errors': 0,
            'created_reading_ids': [],
            'details': []
        }

        for c_id in contract_ids:
            try:
                # Sempre usem transacció per contracte per aïllar
                with transaction.atomic():
                    self._process_contract(c_id, days, batch, dry_run, summary, observation=observation, period=period, statistic=statistic)
                    if dry_run:
                        transaction.set_rollback(True)

            except Exception as e:
                summary['errors'] += 1
                logger.error(f"Error estimating for contract {c_id}: {str(e)}", exc_info=True)
                summary['details'].append({'id': c_id, 'status': 'error', 'msg': str(e)})

        return Response(summary, status=status.HTTP_200_OK)

    def _process_contract(self, c_id, days, batch, dry_run, summary, observation=None, r1_prefetch=None, r2_prefetch=None, period=None, statistic=None):
        contract = Contract.objects.filter(id=int(c_id), is_active=True).first() if str(c_id).isdigit() else Contract.objects.filter(token=c_id, is_active=True).first()

        if not contract:
            summary['errors'] += 1
            summary['details'].append({'id': c_id, 'status': 'error', 'msg': 'Contracte no trobat'})
            return

        # Busquem les dues últimes lectures
        last_readings = Reading.objects.filter(
            contract=contract,
            is_active=True,
            is_control=False,
            reading_value__isnull=False
        ).order_by('-reading_date', '-id')[:2]

        r1 = last_readings[0] if len(last_readings) > 0 else None
        r2 = last_readings[1] if len(last_readings) > 1 else None

        supply_points = contract.supply_points.all()
        if not supply_points:
            summary['skipped'] += 1
            summary['details'].append({
                'id': c_id, 
                'token': contract.token,
                'holder_name': contract.holder.name if contract.holder else '',
                'status': 'skipped', 
                'msg': 'Sense supply points'
            })
            return

        last_invoice = Invoice.objects.filter(contract=contract, is_active=True).order_by('-issue_date').first()
        last_invoice_date = last_invoice.issue_date if last_invoice else None

        contract_results = []
        is_intermediate = False
        
        # Logica de lectura intermitja: si r1 > factura i (r1 - r2) > 110 dies
        is_recent = False
        if r1 and last_invoice_date:
            if r1.reading_date > last_invoice_date:
                is_recent = True
            elif r1.reading_date == last_invoice_date:
                if not r1.is_estimated:
                    is_recent = True

        if is_recent:
            if r1 and r2:
                diff = (r1.reading_date - r2.reading_date).days
                if diff > 110:
                    is_intermediate = True
                else:
                    # Si té lectura recent i el salt és petit, no cal fer res
                    summary['skipped'] += 1
                    summary['details'].append({
                        'id': c_id, 
                        'token': contract.token,
                        'holder_name': contract.holder.name if contract.holder else '',
                        'status': 'skipped', 
                        'msg': 'reading_block.skip_small_gap'
                    })
                    return
            else:
                # Té lectura recent però no té penúltima o similar
                summary['skipped'] += 1
                summary['details'].append({
                    'id': c_id, 
                    'token': contract.token,
                    'holder_name': contract.holder.name if contract.holder else '',
                    'status': 'skipped', 
                    'msg': 'reading_block.has_recent_no_history'
                })
                return

        today = timezone.now().date()
        
        # LÒGICA D'INCENDIS: Busquem el tipus d'ús d'incendis per forçar consum 0
        from coredata.utils.fire_usage_utils import get_fire_usage_tokens
        fire_usage_tokens = get_fire_usage_tokens()

        is_fire_hydrant = contract.use_type and contract.use_type.token in fire_usage_tokens

        for sp in supply_points:
            target_date = None
            
            if is_intermediate:
                # Use penultimate reading as base
                target_date = r2.reading_date + timedelta(days=days)
                # Ensure we don't exceed r1 date
                if target_date >= r1.reading_date:
                    target_date = r2.reading_date + timedelta(days=diff // 2)
            else:
                # Use last reading as base
                start_date = r1.reading_date if r1 else (contract.created_at.date() if contract.created_at else None)
                if not start_date:
                    contract_results.append({'sp_id': sp.id, 'status': 'skipped', 'msg': 'No start date found'})
                    continue
                target_date = start_date + timedelta(days=days)

            # LIMIT: NEVER create a reading in the future
            if target_date > today:
                contract_results.append({'sp_id': sp.id, 'status': 'skipped', 'msg': 'reading_block.future_estimation'})
                summary['skipped'] += 1
                continue

            base_r = r2 if is_intermediate else r1
            base_val = float(base_r.reading_value) if base_r else 0

            if base_r and target_date <= base_r.reading_date:
                contract_results.append({'sp_id': sp.id, 'status': 'skipped', 'msg': 'La data d\'estimació no pot ser anterior o igual a l\'última lectura'})
                summary['skipped'] += 1
                continue

            if period or statistic:
                # Nova via configurable: es fa servir només si el frontend ha triat
                # explícitament un periode/estadístic. Sense aquests paràmetres es manté
                # el comportament original (get_estimated_reading_minimal_object).
                reading = get_estimated_reading(
                    supply_point=sp,
                    contract=contract,
                    date=target_date,
                    batch=batch,
                    offset_days=days,
                    period=period or READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
                    statistic=statistic or READING_ESTIMATE_STATISTIC_MEAN,
                    max_day_limit=today,
                )
            else:
                reading = get_estimated_reading_minimal_object(
                    supply_point=sp,
                    contract=contract,
                    date=target_date,
                    batch=batch,
                    offset_days=days,
                    force_zero_consumption=is_fire_hydrant
                )

            if reading:
                # Si hi ha observació, l'assignem
                if observation and not dry_run:
                    reading.observation = observation
                    reading.save()

                consumption = float(reading.calculated_value) if reading.calculated_value else 0
                base_consumption = float(base_r.calculated_value) if base_r and base_r.calculated_value else 0
                
                if not dry_run:
                    if not reading.token:
                        reading.token = generate_token(Reading, "-id", f"ESTIM_+{days}")
                    # Manté el mateix valor de lectura (índex) que la base
                    reading.reading_value = base_val
                    reading.save()
                
                res_data = {
                    'sp_id': sp.id, 
                    'status': 'dry-run' if dry_run else 'created', 
                    'val': base_val, # KEEP SAME INDEX
                    'date': target_date.strftime('%Y-%m-%d'),
                    'consumption': consumption, # CONSUMPTION (m3)
                    'is_intermediate': is_intermediate,
                    'base_date': base_r.reading_date.strftime('%Y-%m-%d') if base_r else None,
                    'base_val': base_val,
                    'base_consumption': base_consumption
                }
                if not dry_run:
                    res_data['reading_id'] = reading.id
                    summary['created_reading_ids'].append(reading.id)
                    
                contract_results.append(res_data)
                summary['created'] += 1
            else:
                contract_results.append({'sp_id': sp.id, 'status': 'skipped', 'msg': 'No hi ha prou dades per estimar'})
                summary['skipped'] += 1

        summary['details'].append({
            'id': contract.id, 
            'token': contract.token,
            'holder_name': contract.holder.name if contract.holder else '',
            'results': contract_results
        })
        summary['processed'] += 1

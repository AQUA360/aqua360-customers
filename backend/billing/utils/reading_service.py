

from datetime import timedelta
import datetime
import threading
from time import timezone
import uuid
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from django.core.files.base import ContentFile
from django.http import HttpResponse
import openpyxl
from rest_framework.response import Response
from django.core.files.storage import default_storage
from rest_framework import status
from django.utils.translation import gettext as _

from billing.models import EstimatedBag, EstimatedBagMovement, Reading, ReadingAlert, ReadingBatch
from django.db.models import F, Value, IntegerField, ExpressionWrapper, fields, Q
from django.db import models
from django.db.models.functions import Abs
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from coredata.utils.fire_usage_utils import get_fire_usage_tokens
from service.models import Meter, SupplyPointStatus, SupplyPoint
from statistics.models import ContractConsumption
from statistics.views.reports_views import add_row, adjust_column_widths
from order.models import Order, OrderPriority, OrderReason, OrderStatus, OrderType
from logger.models import LogReadingChange

# Config Project Alerts

# reading_alert_negative
# reading_alert_zero
# reading_alert_meter_cycle

def classify_reading_processing_error(exc, reading=None):
  """
  Tradueix una excepcio capturada durant el processament/assignacio/estimacio
  de lectures a una forma estructurada que el frontend pot fer servir per
  oferir una correccio directa (camp concret + missatge entenedor), en lloc
  de nomes mostrar el missatge cru de Python.
  """
  if reading is not None and getattr(reading, 'reading_date', 'SET') is None:
    return {
      'code': 'missing_reading_date',
      'message': _('La lectura no té una data de lectura assignada.'),
      'fixable': True,
      'fix_field': 'reading_date',
    }

  if isinstance(exc, ValueError) and 'None as a query value' in str(exc):
    return {
      'code': 'missing_required_field',
      'message': _('Falta un valor obligatori a la lectura per poder-la processar.'),
      'fixable': False,
      'fix_field': None,
    }

  return {
    'code': 'unknown',
    'message': str(exc),
    'fixable': False,
    'fix_field': None,
  }


def get_reading_alerts_config():
  """
  Config d'alertes de lectura necessaria per get_reading_minimal_object,
  aillada de qualsevol tasca concreta perque es pugui recalcular una lectura
  individual (p.ex. en corregir-la des del serializer) sense dependre de tot
  el context de process_reading_batch.
  """
  reading_alert_estimated_token = ConfigProject.objects.get(token='reading_alert_estimated').value
  reading_alert_estimated = ReadingAlert.objects.get(token=reading_alert_estimated_token)

  reading_alert_negative_token = ConfigProject.objects.get(token='reading_alert_negative').value
  reading_alert_negative = ReadingAlert.objects.get(token=reading_alert_negative_token)

  reading_alert_zero_token = ConfigProject.objects.get(token='reading_alert_zero').value
  reading_alert_zero = ReadingAlert.objects.get(token=reading_alert_zero_token)

  reading_alert_meter_cycle_token = ConfigProject.objects.get(token='reading_alert_meter_cycle').value
  reading_alert_meter_cycle = ReadingAlert.objects.get(token=reading_alert_meter_cycle_token)

  reading_alert_unusual_consumption_token = ConfigProject.objects.get(token='reading_alert_unusual_consumption').value
  reading_alert_unusual_consumption = ReadingAlert.objects.get(token=reading_alert_unusual_consumption_token)

  reading_alert_low_consumption_config = ConfigProject.objects.filter(token='reading_alert_low_consumption').first()
  reading_alert_low_consumption = ReadingAlert.objects.filter(token=reading_alert_low_consumption_config.value).first() if reading_alert_low_consumption_config and reading_alert_low_consumption_config.value else None

  min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()

  return {
    'negative': reading_alert_negative,
    'zero': reading_alert_zero,
    'meter_cycle': reading_alert_meter_cycle,
    'unusual_consumption': reading_alert_unusual_consumption,
    'estimated': reading_alert_estimated,
    'low_consumption': reading_alert_low_consumption,
    'min_consumption': min_consumption,
  }


def get_reading_minimal_object(reading, type, reading_alert_negative, reading_alert_zero, reading_alert_meter_cycle, reading_alert_unusual_consumption, reading_alert_estimated, batch, min_consumption = None, reading_alert_low_consumption = None):
  
  db_previousreading = Reading.objects.filter(supply_point=reading.supply_point, reading_date__lt=reading.reading_date, contract=reading.contract,is_control=False, meter=reading.meter).order_by('-reading_date', '-created_at').first()
  
  if not db_previousreading:
    db_previousreading = Reading.objects.filter(supply_point=reading.supply_point, reading_date__lt=reading.reading_date, is_control=False, meter=reading.meter).order_by('-reading_date').first()
  
  previous_reading = db_previousreading if db_previousreading else (reading.previous_reading if reading.previous_reading else None)
  
  calc_value = 0
  consumption_days = (reading.reading_date - previous_reading.reading_date).days if previous_reading else 0
  warning = False

  alert = None

  if not previous_reading and reading.contract:
    consumption_days = (reading.reading_date - reading.contract.created_at.date()).days


  if reading.is_estimated:
    calc_value = reading.calculated_value
    warning = reading.is_estimated
    alert = reading_alert_estimated

  if previous_reading:
    prev_value = previous_reading.reading_value
    curr_value = reading.reading_value
    has_prev_value = prev_value is not None
    has_curr_value = curr_value is not None

    if has_prev_value and has_curr_value and curr_value > prev_value:
      calc_value = curr_value - prev_value if not previous_reading.is_close else 0
      
    elif has_prev_value and has_curr_value and curr_value < prev_value and reading.meter == previous_reading.meter:
      warning = True
      calc_value = check_overflow_value(reading, previous_reading) if not previous_reading.is_close else 0
      alert = reading_alert_meter_cycle
    else:
      calc_value = curr_value - prev_value if has_prev_value and has_curr_value else 0
  else:
    calc_value = reading.reading_value
      
  if reading.meter and reading.meter.is_general and reading.meter.sub_meters.count() > 0:
    calc_value = recalc_calc_value_gen_meter(reading, calc_value, reading.supply_point)    

  if calc_value == 0 and not reading.is_estimated:
    warning = True
    alert = reading_alert_zero
    
  if calc_value < 0:
    warning = True
    alert = reading_alert_negative
  elif calc_value > 0 and warning == False:
    
    num_months = consumption_days / 30
    
    # Convert to Decimal to match the type returned by get_average_consumption
    monthly_consumption = Decimal(str(min_consumption.value)) if min_consumption and min_consumption.value else Decimal('6')
    num_months_decimal = Decimal(str(num_months))
    
    if calc_value > (monthly_consumption * num_months_decimal):
      warning = check_unusual_consumption(reading, calc_value)
      if warning:
        alert = reading_alert_unusual_consumption
        
    if not warning and reading_alert_low_consumption:
      warning = check_low_consumption(reading, calc_value)
      if warning:
        alert = reading_alert_low_consumption
  
  
  data = {
    'id':reading.id,
    'token': reading.token,
    'contract': reading.contract.token if reading.contract else None,
    'type': type,
    'read1': previous_reading.reading_value if previous_reading else None,
    'read2': reading.reading_value,
    'calculated_value': calc_value,
    'alert': alert.name if alert else None,
    'warning': warning
  }
  
  
  old_calculated_value = reading.calculated_value
  old_previous_reading_id = reading.previous_reading_id
  old_batch_id = reading.batch_id
  old_alert_id = reading.alert_id
  old_consumption_days = reading.consumption_days

  new_calculated_value = calc_value if not reading.is_estimated else reading.calculated_value
  new_previous_reading = previous_reading if previous_reading else None
  new_real_consumption = (reading.real_consumption if reading.is_estimated and reading.real_consumption else calc_value) - (reading.estimated_used if reading.estimated_used and reading.estimated_used > 0 else 0)

  update_fields = []

  if old_consumption_days != consumption_days:
    reading.consumption_days = consumption_days
    update_fields.append('consumption_days')

  if old_previous_reading_id != (new_previous_reading.id if new_previous_reading else None):
    reading.previous_reading = new_previous_reading
    update_fields.append('previous_reading')

  if old_batch_id != (batch.id if batch else None):
    reading.batch = batch
    update_fields.append('batch')

  if old_alert_id != (alert.id if alert else None):
    reading.alert = alert
    update_fields.append('alert')

  value_changed = old_calculated_value != new_calculated_value
  if value_changed:
    reading.calculated_value = new_calculated_value
    reading.real_consumption = new_real_consumption
    update_fields.extend(['calculated_value', 'real_consumption'])
  elif reading.real_consumption != new_real_consumption:
    reading.real_consumption = new_real_consumption
    update_fields.append('real_consumption')

  if update_fields:
    reading.save(update_fields=update_fields)

  # Si la lectura es estimada i el seu valor calculat ha canviat, cal reflectir
  # la diferencia a la bossa d'estimades (no substituir total_consumption, sumar
  # el diff), i actualitzar el moviment associat en lloc de crear-ne un nou.
  if value_changed and reading.is_estimated and reading.supply_point and reading.contract:
    diff = Decimal(str(new_calculated_value or 0)) - Decimal(str(old_calculated_value or 0))
    bag = EstimatedBag.objects.filter(supply_point=reading.supply_point, contract=reading.contract).first()
    if bag:
      bag.total_consumption = Decimal(str(bag.total_consumption or 0)) + diff
      bag.save(update_fields=['total_consumption'])

      movement = EstimatedBagMovement.objects.filter(reading=reading).first()
      if movement:
        movement.amount = new_calculated_value
        movement.save(update_fields=['amount'])

  return data

def get_existing_reading(reading):
  
  calc_value = 0
  warning = False
  alert = None
  calc_value = reading.calculated_value
  previous_reading =reading.previous_reading
  if reading.alert:
    alert = reading.alert
    warning = True
  
  communication_process_status_finalized_token = ConfigProject.objects.get(token='communication_process_status_finalized_token').value
  communication_status_sent_token = ConfigProject.objects.get(token='communication_status_sent_token').value
  
  data = {
    'id':reading.id,
    'token': reading.token,
    'reading_date': reading.reading_date,
    'contract': reading.contract.token if reading.contract else None,
    'type': reading.origin,
    'read1': previous_reading.reading_value if previous_reading else None,
    'read2': reading.reading_value,
    'calculated_value': reading.real_consumption if reading.real_consumption else calc_value,
    'alert': alert.name if alert else None,
    'warning': warning,
    'previous_leak': previous_reading.leak_value if previous_reading else None,
    'leak_value': reading.leak_value if reading.leak_value else None,
    'in_communication_process': reading.communication_processes.exists() and reading.communication_processes.exclude(status__token=communication_process_status_finalized_token).exists() and not reading.communications.filter(status__token=communication_status_sent_token).exists()
  }
  
  return data

def get_estimated_reading_minimal_object(
    supply_point, contract, date, batch, 
    offset_days: int = 90, max_day_limit = None, force_zero_consumption = False, create_reading = True
):
  
  if offset_days <= 0:
    raise ValueError("offset_days ha de ser > 0")

  # Check if this contract is within 30 days of the average batch date
  is_new_contract_exception = False
  avg_batch_date = None
  if batch:
    reading_dates = batch.readings.exclude(reading_date__isnull=True).values_list('reading_date', flat=True)
    if reading_dates:
      total_days = sum((d - datetime.date(1970, 1, 1)).days for d in reading_dates)
      avg_days = total_days // len(reading_dates)
      avg_batch_date = datetime.date(1970, 1, 1) + datetime.timedelta(days=avg_days)
      
  if avg_batch_date and abs((contract.created_at.date() - avg_batch_date).days) < 30:
    is_new_contract_exception = True

  # LÒGICA D'INCENDIS: Comprovar si el contracte o el punt de subministrament (connexió) és contra incendis per forçar consum a 0.
  fire_usage_tokens = get_fire_usage_tokens()

  try:
    fire_connection_use_type_token = ConfigProject.objects.get(token='fire_connection_use_type_token').value
  except ConfigProject.DoesNotExist:
    fire_connection_use_type_token = 'incendis'

  is_fire_contract = contract and contract.use_type and contract.use_type.token in fire_usage_tokens
  is_fire_connection = supply_point and supply_point.connection and supply_point.connection.use_type and supply_point.connection.use_type.token == fire_connection_use_type_token

  if is_fire_contract or is_fire_connection:
    force_zero_consumption = True

  no_meter_status = ConfigProject.objects.get(token='token_meter_status_no_meter').value
  is_gauge = supply_point.meter and supply_point.meter.status and supply_point.meter.status.token == no_meter_status

  last_reading = Reading.objects.filter(supply_point=supply_point, is_control=False, contract=contract, reading_value__isnull=False).order_by('-reading_date').first()
  existing_reading = Reading.objects.filter(supply_point=supply_point, is_control=False, contract=contract).order_by('-reading_date').first()
  
  if not last_reading and not existing_reading:
    if supply_point.meter:
        last_reading = Reading.objects.filter(meter=supply_point.meter, is_control=False, reading_value__isnull=False).order_by('-reading_date').first()
        existing_reading = Reading.objects.filter(meter=supply_point.meter, is_control=False).order_by('-reading_date').first()
  
  read1 = 0
  if last_reading and hasattr(last_reading, 'reading_value') and last_reading.reading_value is not None:
      read1 = last_reading.reading_value
      
  # 1. Busquem la mitjana diària estadística (multi-anual i estacional)
  # Fem servir la data sol·licitada original per determinar l'estacionalitat
  if is_new_contract_exception:
      min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()
      monthly_val = Decimal(str(min_consumption.value)) if min_consumption and min_consumption.value else Decimal('6')
      daily_avg = monthly_val / Decimal('30.44')
  else:
      daily_avg = get_statistical_daily_avg(contract, date.month, target_year=date.year, offset_days=offset_days)
      
      if daily_avg is None:
          min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()
          monthly_val = Decimal(str(min_consumption.value)) if min_consumption and min_consumption.value else Decimal('6')
          daily_avg = monthly_val / Decimal('30.44')
  
  if daily_avg < 0:
      daily_avg = Decimal('0')

  # 2. LÒGICA D'AJUST DE DATA I SEGURETAT (Normalització de períodes)
  final_date = date
  consumption_days = offset_days
  
  # Determinem si hem de crear una lectura nova o actualitzar una existent
  is_new = True
  if existing_reading and last_reading and existing_reading.id != last_reading.id:
      is_new = False

  try:
    limit = int(ConfigProject.objects.get(token='reading_estimate_limit_percentage').value)
  except ConfigProject.DoesNotExist:
    limit = 33
  
  contract_readings = Reading.objects.filter(contract=contract, reading_date__gte=contract.created_at, is_control=False, is_initial=False)
  
  if last_reading and last_reading.contract and last_reading.contract == contract:
    # Intentem normalitzar la data al període nominal (ex: 90 dies des de l'anterior)
    target_nominal_date = last_reading.reading_date + timedelta(days=offset_days)
    
    # Si la diferència entre la data demanada i la nominal és massa gran, ens quedem amb la demanada
    if abs((target_nominal_date - date).days) > (offset_days * (limit / 100)):
      final_date = date
    else:
      final_date = target_nominal_date
    
    # No podem sobrepassar el límit màxim permès (p.ex. 'avui')
    if max_day_limit and final_date > max_day_limit:
      final_date = max_day_limit
    
    consumption_days = (final_date - last_reading.reading_date).days
    
  elif last_reading and last_reading.contract != contract:
    consumption_days = (final_date - last_reading.reading_date).days
  else:
    consumption_days = offset_days

  # Vigilem que la data no sigui anterior a la creació del contracte
  if final_date < contract.created_at.date():
    final_date = contract.created_at.date()
    if last_reading and last_reading.contract == contract:
      consumption_days = (final_date - last_reading.reading_date).days
  
  # Validació de dies mínims per seguretat
  if not is_new_contract_exception and (consumption_days / offset_days) * 100 < limit and contract_readings.count() > 0:
    return None

  # 3. CÀLCUL FINAL DEL VOLUM basat en la DATA FINAL decidida
  average_to_add = daily_avg * Decimal(str(consumption_days))
  calc_val = int(average_to_add.quantize(Decimal('1'), rounding=ROUND_HALF_UP)) if not force_zero_consumption else 0

  # Els aforaments no tenen comptador acumulador: reutilitzem el consum de l'última lectura (0 si no n'hi ha)
  if is_gauge:
    calc_val = int(last_reading.calculated_value) if last_reading and last_reading.calculated_value is not None else 0
  
  if not create_reading:
    
    return {
      'reading_date': final_date,
      'reading_value': read1,
      'calculated_value': calc_val,
      'consumption_days': consumption_days,
      'is_estimated': not is_gauge,
      'is_active': True,
      'batch': batch,
      'origin': _('Estimada') if not is_gauge else supply_point.meter.status.name
    }
    
  if is_new:
      reading = Reading.objects.create(
          supply_point=supply_point,
          reading_date=final_date,
          reading_value=read1,
          meter=supply_point.meter,
          contract=contract,
          calculated_value=calc_val,
          is_estimated=not is_gauge,
          consumption_days=consumption_days,
          is_active=True,
          batch=batch,
          previous_reading=last_reading,
          origin=_('Estimada') if not is_gauge else supply_point.meter.status.name
      )
  else:
      reading = existing_reading
      reading.reading_date = final_date
      reading.reading_value = read1
      reading.calculated_value = calc_val
      reading.consumption_days = consumption_days
      reading.is_estimated = not is_gauge
      reading.batch = batch
      reading.previous_reading = last_reading
      reading.origin = _('Estimada') if not is_gauge else supply_point.meter.status.name
      reading.save()

  # 4. PROCESSAMENT DE COMPTADOR GENERAL I SAFATA D'ESTIMATS
  if reading.is_estimated:
    try:
      estimated_consumption = recalc_calc_value_gen_meter(reading, reading.calculated_value, supply_point)
      
      try:
        estimated_bag = EstimatedBag.objects.get(supply_point=supply_point, contract=contract)
        estimated_bag.total_consumption += int(estimated_consumption)
        estimated_bag.save()
        
        EstimatedBagMovement.objects.create(
          token=uuid.uuid4(),
          estimated_bag=estimated_bag,
          movement_date=reading.reading_date,
          reading=reading,
          amount=int(estimated_consumption),
          is_positive=True
        )
      except EstimatedBag.DoesNotExist:
        pass
    except Exception as e:
      print(f'Error in estimated_bag processing: {e}')
    
  return reading

def recalc_calc_value_gen_meter(reading, calculated_value, supply_point_instance):
  
  meter = supply_point_instance.meter
  if not meter or not meter.is_general:
    return calculated_value
  
  print(f'recalc_calc_value_gen_meter: processing meter={meter.id}, is_general={meter.is_general}')
  general_meter = meter
  total_meter_general = 1
    
  try:
      active_status_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
      active_status = SupplyPointStatus.objects.get(token=active_status_token)
  except (ConfigProject.DoesNotExist, SupplyPointStatus.DoesNotExist) as e:
      print(f'Error: Could not find active status configuration: {e}')
      return calculated_value

  child_meters = meter.sub_meters.all()
  child_supply_points = SupplyPoint.objects.filter(meter__in=child_meters, status=active_status)
  supply_points = child_supply_points
  
  print(f'recalc_calc_value_gen_meter: meter={meter.id} has {child_meters.count()} child_meters, {child_supply_points.count()} child supply_points')
  
  # Prevent infinite loops by limiting iterations
  supply_points_list = list(supply_points[:1000])  # Limit to 1000 to prevent excessive processing
  if len(supply_points_list) >= 1000:
    print(f'WARNING: recalc_calc_value_gen_meter: meter={meter.id} has {supply_points.count()} supply_points, limiting to 1000')
  
  consumption_sub_meters = 0.0
  
  # Bulk fetch all readings in one query (including general child meters)
  sp_meter_pairs = [(sp.id, sp.meter.id) for sp in supply_points_list if sp.meter]
  
  sub_meter_readings_dict = {}
  revised_readings_dict = {}
  if reading.batch and reading.batch.token and sp_meter_pairs:
      supply_point_ids = [pair[0] for pair in sp_meter_pairs]
      meter_ids = [pair[1] for pair in sp_meter_pairs]

      sub_meter_readings = Reading.objects.filter(
          batch__token=reading.batch.token,
          supply_point_id__in=supply_point_ids,
          meter_id__in=meter_ids,
          is_control=False,
          is_initial=False,
      ).only('calculated_value', 'supply_point_id', 'meter_id', 'is_revised').values(
          'supply_point_id', 'meter_id', 'calculated_value', 'is_revised'
      )

      for reading_data in sub_meter_readings:
          key = (reading_data['supply_point_id'], reading_data['meter_id'])
          sub_meter_readings_dict[key] = float(reading_data['calculated_value'] or 0)
          revised_readings_dict[key] = reading_data['is_revised']

  def _get_sub_meter_consumption(parent_meter, batch_token, act_status, visited=None):
      """Recursively sum calculated_value of sub-meter readings for a revised parent meter."""
      if visited is None:
          visited = set()
      if parent_meter.id in visited:
          return 0
      visited.add(parent_meter.id)

      total = 0.0
      child_meters = parent_meter.sub_meters.all()
      if not child_meters.exists():
          return 0

      child_sps = SupplyPoint.objects.filter(
          meter__in=child_meters, status=act_status
      ).select_related('meter')

      for sp in child_sps:
          if not sp.meter:
              continue
          child_reading = Reading.objects.filter(
              batch__token=batch_token,
              supply_point=sp,
              meter=sp.meter,
              is_control=False,
              is_initial=False,
          ).only('calculated_value', 'is_revised').first()
          if child_reading:
              total += float(child_reading.calculated_value or 0)
              # Only recurse deeper if NOT revised (raw value needs sub-meter expansion)
              if not child_reading.is_revised:
                  total += _get_sub_meter_consumption(sp.meter, batch_token, act_status, visited)
      return total

  for idx, supply_point in enumerate(supply_points_list):
      if idx % 100 == 0:
          print(f'recalc_calc_value_gen_meter: processing supply_point {idx}/{len(supply_points_list)} for meter={meter.id}')
      if supply_point.meter:
          key = (supply_point.id, supply_point.meter.id)
          if key in sub_meter_readings_dict:
              consumption_sub_meters += sub_meter_readings_dict[key]
              # If the reading is NOT revised, its calculated_value is raw and we need
              # to add its sub-meters' consumption so the parent can subtract the full tree.
              # If it IS revised, calculated_value already has sub-meters subtracted — don't double-count.
              if not revised_readings_dict.get(key, False) and reading.batch and reading.batch.token:
                  consumption_sub_meters += _get_sub_meter_consumption(
                      supply_point.meter, reading.batch.token, active_status
                  )
  
  print(f'recalc_calc_value_gen_meter: meter={meter.id} - total_meter_general={total_meter_general}, consumption_sub_meters={consumption_sub_meters}')
  
  if not general_meter:
      print(f'recalc_calc_value_gen_meter: no general_meter found, calling recalc_calc_value_meter_multiple_contracts')
      return recalc_calc_value_meter_multiple_contracts(reading, calculated_value, supply_point_instance)
    
    
  if consumption_sub_meters > 0:
      calculated_value = float(calculated_value) - float(consumption_sub_meters) if float(calculated_value) - float(consumption_sub_meters) > 0 else 0
      reading.is_revised = True
      print(f'recalc_calc_value_gen_meter: using consumption_sub_meters={consumption_sub_meters}')

  print(f'recalc_calc_value_gen_meter: returning calculated_value={calculated_value}')
  return calculated_value

def get_reading_document_target_contract(supply_point, active_contract_status_token=None):
  """
  Single active contract for importing a reading document row.

  Prefer the contract that has this supply point as supply_point_default;
  otherwise the first active contract linked via M2M. Terminated/inactive
  contracts are never selected.
  """
  if active_contract_status_token is None:
    try:
      active_contract_status_token = ConfigProject.objects.get(token='contract_active_token').value
    except ConfigProject.DoesNotExist:
      return None

  active_qs = Contract.objects.filter(
    status__token=active_contract_status_token,
    is_active=True,
  )
  preferred = (
    active_qs.filter(supply_point_default=supply_point)
    .order_by('-id')
    .first()
  )
  if preferred:
    return preferred
  return (
    supply_point.contracts.filter(
      status__token=active_contract_status_token,
      is_active=True,
    )
    .order_by('-id')
    .first()
  )


def _get_billable_contract_for_supply_point(supply_point, contract_active_token):
  """
  Active billable contract for a supply point (block_billing=False).
  Prefers supply_point_default; falls back to M2M.
  """
  preferred = get_reading_document_target_contract(supply_point, contract_active_token)
  if preferred and not preferred.block_billing:
    return preferred
  return (
    supply_point.contracts.filter(
      status__token=contract_active_token,
      is_active=True,
      block_billing=False,
    )
    .order_by('-id')
    .first()
  )


def _get_general_meter_fanout_targets(meter, active_sp_status, contract_active_token):
  """
  Active supply points on a general meter paired with one active billable contract each.
  Prefers supply_point_default; falls back to M2M. Skips block_billing=True.
  """
  supply_points = (
    SupplyPoint.objects.filter(meter=meter, status=active_sp_status)
    .select_related('meter')
    .distinct()
  )
  targets = []
  seen_contracts = set()
  for supply_point in supply_points:
    contract = _get_billable_contract_for_supply_point(supply_point, contract_active_token)
    if not contract or contract.id in seen_contracts:
      continue
    seen_contracts.add(contract.id)
    targets.append((supply_point, contract))
  return targets


def count_general_meter_billable_targets(meter, active_sp_status=None, contract_active_token=None):
  """
  Number of (supply_point, billable contract) pairs that share a general meter.
  Used as divisor when splitting consumption without sub-meters.
  """
  if not meter:
    return 0
  if active_sp_status is None:
    try:
      active_sp_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
      active_sp_status = SupplyPointStatus.objects.get(token=active_sp_token)
    except (ConfigProject.DoesNotExist, SupplyPointStatus.DoesNotExist):
      return 0
  if contract_active_token is None:
    try:
      contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
    except ConfigProject.DoesNotExist:
      return 0
  return len(_get_general_meter_fanout_targets(meter, active_sp_status, contract_active_token))


def _build_general_meter_copy_token(canonical, contract, index):
  meter_code = canonical.meter.code if canonical.meter and canonical.meter.code else canonical.meter_id
  base = canonical.token or f"{meter_code}/{canonical.id}"
  contract_token = contract.token if contract and contract.token else contract.id
  return f"{base}/{contract_token}/{index}"


def fanout_general_meter_readings(billing, readings=None):
  """
  Expand canonical general-meter readings (no sub-meters) into one Reading per
  active supply point / contract, linked via copied_from.

  Keeps calculated_value as the full meter consumption; invoice generation
  divides via recalc_consumption_general_meter_no_submeters.

  Idempotent: skips targets that already have a billing reading for that meter+contract.
  Returns the list of created copy readings.
  """
  if billing is None:
    return []

  try:
    active_sp_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
    active_sp_status = SupplyPointStatus.objects.get(token=active_sp_token)
  except (ConfigProject.DoesNotExist, SupplyPointStatus.DoesNotExist):
    return []

  try:
    contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
  except ConfigProject.DoesNotExist:
    return []

  # Do not fan out chain anchors (previous_reading of another reading on this billing)
  previous_ids = set(
    billing.readings.filter(previous_reading__isnull=False)
    .values_list('previous_reading_id', flat=True)
  )

  if readings is None:
    canonical_qs = billing.readings.filter(
      meter__is_general=True,
      copied_from__isnull=True,
      is_control=False,
      is_active=True,
      is_close=False,
      is_initial=False,
    ).select_related('meter', 'batch', 'previous_reading')
  else:
    canonical_ids = [r.id for r in readings if r is not None]
    canonical_qs = Reading.objects.filter(
      id__in=canonical_ids,
      meter__is_general=True,
      copied_from__isnull=True,
      is_control=False,
      is_active=True,
      is_close=False,
      is_initial=False,
    ).select_related('meter', 'batch', 'previous_reading')

  created = []
  for canonical in canonical_qs:
    if canonical.id in previous_ids:
      continue
    meter = canonical.meter
    if not meter or meter.sub_meters.exists():
      continue

    # Ensure canonical is attached to this billing
    if canonical.billing_id != billing.id:
      canonical.billing = billing
      canonical.save(update_fields=['billing'])

    targets = _get_general_meter_fanout_targets(meter, active_sp_status, contract_active_token)
    if not targets:
      continue

    for index, (supply_point, contract) in enumerate(targets):
      existing = (
        Reading.objects.filter(
          billing=billing,
          meter=meter,
          contract=contract,
          is_control=False,
          is_active=True,
          is_close=False,
          is_initial=False,
        )
        .filter(Q(copied_from=canonical) | Q(id=canonical.id) | Q(reading_date=canonical.reading_date))
        .first()
      )
      if existing:
        updates = []
        if existing.supply_point_id is None and supply_point:
          existing.supply_point = supply_point
          updates.append('supply_point')
        if existing.billing_id != billing.id:
          existing.billing = billing
          updates.append('billing')
        if existing.batch_id is None and canonical.batch_id:
          existing.batch = canonical.batch
          updates.append('batch')
        if updates:
          existing.save(update_fields=updates)
        continue

      # Canonical already matches this contract: bind supply_point and reuse it
      if canonical.contract_id == contract.id:
        updates = []
        if canonical.supply_point_id != supply_point.id:
          canonical.supply_point = supply_point
          updates.append('supply_point')
        if updates:
          canonical.save(update_fields=updates)
        continue

      if canonical.contract_id is None and len(targets) == 1:
        # Single target: attach contract/SP to the canonical reading instead of copying
        canonical.contract = contract
        canonical.supply_point = supply_point
        canonical.save(update_fields=['contract', 'supply_point'])
        continue
      
      can_enter_readings = check_billing_period(
        reading_date=canonical.reading_date,
        supply_point=supply_point,
        meter=meter,
        contract=contract,
        previous_reading=canonical.previous_reading,
        is_termination=False,
      )
      if not can_enter_readings:
        continue

      copy = Reading.objects.create(
        token=_build_general_meter_copy_token(canonical, contract, index),
        batch=canonical.batch,
        billing=billing,
        contract=contract,
        supply_point=supply_point,
        meter=meter,
        reading_date=canonical.reading_date,
        reading_value=canonical.reading_value,
        calculated_value=canonical.calculated_value,
        leak_value=canonical.leak_value,
        estimated_used=canonical.estimated_used,
        consumption_days=canonical.consumption_days,
        real_consumption=canonical.real_consumption,
        origin=canonical.origin,
        previous_reading=canonical.previous_reading,
        is_control=False,
        is_estimated=canonical.is_estimated,
        is_close=False,
        is_initial=False,
        is_active=True,
        copied_from=canonical,
        is_revised=canonical.is_revised,
        document=canonical.document,
        reader_alert=canonical.reader_alert,
        operator=canonical.operator,
        alert=canonical.alert,
        remote_alert=canonical.remote_alert,
        alert_notes=canonical.alert_notes,
      )
      created.append(copy)

  return created


def find_canonical_general_meter_reading(meter, reading_date=None, batch=None, start_date=None, end_date=None):
  """
  Find the physical (non-copy) reading for a general meter, typically with no contract.
  Used when assigning readings to a batch before billing fan-out.
  """
  if not meter or not meter.is_general:
    return None
  qs = Reading.objects.filter(
    meter=meter,
    copied_from__isnull=True,
    is_control=False,
    is_active=True,
    is_close=False,
    is_initial=False,
  ).filter(
      Q(previous_reading__is_close=False) |
      Q(previous_reading__isnull=True)
    )
  if batch is not None:
    qs = qs.filter(Q(batch=batch) | Q(batch__isnull=True))
  if reading_date is not None:
    qs = qs.filter(reading_date=reading_date)
  elif start_date is not None and end_date is not None:
    qs = qs.filter(reading_date__range=(start_date, end_date))
  # Prefer contract-less canonical readings
  qs = qs.order_by('contract_id', '-reading_date', '-id')
  return qs.first()


def recalc_calc_value_meter_multiple_contracts(reading, calculated_value, supply_point_instance):
  meter_instance = supply_point_instance.meter
    
  if not meter_instance:
      return calculated_value 
  
  try:
      contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
  except ConfigProject.DoesNotExist:
      print(f'Warning: contract_active_token not found in ConfigProject, returning original calculated_value')
      return calculated_value
  
  total_contracts = supply_point_instance.contracts.filter(status__token=contract_active_token).count()
  
  # Prevent division by zero
  if total_contracts == 0:
      print(f'Warning: No active contracts found for supply_point {supply_point_instance.id}, returning original calculated_value')
      return calculated_value
  
  calculated_value = float(calculated_value) / float(total_contracts)
  
  return calculated_value


def check_overflow_value(reading, previous_reading):
  if len(str(int(previous_reading.reading_value))) == reading.meter.digits and len(str(int(reading.reading_value))) <= 3:
    max_number = 10**reading.meter.digits
    calc_value = (max_number - previous_reading.reading_value) + reading.reading_value
  else:
    calc_value = reading.reading_value - previous_reading.reading_value if previous_reading and previous_reading.reading_value else 0
  return calc_value

def check_unusual_consumption(reading, calc_value):
  
  # Get minimum consumption for warning from ConfigProject
  try:
      min_val_config = ConfigProject.objects.get(token='reading_alert_unusual_consumption_min_value')
      min_val = Decimal(str(min_val_config.value))
  except Exception:
      min_val = Decimal('20')

  if calc_value is not None and Decimal(str(calc_value)) < min_val:
      return False

  # The difference between the previous reading's consumption and the current one must be at least min_val
  if reading.previous_reading:
      prev_consumption = reading.previous_reading.real_consumption if reading.previous_reading.real_consumption is not None else reading.previous_reading.calculated_value
      if prev_consumption is not None:
          if abs(Decimal(str(calc_value)) - Decimal(str(prev_consumption))) < min_val:
              return False

  if reading.contract:
      previous_readings = Reading.objects.filter(
          contract=reading.contract,
          reading_date__lt=reading.reading_date,
          is_control=False
      ).order_by('reading_date')
      if previous_readings.count() == 1:
          first_reading = previous_readings.first()
          if first_reading.reading_value is not None and reading.reading_value is not None:
              if reading.reading_value > first_reading.reading_value:
                  return False
  average_consumption = get_average_consumption(reading.contract, reading.reading_date.month)
  checked_average = False
  
  if average_consumption:
    if average_consumption > calc_value:
      return False
    
    diff = percent_difference(average_consumption, calc_value)
    if diff is not None and diff > 100:
      print(f"Warning: Consumption difference is {diff}% between {average_consumption} and {calc_value}")
      checked_average = True
    else:
      return False
    
  last_calc_values = Reading.objects.filter(
    contract=reading.contract, is_control=False, is_active=True
  ).exclude(id=reading.id).order_by('-reading_date')[:5].values('calculated_value')

  for row in last_calc_values:
    last_val = row.get('calculated_value')
    if last_val is None:
      continue
    diff_last = percent_difference(last_val, calc_value)
    print(f"diff between {last_val} and {calc_value} is {diff_last}")
    if diff_last is not None and diff_last < 50:
      return False
  
  if checked_average:
    return True
  
  previous_year_reading = get_previous_year_reading(reading.reading_date, reading.supply_point)
  
  if previous_year_reading:
    previous_year_calc_value = previous_year_reading.real_consumption if previous_year_reading.real_consumption else previous_year_reading.calculated_value
    if not previous_year_calc_value or previous_year_calc_value is None:
      previous_year_previous_reading = Reading.objects.filter(supply_point=previous_year_reading.supply_point, reading_date__lt=previous_year_reading.reading_date, is_control=False, is_initial=False).order_by('-reading_date').first()
      if previous_year_previous_reading:
        previous_year_calc_value = previous_year_reading.reading_value - previous_year_previous_reading.reading_value
      else:
        # If no previous reading found, can't calculate difference, skip this check
        return False
    diff = percent_difference(previous_year_calc_value, calc_value)
    if diff is not None and diff > 100:
      #print(f"Warning: Consumption difference is {diff}% between {previous_year_reading.reading_date} and {reading.reading_date}")
      return True
  return False

def check_low_consumption(reading, calc_value):
  average_consumption = get_average_consumption(reading.contract, reading.reading_date.month)
  checked_average = False
  
  if average_consumption and average_consumption > float(calc_value):
    diff = percent_difference(average_consumption, calc_value)
    if diff is not None and diff > 50:
      checked_average = True
    else:
      return False
      
  last_calc_values = Reading.objects.filter(
    contract=reading.contract, is_control=False, is_active=True
  ).exclude(id=reading.id).order_by('-reading_date')[:5].values('calculated_value')

  for row in last_calc_values:
    last_val = row.get('calculated_value')
    if last_val is None or last_val == 0:
      continue
    diff_last = percent_difference(last_val, calc_value)
    if diff_last is not None and diff_last < 50:
      return False
      
  if checked_average:
    return True
    
  previous_year_reading = get_previous_year_reading(reading.reading_date, reading.supply_point)
  
  if previous_year_reading:
    previous_year_calc_value = previous_year_reading.real_consumption if previous_year_reading.real_consumption else previous_year_reading.calculated_value
    if not previous_year_calc_value or previous_year_calc_value is None:
      previous_year_previous_reading = Reading.objects.filter(supply_point=previous_year_reading.supply_point, reading_date__lt=previous_year_reading.reading_date, is_control=False, is_initial=False).order_by('-reading_date').first()
      if previous_year_previous_reading:
        previous_year_calc_value = previous_year_reading.reading_value - previous_year_previous_reading.reading_value
      else:
        return False
    if previous_year_calc_value and previous_year_calc_value > float(calc_value):
      diff = percent_difference(previous_year_calc_value, calc_value)
      if diff is not None and diff > 50:
        return True
  return False

def get_statistical_daily_avg(contract, month, target_year, offset_days):
  """
  Calcula la mitjana diària de consum basada en l'històric dels últims 5 anys.
  Per a cada any, busca el mes sol·licitat, i si no el té, busca el mes més proper 
  d'aquell any. Després fa la mitjana d'aquests valors anuals recollits.
  """
  import datetime
  
  if target_year is None:
      target_year = datetime.datetime.now().year
      
  dailies = []
  
  # Prioritat de cerca mensual: mateix mes, -1, +1, -2, +2...
  # Preferim el mes anterior si estan a la mateixa distància
  month_offsets = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6]
  
  # Busquem en els darrers 5 anys incloent l'any actual
  for y in range(target_year - 5, target_year + 1):
      record_found = None
      
      for m_off in month_offsets:
          search_month = ((month + m_off - 1) % 12) + 1
          
          record = ContractConsumption.objects.filter(contract=contract, year=y, period=search_month).first()
          if record:
              record_found = record
              break
              
      if record_found:
          val = None
          if record_found.daily_consumption is not None:
              val = Decimal(str(record_found.daily_consumption))
          elif record_found.consumption is not None:
              if offset_days > 45:
                  val = Decimal(str(record_found.consumption)) / Decimal(str(offset_days))
              else:
                  val = Decimal(str(record_found.consumption)) / Decimal('30.44')
                  
          if val is not None:
              dailies.append(val)
              
  if dailies:
      return sum(dailies) / len(dailies)
      
  # Fallback a registres antics sense any 'legacy' o global
  query = ContractConsumption.objects.filter(contract=contract)
  if target_year:
      query = query.filter(Q(year__lte=target_year) | Q(year__isnull=True))
      
  records = query.all()
  if records:
      global_dailies = []
      for r in records:
          if r.daily_consumption is not None:
              global_dailies.append(Decimal(str(r.daily_consumption)))
          elif r.consumption is not None:
              if not r.year and offset_days > 45:
                  global_dailies.append(Decimal(str(r.consumption)) / Decimal(str(offset_days)))
              else:
                  global_dailies.append(Decimal(str(r.consumption)) / Decimal('30.44'))
      if global_dailies:
          return sum(global_dailies) / len(global_dailies)

  return None

def calculate_month_multiyear_avg(contract, month, target_year, offset_days):
  """
  Calcula la mitjana aritmètica dels registres de ContractConsumption per a un mes concret
  considerant tots els anys anteriors disponibles.
  """
  query = ContractConsumption.objects.filter(contract=contract, period=month)
  if target_year:
      query = query.filter(Q(year__lt=target_year) | Q(year__isnull=True))
  
  records = query.all()
  if not records:
    return None
  
  dailies = []
  for r in records:
    # Acceptem el 0.0 com a dada vàlida (no volem que salti al mínim si el client realment no consumeix)
    if r.daily_consumption is not None:
      dailies.append(Decimal(str(r.daily_consumption)))
    elif r.consumption is not None:
      # Cas Legacy
      if not r.year and offset_days > 45:
        dailies.append(Decimal(str(r.consumption)) / Decimal(str(offset_days)))
      else:
        dailies.append(Decimal(str(r.consumption)) / Decimal('30.44'))
  
  if dailies:
    return sum(dailies) / len(dailies)
  
  return None

def get_average_consumption_object(contract, month, target_year=None):
  # Mantingut per compatibilitat de signatura, però ara és un wrapper de la nova lògica
  # Retorna un "pseudoregistre" o el primer que trobi (ja no s'utilitza per a l'estimació principal)
  return ContractConsumption.objects.filter(contract=contract, period=month).order_by('-year').first()

def get_average_consumption(contract, month):
  from datetime import datetime
  # Fem servir la nova lògica de mitjana multi-anual (assumint mensualitat per defecte en aquest wrapper)
  daily_avg = get_statistical_daily_avg(contract, month, datetime.now().year, 30)
  if daily_avg is not None:
    return daily_avg * Decimal('30.44')
  return None
    
  return average

def get_previous_year_reading(date, supply_point):
  
  start_date = date - timedelta(days=25) - relativedelta(years=1)
  end_date = date + timedelta(days=25) - relativedelta(years=1)
  
  reading = (
    Reading.objects.filter(reading_date__range=(start_date, end_date), supply_point=supply_point)
      .annotate(
        date_difference=ExpressionWrapper(
          F('reading_date') - date,
          output_field=fields.DurationField()
        )
      )
    .order_by('date_difference')
    .first()
  )
  
  return reading

def get_reading_same_period_previous_year(supply_point, contract, target_date, max_months_back=11):
  """
  Cerca una lectura real (supply_point + contract) del mateix mes que target_date
  de l'any anterior. Si no n'hi ha, retrocedeix mes a mes (sempre dins l'any
  anterior) fins a max_months_back mesos.
  Retorna (reading, mesos_retrocedits) o (None, None) si no es troba res.
  """
  for months_back in range(0, max_months_back + 1):
    period_date = target_date - relativedelta(years=1) - relativedelta(months=months_back)
    reading = (
      Reading.objects.filter(
        supply_point=supply_point,
        contract=contract,
        is_control=False,
        is_active=True,
        reading_date__year=period_date.year,
        reading_date__month=period_date.month,
        calculated_value__isnull=False,
      )
      # Preferim una lectura real (is_estimated=False) per sobre d'una d'estimada del mateix mes
      .order_by('is_estimated', '-reading_date')
      .first()
    )
    if reading:
      return reading, months_back

  return None, None

def get_contract_multiyear_daily_avg(contract, target_date, years_back=2):
  """
  Mitjana diària de consum del contracte a partir de totes les seves lectures
  reals dels darrers `years_back` anys. Fallback per a contractes nous que no
  tenen cap lectura en el mateix període de l'any anterior.
  """
  start_date = target_date - relativedelta(years=years_back)
  readings = Reading.objects.filter(
    contract=contract,
    is_control=False,
    is_active=True,
    reading_date__gte=start_date,
    reading_date__lte=target_date,
    calculated_value__isnull=False,
    consumption_days__gt=0,
  )

  total_value = Decimal('0')
  total_days = 0
  for r in readings:
    total_value += Decimal(str(r.calculated_value))
    total_days += r.consumption_days

  if total_days <= 0:
    return None

  return total_value / Decimal(total_days)

READING_ESTIMATE_PERIOD_LAST_READING = 'last_reading'
READING_ESTIMATE_PERIOD_LAST_YEAR = 'last_year'
READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR = 'same_period_previous_year'
READING_ESTIMATE_PERIOD_HISTORIC = 'historic'

READING_ESTIMATE_PERIOD_CHOICES = (
  READING_ESTIMATE_PERIOD_LAST_READING,
  READING_ESTIMATE_PERIOD_LAST_YEAR,
  READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
  READING_ESTIMATE_PERIOD_HISTORIC,
)
PERIOD_MONTHS_MAP = {
      'trimestral': 90,
      'semestral': 180,
      'bimestral': 60,
      'quadrimestral': 120,
      'anual': 360,
      'mensual': 30,
  }
READING_ESTIMATE_STATISTIC_MEAN = 'mean'
READING_ESTIMATE_STATISTIC_MEDIAN = 'median'

READING_ESTIMATE_STATISTIC_CHOICES = (
  READING_ESTIMATE_STATISTIC_MEAN,
  READING_ESTIMATE_STATISTIC_MEDIAN,
)

def collect_last_reading_daily_values(supply_point, contract, date):
  """Consum diari de l'última lectura real anterior a `date`."""
  last_reading = Reading.objects.filter(
    supply_point=supply_point, contract=contract, is_control=False, is_active=True,
    reading_date__lt=date, calculated_value__isnull=False, consumption_days__gt=0,
  ).order_by('-reading_date').first()

  if not last_reading:
    return []

  return [Decimal(str(last_reading.calculated_value)) / Decimal(last_reading.consumption_days)]

def collect_last_year_daily_values(supply_point, contract, date):
  """Consum diari de totes les lectures reals de l'últim any anterior a `date`."""
  start_date = date - relativedelta(years=1)
  readings = Reading.objects.filter(
    supply_point=supply_point, contract=contract, is_control=False, is_active=True,
    reading_date__gte=start_date, reading_date__lt=date,
    calculated_value__isnull=False, consumption_days__gt=0,
  )

  return [Decimal(str(r.calculated_value)) / Decimal(r.consumption_days) for r in readings]

def collect_same_period_previous_year_daily_values(supply_point, contract, date):
  """
  Consum diari de la lectura real del mateix mes de l'any anterior (supply_point +
  contract); si no n'hi ha, retrocedeix mes a mes dins l'any anterior.
  """
  reading, _ = get_reading_same_period_previous_year(supply_point, contract, date)
  if not reading:
    return []

  days = reading.consumption_days if reading.consumption_days else 30
  return [Decimal(str(reading.calculated_value)) / Decimal(days)]

def collect_historic_daily_values(contract, month, target_year, offset_days=90):
  """
  Recopila els valors de consum diari de l'històric de ContractConsumption (fins a
  5 anys enrere), cercant per a cada any el mes sol·licitat (o el més proper).
  Mateixa font de dades que get_statistical_daily_avg, però retorna la llista de
  valors sense agregar, per poder-hi aplicar mitjana o mediana.
  """
  if target_year is None:
    target_year = datetime.datetime.now().year

  dailies = []
  month_offsets = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6]

  for y in range(target_year - 5, target_year + 1):
    record_found = None
    for m_off in month_offsets:
      search_month = ((month + m_off - 1) % 12) + 1
      record = ContractConsumption.objects.filter(contract=contract, year=y, period=search_month).first()
      if record:
        record_found = record
        break

    if record_found:
      val = None
      if record_found.daily_consumption is not None:
        val = Decimal(str(record_found.daily_consumption))
      elif record_found.consumption is not None:
        if offset_days > 45:
          val = Decimal(str(record_found.consumption)) / Decimal(str(offset_days))
        else:
          val = Decimal(str(record_found.consumption)) / Decimal('30.44')

      if val is not None:
        dailies.append(val)

  if dailies:
    return dailies

  # Fallback a registres antics sense any 'legacy' o global
  query = ContractConsumption.objects.filter(contract=contract)
  if target_year:
    query = query.filter(Q(year__lte=target_year) | Q(year__isnull=True))

  global_dailies = []
  for r in query.all():
    if r.daily_consumption is not None:
      global_dailies.append(Decimal(str(r.daily_consumption)))
    elif r.consumption is not None:
      if not r.year and offset_days > 45:
        global_dailies.append(Decimal(str(r.consumption)) / Decimal(str(offset_days)))
      else:
        global_dailies.append(Decimal(str(r.consumption)) / Decimal('30.44'))

  return global_dailies

def aggregate_daily_values(values, statistic=READING_ESTIMATE_STATISTIC_MEAN):
  """
  Agrega una llista de Decimal segons l'estadístic triat (mitjana o mediana).
  No es fa servir el modul estandard `statistics` perque aquest projecte te una
  app Django anomenada igual (`statistics.models`/`statistics.views`), que tapa
  el modul de la libreria estandard un cop importada.
  """
  if not values:
    return None

  if statistic == READING_ESTIMATE_STATISTIC_MEDIAN:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
      return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2

  return sum(values) / len(values)

def get_estimated_reading(
    supply_point, contract, date, batch=None, offset_days=30,
    period=READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
    statistic=READING_ESTIMATE_STATISTIC_MEAN, create_reading=True, max_day_limit=None,
):
  """
  Genera/actualitza una lectura estimada. El consum diari es calcula recopilant
  els valors del `period` triat i agregant-los amb l'`statistic` triat:

  Periodes disponibles (READING_ESTIMATE_PERIOD_*):
    - last_reading: només l'última lectura real.
    - last_year: totes les lectures reals de l'últim any.
    - same_period_previous_year: lectura real del mateix mes de l'any anterior
      (retrocedint mes a mes si cal). Comportament anterior per defecte.
    - historic: mitjana/mediana històrica multi-any per mes (ContractConsumption),
      comportament de get_statistical_daily_avg.

  Si el període triat no retorna cap valor (p.ex. contracte nou sense historial),
  es fa servir com a fallback la mitjana multi-anual (2 anys) de totes les
  lectures del contracte, i en última instància el consum mínim configurat
  (ConfigProject 'minimum_consumption').
  """
  if period not in READING_ESTIMATE_PERIOD_CHOICES:
    raise ValueError(f"Periode desconegut: {period}")
  if statistic not in READING_ESTIMATE_STATISTIC_CHOICES:
    raise ValueError(f"Estadístic desconegut: {statistic}")

  fire_usage_tokens = get_fire_usage_tokens()

  try:
    fire_connection_use_type_token = ConfigProject.objects.get(token='fire_connection_use_type_token').value
  except ConfigProject.DoesNotExist:
    fire_connection_use_type_token = 'incendis'

  is_fire_contract = contract and contract.use_type and contract.use_type.token in fire_usage_tokens
  is_fire_connection = supply_point and supply_point.connection and supply_point.connection.use_type and supply_point.connection.use_type.token == fire_connection_use_type_token
  force_zero_consumption = is_fire_contract or is_fire_connection

  no_meter_status = ConfigProject.objects.get(token='token_meter_status_no_meter').value
  is_gauge = supply_point.meter and supply_point.meter.status and supply_point.meter.status.token == no_meter_status

  last_reading = Reading.objects.filter(
    supply_point=supply_point, contract=contract, is_control=False, reading_value__isnull=False
  ).order_by('-reading_date').first()
  existing_reading = Reading.objects.filter(
    supply_point=supply_point, contract=contract, is_control=False
  ).order_by('-reading_date').first()

  read1 = last_reading.reading_value if last_reading and last_reading.reading_value is not None else 0

  period_collectors = {
    READING_ESTIMATE_PERIOD_LAST_READING: lambda: collect_last_reading_daily_values(supply_point, contract, date),
    READING_ESTIMATE_PERIOD_LAST_YEAR: lambda: collect_last_year_daily_values(supply_point, contract, date),
    READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR: lambda: collect_same_period_previous_year_daily_values(supply_point, contract, date),
    READING_ESTIMATE_PERIOD_HISTORIC: lambda: collect_historic_daily_values(contract, date.month, date.year, offset_days),
  }

  # Etiquetes traduïbles (claus de .po a locale/<lang>/LC_MESSAGES/django.po).
  # Es defineixen dins la funció perquè _() s'avaluï amb l'idioma actiu de la petició.
  period_labels = {
    READING_ESTIMATE_PERIOD_LAST_READING: _('última lectura'),
    READING_ESTIMATE_PERIOD_LAST_YEAR: _('últim any'),
    READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR: _('mateix període any anterior'),
    READING_ESTIMATE_PERIOD_HISTORIC: _('històric multianual'),
  }
  statistic_labels = {
    READING_ESTIMATE_STATISTIC_MEAN: _('mitjana'),
    READING_ESTIMATE_STATISTIC_MEDIAN: _('mediana'),
  }
  period_label = period_labels.get(period, period)
  statistic_label = statistic_labels.get(statistic, statistic)

  values = period_collectors[period]()
  daily_avg = aggregate_daily_values(values, statistic)
  source = f"{period_label} / {statistic_label}" if daily_avg is not None else None

  if daily_avg is None:
    daily_avg = get_contract_multiyear_daily_avg(contract, date)
    if daily_avg is not None:
      source = f"{_('mitjana multianual')} ({_('alternativa a')} {period_label})"

  if daily_avg is None:
    min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()
    monthly_val = Decimal(str(min_consumption.value)) if min_consumption and min_consumption.value else Decimal('6')
    daily_avg = monthly_val / Decimal('30.44')
    source = _('consum mínim')

  if daily_avg < 0:
    daily_avg = Decimal('0')

  final_date = date

  # Mai generar una lectura amb data futura (mateix criteri que get_estimated_reading_minimal_object)
  if max_day_limit and final_date > max_day_limit:
    final_date = max_day_limit

  consumption_days = (final_date - last_reading.reading_date).days if last_reading else offset_days
  if consumption_days <= 0:
    consumption_days = offset_days

  if final_date < contract.created_at.date():
    final_date = contract.created_at.date()

  calc_val = int((daily_avg * Decimal(str(consumption_days))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) if not force_zero_consumption else 0

  if is_gauge:
    calc_val = int(last_reading.calculated_value) if last_reading and last_reading.calculated_value is not None else 0

  is_new = not (existing_reading and last_reading and existing_reading.id != last_reading.id)

  origin_label = f"{_('Estimada')} ({source})" if not is_gauge else supply_point.meter.status.name

  if not create_reading:
    return {
      'reading_date': final_date,
      'reading_value': read1,
      'calculated_value': calc_val,
      'consumption_days': consumption_days,
      'is_estimated': not is_gauge,
      'is_active': True,
      'batch': batch,
      'origin': origin_label,
      'source': source,
    }

  if is_new:
    reading = Reading.objects.create(
      supply_point=supply_point,
      contract=contract,
      meter=supply_point.meter,
      reading_date=final_date,
      reading_value=read1,
      calculated_value=calc_val,
      consumption_days=consumption_days,
      is_estimated=not is_gauge,
      is_active=True,
      batch=batch,
      previous_reading=last_reading,
      origin=origin_label,
    )
  else:
    reading = existing_reading
    reading.reading_date = final_date
    reading.reading_value = read1
    reading.calculated_value = calc_val
    reading.consumption_days = consumption_days
    reading.is_estimated = not is_gauge
    reading.batch = batch
    reading.previous_reading = last_reading
    reading.origin = origin_label
    reading.save()

  return reading

def get_estimated_reading_previous_year(supply_point, contract, date, batch=None, offset_days=30, create_reading=True):
  """
  Wrapper de compatibilitat: equivalent a get_estimated_reading amb
  period=same_period_previous_year i statistic=mean (comportament original).
  """
  return get_estimated_reading(
    supply_point, contract, date, batch=batch, offset_days=offset_days,
    period=READING_ESTIMATE_PERIOD_SAME_PERIOD_PREVIOUS_YEAR,
    statistic=READING_ESTIMATE_STATISTIC_MEAN, create_reading=create_reading,
  )

def percent_difference(num1, num2):
  try:
  ### Previous code for relative difference (40 to 80 -> 66%)
    # difference = abs(num1 - num2)
    # average = (num1 + num2) / 2
    # return (difference / average) * 100 if average != 0 else float('inf')
      
  ## Current code for normal percentage change (40 to 80 -> 100%)
    difference = abs(num1 - num2)
    return (difference / num1) * 100 if num1 != 0 else float('inf')

  except Exception as e:
    print(f"Error: {e}")
    return None


def copy_new_reading_to_all(new_reading, has_future_reading):
  active_contract = ContractStatus.objects.get(token=ConfigProject.objects.get(token='contract_active_token').value)
  reading_contract = new_reading.contract
  contracts = Contract.objects.filter(supply_points__in=[new_reading.supply_point], status=active_contract)
  if reading_contract:
    contracts = contracts.exclude(id=reading_contract.id)
  
  for contract in contracts:
    try:
      if not new_reading.is_control:
        previous_reading = Reading.objects.filter(supply_point=new_reading.supply_point, meter=new_reading.meter, reading_date__lt=new_reading.reading_date, is_control=False).order_by('-reading_date').first()
      else:
        previous_reading = None
    except:
      previous_reading = None
      
    reading_copy = Reading.objects.create(
      token=new_reading.token,
      supply_point=new_reading.supply_point,
      reading_date=new_reading.reading_date,
      reading_value=new_reading.reading_value,
      calculated_value=new_reading.calculated_value,
      real_consumption=new_reading.real_consumption,
      leak_value=new_reading.leak_value,
      consumption_days=new_reading.consumption_days,
      origin=new_reading.origin,
      meter=new_reading.meter,
      contract=contract,
      previous_reading=previous_reading,
      is_control=new_reading.is_control,
      is_estimated=new_reading.is_estimated,
    )
    
    if new_reading.estimated_used and new_reading.estimated_used > 0:
      try:
        estimated_bag = EstimatedBag.objects.get(
          supply_point=reading_copy.supply_point, contract=reading_copy.contract)
      except:
        estimated_bag = None
      
      if estimated_bag:
        calculate_estimated_bag(reading_copy.calculated_value, reading_copy.is_estimated, reading_copy, estimated_bag)
    
    if not new_reading.is_control:
      future_reading = Reading.objects.filter(
        supply_point=new_reading.supply_point, meter=new_reading.meter, 
        reading_date__gt=new_reading.reading_date, is_control=False, is_initial=False).order_by('reading_date').first()
      if future_reading:
        future_reading.previous_reading = reading_copy
        future_reading.save()
        
    if new_reading.is_estimated and not has_future_reading:
      try:
        estimated_bag = EstimatedBag.objects.get(
          supply_point=reading_copy.supply_point, contract=reading_copy.contract)
        estimated_bag.total_consumption += reading_copy.calculated_value
        estimated_bag.save()
        EstimatedBagMovement.objects.create(
            token=uuid.uuid4(),
            estimated_bag=estimated_bag,
            movement_date=reading_copy.reading_date,
            reading=reading_copy,
            amount=reading_copy.calculated_value,
            is_positive=True
        )
      except:
          pass


def recalculate_estimated_readings(reading_ids):
  """
  Recalculates estimated readings by re-running the estimation algorithm.
  Updates calculated_value, reading_value, consumption and the estimated bag movements.
  Returns a list of updated Reading objects.
  """
  PERIOD_MONTHS_MAP = {
    'trimestral': 90,
    'semestral': 180,
    'bimestral': 60,
    'quadrimestral': 120,
    'anual': 360,
    'mensual': 30,
  }

  no_meter_status = ConfigProject.objects.get(token='token_meter_status_no_meter').value

  fire_usage_tokens = get_fire_usage_tokens()

  try:
    fire_connection_use_type_token = ConfigProject.objects.get(token='fire_connection_use_type_token').value
  except ConfigProject.DoesNotExist:
    fire_connection_use_type_token = 'incendis'

  readings = Reading.objects.filter(id__in=reading_ids, is_active=True, is_estimated=True).select_related(
    'supply_point', 'contract', 'meter', 'previous_reading',
    'supply_point__meter', 'supply_point__meter__status',
    'contract__use_type', 'supply_point__connection', 'supply_point__connection__use_type',
    'supply_point__property__route_position__route__biller',
  )

  updated_readings = []

  for reading in readings:
    supply_point = reading.supply_point
    contract = reading.contract

    if not supply_point or not contract:
      continue

    try:
      biller = supply_point.property.route_position.route.biller
      offset_days = PERIOD_MONTHS_MAP.get(biller.period_type, 90) if biller else 90
    except Exception:
      offset_days = 90

    is_fire_contract = contract.use_type and contract.use_type.token in fire_usage_tokens
    is_fire_connection = (supply_point.connection and supply_point.connection.use_type
                          and supply_point.connection.use_type.token == fire_connection_use_type_token)
    force_zero_consumption = is_fire_contract or is_fire_connection

    is_gauge = (supply_point.meter and supply_point.meter.status
                and supply_point.meter.status.token == no_meter_status)

    daily_avg = get_statistical_daily_avg(
      contract, reading.reading_date.month,
      target_year=reading.reading_date.year,
      offset_days=offset_days
    )
    if daily_avg is None:
      min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()
      monthly_val = Decimal(str(min_consumption.value)) if min_consumption and min_consumption.value else Decimal('6')
      daily_avg = monthly_val / Decimal('30.44')
    if daily_avg < 0:
      daily_avg = Decimal('0')

    consumption_days = reading.consumption_days or offset_days

    if is_gauge:
      previous = reading.previous_reading
      new_calc_val = int(previous.calculated_value) if previous and previous.calculated_value is not None else 0
    elif force_zero_consumption:
      new_calc_val = 0
    else:
      average_to_add = daily_avg * Decimal(str(consumption_days))
      new_calc_val = int(average_to_add.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    old_calc_val = int(reading.calculated_value) if reading.calculated_value is not None else 0

    if new_calc_val == old_calc_val:
      updated_readings.append(reading)
      continue

    delta = new_calc_val - old_calc_val
    reading.calculated_value = new_calc_val

    # Update reading_value for estimated readings: it reflects the previous reading's value
    if reading.previous_reading and reading.previous_reading.reading_value is not None:
      reading.reading_value = reading.previous_reading.reading_value

    reading.save()

    # Update estimated bag and its movement
    try:
      estimated_bag = EstimatedBag.objects.get(supply_point=supply_point, contract=contract)
      estimated_bag.total_consumption += delta
      estimated_bag.save()

      movement = EstimatedBagMovement.objects.filter(reading=reading, is_positive=True).first()
      if movement:
        movement.amount = new_calc_val
        movement.save()
      else:
        EstimatedBagMovement.objects.create(
          token=uuid.uuid4(),
          estimated_bag=estimated_bag,
          movement_date=reading.reading_date,
          reading=reading,
          amount=new_calc_val,
          is_positive=True
        )
    except EstimatedBag.DoesNotExist:
      pass

    updated_readings.append(reading)

  return updated_readings


def calculate_estimated_bag(calculated_value, is_estimated, new_reading, estimated_bag):
  cal_value = calculated_value
  if is_estimated:
      try:
          estimated_bag.total_consumption += cal_value
          estimated_bag.save()
          EstimatedBagMovement.objects.create(
              token=uuid.uuid4(),
              estimated_bag=estimated_bag,
              movement_date=new_reading.reading_date,
              reading=new_reading,
              amount=new_reading.calculated_value,
              is_positive=True
          )
      except:
          pass
  else:
      bag_amount = estimated_bag.total_consumption
      try:
          if bag_amount > 0:
              total_used = 0
              if bag_amount > cal_value:
                  total_used = cal_value
              else:
                  total_used = bag_amount
              if total_used > 0:
                  estimated_bag.total_consumption -= total_used
                  estimated_bag.save()
                  EstimatedBagMovement.objects.create(
                      token=uuid.uuid4(),
                      estimated_bag=estimated_bag,
                      movement_date=new_reading.reading_date,
                      reading=new_reading,
                      amount=total_used,
                      is_positive=False
                  )
                  new_reading.estimated_used = total_used
                  new_reading.save()
      except:
          pass

def modify_existing_readings(readings_data, readings_to_update, readings_to_delete=None, user=None):
  
  if readings_to_delete:
    Reading.objects.filter(id__in=readings_to_delete).update(is_active=False, is_control=True, batch=None, billing=None)
    
  # We don't mark all as control at the beginning anymore, we'll do it selectively.
  # readings = Reading.objects.filter(id__in=readings_to_update)
  # readings.update(is_control=True)
  
  # readings to update should not have ids in readings_to_delete
  
  readings_cache = {r.id: r for r in Reading.objects.filter(id__in=readings_to_update)}
  active_contract = ConfigProject.objects.get(token='contract_active_token').value
  
  for data in readings_data:
    print("\ndata", data)
    supply_point_id = data.get('supply_point_id')
    contract_id = data.get('contract_id')
    bag_to_maintain = data.get('bag_to_maintain')
    readings_list = data.get('readings', [])
    supply_point = SupplyPoint.objects.get(id=supply_point_id)
    contract = Contract.objects.get(id=contract_id)
    
    estimated_from_readings = 0
    current_meter_id = supply_point.meter.id if supply_point.meter else None

    for reading_item in sorted(readings_list, key=lambda x: (x['reading_date'], str(x.get('meter_id')) == str(current_meter_id))):
        # print("reading_item", reading_item)
        
        reading_id = reading_item.get('id')
        reading_date = reading_item.get('reading_date')
        reading_value = reading_item.get('reading_value')
        leak_value = reading_item.get('leak_value')
        calculated_value = reading_item.get('calculated_value')
        origin = reading_item.get('origin')
        reading_batch_id = reading_item.get('batch_id')
        previous_reading_date = reading_item.get('previous_reading_option_key')
        meter_id = reading_item.get('meter_id')
        consumption_days = reading_item.get('consumption_days')
        is_control = reading_item.get('is_control', False)
        is_estimated = reading_item.get('is_estimated', False)
        is_initial = reading_item.get('is_initial', False)
        estimated_used = reading_item.get('estimated_used', None)
        block_estimate_correction = reading_item.get('block_estimate_correction', False)
        
        add_to_all = reading_item.get('add_to_all', False)
        print("\n")
        print("reading_id", reading_id)
        print("calculated_value", calculated_value)
        try:
          estimated_bag = EstimatedBag.objects.get(supply_point=supply_point, contract__id=contract_id)
        except:
          estimated_bag = None
        try:
          batch = ReadingBatch.objects.get(id=reading_batch_id)
        except:
          batch = None
        try:
          previous_reading_date_date = datetime.datetime.strptime(previous_reading_date, "%Y-%m-%d").date()
          previous_reading = Reading.objects.filter(
            contract__id=contract_id,
            reading_date=previous_reading_date_date, 
            is_control=False)
          if previous_reading.count() > 1:
            if datetime.datetime.strptime(reading_date, "%Y-%m-%d").date() == previous_reading_date_date:
              previous_reading = previous_reading.exclude(meter__id=meter_id).first()
            else:
              previous_reading = previous_reading.get(meter__id=meter_id)
          else:
            previous_reading = previous_reading.first()
        except:
          print("no previous reading found")
          previous_reading = None

        try:
          meter = Meter.objects.get(id=meter_id)
        except:
          meter = None
        
        new_reading = None
        if reading_id and reading_id in readings_cache:
            reading = readings_cache[reading_id]
            if reading.is_control:
              continue
            # Check for value changes (reading, leak)
            # We use strings for comparison to handle potential decimal/int edge cases from JSON
            val_changed = (
                str(float(reading.reading_value if reading.reading_value != None else -1)) != str(float(reading_value if reading_value else 0)) or
                str(float(reading.leak_value or 0)) != str(float(leak_value or 0)) or 
                str(float(reading.consumption_days or 0)) != str(float(consumption_days or 0)) or 
                str(reading.reading_date) != str(reading_date) or 
                (reading.is_estimated and not is_estimated) or 
                str(float(reading.meter.id)) != str(float(meter_id)) or 
                str(float(reading.calculated_value)) != str(float(calculated_value)) or
                (reading.estimated_used != 0 and block_estimate_correction) or
                (
                  float(reading.estimated_used or 0) != float(estimated_used or 0) and 
                  ((reading.estimated_used != 0 and reading.estimated_used != None) or (float(estimated_used or 0) != 0 and float(estimated_used or 0) != None))
                  )
            )
            
            if val_changed:
                # reading.reading_date = reading_date
                if block_estimate_correction:
                  estimated_used = 0
                if not block_estimate_correction and estimated_used == 0:
                  estimated_used = None
                calculated_int = int(float(calculated_value or 0))
                leak_int = int(float(leak_value or 0))
                if estimated_used and int(float(estimated_used) )> (calculated_int - (leak_int or 0)):
                  estimated_used = calculated_int - (leak_int or 0)
                
                contract_terminations = reading.contract_termination_requests.all()
                
                new_reading = Reading.objects.create(
                    token=f"{supply_point.meter.code}/MOD",
                    batch=batch,
                    contract=reading.contract,
                    supply_point=reading.supply_point,
                    meter=meter,
                    estimated_used=estimated_used,
                    reading_date=reading_date,
                    reading_value=reading_value,
                    leak_value=leak_value if leak_value else 0,
                    calculated_value=calculated_value,
                    consumption_days=consumption_days,
                    real_consumption=calculated_value,
                    origin=origin,
                    is_close=reading.is_close,
                    is_active=True,
                    is_control=False, 
                    previous_reading=previous_reading
                )
                reading.is_control = True
                if reading.original_readings and reading.original_readings.count() > 0:
                  og_reading = reading.original_readings.first()
                else:
                  og_reading = reading
                og_reading.modified_readings.add(new_reading)
                reading.save()
                og_reading.save()
                LogReadingChange.objects.create(
                    contract=reading.contract,
                    meter=meter,
                    user=user,
                    reading_date=reading.reading_date,
                    previous_value=reading.reading_value,
                    current_value=reading_value,
                    observation="Modificació de lectura"
                )
                
                if contract_terminations and contract_terminations.count() > 0:
                  for contract_termination in contract_terminations:
                    if contract_termination.readings.filter(id=reading_id).exists():
                      contract_termination.readings.remove(reading)
                      contract_termination.readings.add(new_reading)
                      contract_termination.save()
                
            else:
              reading.previous_reading = previous_reading
              reading.is_control = is_control
              reading.origin = origin
              reading.batch = batch if not is_control else None
              if reading.is_control:
                reading.batch = None
              reading.save()
                
        else:
            # New reading (no ID or not in update list)
            if add_to_all:
              contracts = Contract.objects.filter(supply_points__meter__id=meter.id, status__token=active_contract)
            else:
              contracts = [contract]
            
            for cr in contracts:
              new_cal_value = calculated_value
              if cr.id == contract.id:
                cr_prev_reading = previous_reading
              else:
                try:
                  cr_prev_reading = Reading.objects.get(
                    contract__id=cr.id,
                    reading_date=previous_reading.reading_date,
                    is_control=False,
                    meter__id=meter_id,
                  )
                except:
                  cr_prev_reading = Reading.objects.filter(
                    contract__id=cr.id,
                    is_control=False,
                    meter__id=meter_id,
                  ).order_by('-reading_date').first()
                  if not cr_prev_reading:
                    continue
                  new_cal_value = reading_value - cr_prev_reading.reading_value
              
              
              created_reading = Reading.objects.create(
                  token=f"{supply_point.meter.code}",
                  batch=batch if not is_control else None,
                  contract=cr,
                  supply_point=cr.supply_points.filter(meter__id=supply_point.meter.id).first(),
                  meter=meter,
                  reading_date=reading_date,
                  reading_value=reading_value,
                  leak_value=leak_value,
                  calculated_value=new_cal_value,
                  consumption_days=consumption_days,
                  real_consumption=calculated_value,
                  origin=origin,
                  is_initial=is_initial,
                  is_estimated=is_estimated,
                  is_active=True,
                  is_control=is_control,
                  previous_reading=cr_prev_reading if not is_control else None,
              )
              LogReadingChange.objects.create(
                  contract=cr,
                  meter=meter,
                  user=user,
                  reading_date=reading_date,
                  previous_value=cr_prev_reading.reading_value if cr_prev_reading else None,
                  current_value=reading_value,
                  observation=f"Creació de lectura (Origen: {origin or 'Manual'})"
              )
              if is_estimated:
                estimated_from_readings += new_cal_value
                if estimated_bag:
                  EstimatedBagMovement.objects.create(
                    token=uuid.uuid4(),
                    estimated_bag=estimated_bag,
                    movement_date=datetime.datetime.now().date(),
                    reading=created_reading,
                    amount=new_cal_value,
                    is_positive=True
                  )
                
              print("created_reading", created_reading)
              if created_reading.contract.id == contract.id:
                new_reading = created_reading
                print("new_reading", new_reading)
        
        if new_reading and new_reading.calculated_value and int(float(new_reading.calculated_value)) < 0:
            original_calc = new_reading.calculated_value
            try:
                alert_token = ConfigProject.objects.get(token='reading_alert_negative').value
                new_reading.alert = ReadingAlert.objects.get(token=alert_token)
                new_reading.alert_notes = new_reading.alert.name
                new_reading.save(update_fields=['alert', 'alert_notes'])
            except:
                pass
    try:
      if estimated_bag:
        if float(estimated_bag.total_consumption) > 0:
          EstimatedBagMovement.objects.create(
            token=uuid.uuid4(),
            estimated_bag=estimated_bag,
            movement_date=datetime.datetime.now().date(),
            reading=None,
            amount=estimated_bag.total_consumption,
            is_positive=False
          )
        estimated_bag.total_consumption = bag_to_maintain
        estimated_bag.save()
        extra_consumption = int(float(bag_to_maintain) - float(estimated_from_readings))
        if extra_consumption != 0:
          EstimatedBagMovement.objects.create(
            token=uuid.uuid4(),
            estimated_bag=estimated_bag,
            movement_date=datetime.datetime.now().date(),
            reading=None,
            amount=abs(extra_consumption),
            is_positive=extra_consumption > 0
          )
    except Exception as e:
      raise e
  return Response({'status': 'ok'}, status=status.HTTP_200_OK)

def check_billing_period(reading_date, supply_point, meter, contract, previous_reading, is_termination=False):
  """ 
  if closest related billing period to this reading, check previous reading and
  if previous reading is in same period by at least 80% of period, 
  example reading 2026-01-01, previous reading 2025-12-01, period 90 days, 
  previous reading is in same period by at least 80% of period, do not allow new reading
  example 2 reading 2026-01-01, previous reading 2025-10-20, period 90 days, 
  previous reading is not in same period by at least 80% of period, allow new reading
  return True -> allow to add reading OR overwrite reading
  """
  
  PERIOD_MONTHS_MAP = {
      'trimestral': 90,
      'semestral': 180,
      'bimestral': 60,
      'quadrimestral': 120,
      'anual': 360,
      'mensual': 30,
  }
  
  if is_termination:
    return True
  
  previous_readings = Reading.objects.filter(
    supply_point=supply_point,
    meter=meter,
    reading_date__lt=reading_date,
    is_control=False,
    is_initial=False,
    contract=contract,
  )
  
  try:
    next_reading = Reading.objects.filter(
      supply_point=supply_point,
      meter=meter,
      reading_date__gt=reading_date,
      is_control=False,
      contract=contract,
    ).order_by('reading_date').first()
  except:
    next_reading = None
  
  if not previous_readings or previous_readings.count() == 0:
    print("no previous readings found")
    return True
  
  # readings_have_period = any(reading.billing.biller for reading in previous_readings if reading.billing)
  # if not readings_have_period:
  #   print("readings do not have period")
  #   return True
  
  biller = supply_point.property.route_position.route.biller
  billing_period_days = PERIOD_MONTHS_MAP[biller.period_type] if biller else 90
  
  reading_date = reading_date
  prev_reading_date = previous_reading.reading_date
  next_reading_date = next_reading.reading_date if next_reading else None
  
  days_difference = (reading_date - prev_reading_date).days
  next_days_difference = (next_reading_date - reading_date).days if next_reading and next_reading_date else None
  # print("days_difference", days_difference)
  
  if (billing_period_days-days_difference)/billing_period_days > 0.2:
    # print("reading is within previous period")
    return False
  
  if next_reading and next_reading_date and ((billing_period_days-next_days_difference)/billing_period_days > 0.2):
    return False
  
  return True
import uuid
from celery import shared_task
from collections import defaultdict
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.utils.translation import override
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _
from billing.models import Reading, Invoice
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from coredata.utils.fire_usage_utils import get_fire_usage_tokens
from notification.models import Notification
from service.models import SupplyPoint
from statistics.utils.daily_document_service import execute_available_report, generate_daily_document
from statistics.utils.billing_amount_average import seasonal_amounts
from .models import ContractConsumption, BillingConsumption, DailyDocument, DailyDocumentStatus, DailyDocumentTemplate


class ReportWarning(Exception):
    pass


def _median(values):
    """
    Compute the median without importing stdlib `statistics` (this project has an app named `statistics`).
    Works with numeric types including Decimal.
    """
    values = sorted([v for v in values if v is not None])
    n = len(values)
    if n == 0:
        return None
    mid = n // 2
    if n % 2 == 1:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2

def _infer_period_from_invoice(invoice):
    raw_date = invoice.issue_date
    if raw_date is None:
        raise ValueError(f"Invoice {invoice.id} has no issue_date")

    # Si és date o datetime
    if isinstance(raw_date, (date, datetime)):
        d = raw_date if isinstance(raw_date, date) else raw_date.date()
        return d.year, d.month

    # Si arriba com a string en algun cas antic
    if isinstance(raw_date, str):
        raw_date = raw_date.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                d = datetime.strptime(raw_date, fmt).date()
                return d.year, d.month
            except ValueError:
                continue

    raise ValueError(f"Unrecognized issue_date format for invoice {invoice.id}: {raw_date}")


@shared_task
def update_billing_consumption(invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)

        # --- Determinar any / mes ---
        year = invoice.billing_period_year
        month = invoice.billing_period_month
        invalid_year = year in (None, 0, "", "0", "0000")
        invalid_month = month in (None, 0, "", "0")

        if invalid_year or invalid_month:
            period_year, period_month = _infer_period_from_invoice(invoice)
            invoice.billing_period_year = period_year
            invoice.billing_period_month = period_month
            invoice._skip_signal = True
            invoice.save(update_fields=['billing_period_year', 'billing_period_month'])
        else:
            period_year = int(year)
            period_month = int(month)

        # --- Daily avg (subtracting leaks if any) ---
        raw_consumption = invoice.consumption or 0
        total_leak = 0
        try:
            leaks = invoice.readings.filter(is_active=True, leak_value__isnull=False).values_list('leak_value', flat=True)
            total_leak = sum(leaks)
        except:
            pass
            
        # LÒGICA D'INCENDIS
        fire_usage_tokens = get_fire_usage_tokens()

        if invoice.contract and invoice.contract.use_type and invoice.contract.use_type.token in fire_usage_tokens:
            consumption = 0
        else:
            consumption = float(raw_consumption) - float(total_leak)
            
        days = invoice.consumption_days or 0
        daily_avg = (consumption / days) if days > 0 else 0

        # --- Mitjana de consum ---
        avg_consumption = 0
        if invoice.contract:
            prev = BillingConsumption.objects.filter(
                contract=invoice.contract, is_active=True
            ).exclude(invoice=invoice).values_list("consumption", flat=True)
            values = [c for c in prev if c is not None]
            values.append(consumption)
            avg_consumption = sum(values) / len(values)

        # --- Imports ---
        net_amount = invoice.subtotal_final or 0
        total_amount = invoice.total_final or 0
        tax_amount = total_amount - net_amount

        # --- Mitjana d’imports ---
        # Del mateix període d'anys anteriors (veure statistics/utils/billing_amount_average.py);
        # si el contracte no en té històric, la de totes les factures com fins ara.
        avg_amount = 0
        if invoice.contract:
            prev_amounts = BillingConsumption.objects.filter(
                contract=invoice.contract, is_active=True
            ).exclude(invoice=invoice)
            rows = list(prev_amounts.values_list('year', 'month', 'total_amount'))
            vals = seasonal_amounts(rows, period_year, period_month)
            if not vals:
                vals = [float(a) for _, _, a in rows if a is not None]
            vals.append(float(total_amount or 0))
            avg_amount = sum(vals) / len(vals)

        # --- Anomaly detection ---
        is_active_stat = True
        if invoice.contract:
            try:
                threshold = float(ConfigProject.objects.get(token='stats_consumption_threshold').value)
            except:
                threshold = 50.0
            try:
                days_threshold = float(ConfigProject.objects.get(token='stats_days_threshold').value)
            except:
                days_threshold = 50.0
            
            prev_stats = BillingConsumption.objects.filter(contract=invoice.contract, is_active=True).exclude(invoice=invoice)
            from django.db.models import Avg
            baseline_daily = prev_stats.aggregate(Avg('consumption_daily_avg'))['consumption_daily_avg__avg']
            baseline_days = prev_stats.aggregate(Avg('consumption_days'))['consumption_days__avg']
            
            if baseline_daily and baseline_days:
                is_high_consumption = daily_avg > float(baseline_daily) * (1 + threshold / 100)
                
                is_anomaly_long_period = is_high_consumption and days > float(baseline_days) * (1 + days_threshold / 100)
                is_anomaly_short_period = is_high_consumption and days < float(baseline_days) * (1 - days_threshold / 100)
                
                if is_anomaly_long_period or is_anomaly_short_period:
                    is_active_stat = False

        # --- Crear o actualitzar el consum ---
        BillingConsumption.objects.update_or_create(
            invoice=invoice,
            defaults={
                'contract': invoice.contract,
                'year': period_year,
                'month': period_month,
                'consumption': consumption,
                'consumption_days': days,
                'consumption_daily_avg': daily_avg,
                'consumption_avg': avg_consumption,
                'total_amount': total_amount,
                'total_amount_avg': avg_amount,
                'tax_amount': tax_amount,
                'net_amount': net_amount,
                'is_active': is_active_stat,
            }
        )

        return f"Billing consumption updated for invoice {invoice.token}"

    except Exception as e:
        return f"Error updating billing consumption for invoice {invoice_id}: {e}"

@shared_task
def update_billing_consumption_batch(invoice_ids):
    from django.db import close_old_connections
    close_old_connections()
    results = []
    for invoice_id in invoice_ids:
        try:
            res = update_billing_consumption(invoice_id)
            results.append(res)
        except Exception as e:
            results.append(f"Error in batch for invoice {invoice_id}: {e}")
    close_old_connections()
    return f"Processed {len(invoice_ids)} invoices"

@shared_task
def backfill_billing_consumption():
    try:
        invoices = Invoice.objects.filter(
            is_confirmed=True,
            type_final='F',
            billing_consumption__isnull=True
        ).exclude(status_id=1)
        total = invoices.count()
        print(f"Backfilling billing consumption for {total} invoices...")

        # Iterator: no petes la RAM
        for i, invoice in enumerate(invoices.iterator(chunk_size=1000), start=1):
            update_billing_consumption.run(invoice.id)
            if i % 500 == 0:
                print(f"Progress {i}/{total}")

        return f"Backfilled billing consumption for {total} invoices"
    except Exception as e:
        return f"Error backfilling billing consumption: {e}"

def prefill_invoice_periods():
    qs = Invoice.objects.filter(
        billing_period_year__isnull=True,
        issue_date__isnull=False
    )
    total = qs.count()
    print(f"Fixing billing period for {total} invoices...")

    for i, inv in enumerate(qs.iterator(chunk_size=1000), start=1):
        d = inv.issue_date  # és DateField: objecte date
        inv.billing_period_year = d.year
        inv.billing_period_month = d.month
        inv._skip_signal = True
        inv.save(update_fields=['billing_period_year', 'billing_period_month'])
        if i % 500 == 0:
            print(f"Progress {i}/{total}")

    return f"Fixed billing period for {total} invoices"

class MockRequest:
  def __init__(self, data):
    self.data = data


def execute_report(generator_func_name, report_data, task=None, skip_general_report=False):
  """Run an AvailableReport generator in-process (no Celery enqueue).

  Same mapping and payload normalisation as `run_report_task`, so daily
  documents can reuse it while already inside `generate_daily_documents`.

  When `skip_general_report` is True (daily documents), `save_report` still
  uploads the file but does not create a GeneralReport row.

  Returns (document_id, filename). Raises on error.
  """
  if not report_data:
    report_data = {}
  else:
    report_data = dict(report_data)

  start_date_val = report_data.get('start_date')
  end_date_val = report_data.get('end_date')
  date_range_val = report_data.get('date_range')

  if start_date_val and end_date_val and not date_range_val:
    start_date_iso = f"{start_date_val}T00:00:00.000Z" if 'T' not in str(start_date_val) else start_date_val
    end_date_iso = f"{end_date_val}T23:59:59.999Z" if 'T' not in str(end_date_val) else end_date_val
    report_data['date_range'] = [start_date_iso, end_date_iso]
  elif date_range_val and isinstance(date_range_val, list) and len(date_range_val) >= 2:
    if not start_date_val:
      report_data['start_date'] = date_range_val[0]
    if not end_date_val:
      report_data['end_date'] = date_range_val[1]

  if report_data.get('date_range') and isinstance(report_data['date_range'], list) and len(report_data['date_range']) >= 2:
    d0 = str(report_data['date_range'][0])
    d1 = str(report_data['date_range'][1])
    if d0 and 'T' not in d0:
      report_data['date_range'][0] = f"{d0[:10]}T00:00:00.000Z"
    if d1 and 'T' not in d1:
      report_data['date_range'][1] = f"{d1[:10]}T23:59:59.999Z"

  from statistics.utils.report_filters import get_billing_ids
  remittance_funcs = {
    'aqua_remittance_report',
    'wallet_unpaid_summary',
    'wallet_all_unpaid_summary',
  }
  merged_billing_ids = get_billing_ids(
    report_data,
    include_legacy_id=generator_func_name not in remittance_funcs,
  )
  if merged_billing_ids:
    report_data['billing_ids'] = merged_billing_ids
    if len(merged_billing_ids) == 1 and not report_data.get('id'):
      report_data['id'] = merged_billing_ids[0]
  else:
    billing_id = report_data.get('billing_id')
    if billing_id and not report_data.get('id'):
      report_data['id'] = billing_id

  if generator_func_name in ['aqua_remittance_report', 'wallet_unpaid_summary', 'wallet_all_unpaid_summary']:
    if report_data.get('id') and not report_data.get('remittance_id'):
      report_data['remittance_id'] = report_data.get('id')
    elif report_data.get('remittance_id') and not report_data.get('id'):
      report_data['id'] = report_data.get('remittance_id')

  if generator_func_name in ['accounting_values_report', 'accounting_values_invoice_report', 'accounting_values_payment_report', 'accounting_values_commitment_report']:
    if generator_func_name == 'accounting_values_invoice_report':
      acc_type = 'INVOICE'
    elif generator_func_name == 'accounting_values_payment_report':
      acc_type = 'PAYMENT'
    elif generator_func_name == 'accounting_values_commitment_report':
      acc_type = 'COMMITMENT'
    else:
      acc_type = report_data.get('accounting_type') or report_data.get('account_type') or 'INVOICE'

    report_data['accounting_type'] = acc_type
    report_data['account_type'] = acc_type
    generator_func_name = 'accounting_values_report'

  if generator_func_name == 'aca_summary_report' and str(report_data.get('version')) == '2':
    generator_func_name = 'aca_summary_report_second_ver'

  from contextlib import nullcontext
  from statistics.views.reports_views import black_fill, white_bold_font, without_general_report
  from statistics.utils.report_service import (
    generate_accounting_values_report, generate_aqua_remittance_report, generate_register_billing_summary,
    generate_order_time_summary, generate_bails_report, generate_mini_register_billing_summary, generate_sii_report
  )
  from statistics.utils.report_billing_service import (
    get_report_billing_summary, generate_aca_summary_report, generate_detailed_billing_summary,
    generate_billing_summary_by_supply_type, generate_billing_summary_by_rates, generate_billing_taxes_summary,
    generate_billing_taxes_detailed_summary, generate_billing_detailed_consumption_summary, generate_aca_summary_report_second_ver,
    generate_report_billing_total_by_person, generate_report_billing_347,
    generate_cobraments_report, generate_recaptacio_conceptes_excel,
    generate_clavegueram_invoices_excel, generate_no_register_aca_contracts_report
  )
  from statistics.utils.report_wallet_service import (
    generate_wallet_summary, generate_wallet_bank_list, generate_wallet_bank_summary, generate_wallet_bank_detailed_summary, generate_wallet_cash_detailed_summary,
    generate_wallet_unpaid_detailed_summary, generate_wallet_unpaid_summary, generate_wallet_all_unpaid_summary, generate_total_customers_debt_summary,
    generate_sgt_txt_report, generate_pending_invoices_values_report
  )
  from statistics.utils.report_contract_export_service import generate_contracts_export_report
  from statistics.utils.report_contract_invoice_reading_summary_service import (
      generate_contract_invoice_reading_summary_report,
  )
  from statistics.utils.report_contract_tariffs_export_service import (
      generate_contract_tariffs_export_report,
  )
  from statistics.utils.report_contract_termination_export_service import (
    generate_contract_termination_export_report,
  )
  from statistics.utils.report_wincen_service import generate_wincen_export_report
  from statistics.utils.report_incasol_liquidation_service import generate_incasol_liquidation_report
  from statistics.utils.report_general_billing_summary_service import generate_general_billing_summary_report
  from statistics.utils.daily_activity_service import generate_daily_activity_summary_report
  from statistics.utils.report_advanced_billing_service import (
    generate_detailed_typology_periodicity_report, generate_detailed_concept_report,
    generate_non_tariff_income_report, generate_subscriber_evolution_report,
    generate_social_tariff_evolution_report, generate_claim_response_time_report,
    generate_management_volume_report
  )
  from statistics.utils.report_accounting_service import generate_general_accounting_report
  from statistics.utils.report_billing_by_zone_service import generate_billing_by_zone_report

  generator_funcs = {
    'accounting_values_report': generate_accounting_values_report,
    'aqua_remittance_report': generate_aqua_remittance_report,
    'register_billing_summary': generate_register_billing_summary,
    'get_report_billing_summary': get_report_billing_summary,
    'aca_summary_report': generate_aca_summary_report,
    'aca_summary_report_second_ver': generate_aca_summary_report_second_ver,
    'bails_report': generate_bails_report,
    'wallet_summary': generate_wallet_summary,
    'sii_report': generate_sii_report,
    'pending_invoices_values_report': generate_pending_invoices_values_report,
    'sgt_txt_report': generate_sgt_txt_report,
    'no_register_aca_contracts_report': generate_no_register_aca_contracts_report,
    'total_customers_debt_report': generate_total_customers_debt_summary,
    'wallet_bank_list': generate_wallet_bank_list,
    'wallet_bank_summary': generate_wallet_bank_summary,
    'wallet_bank_detailed_summary': generate_wallet_bank_detailed_summary,
    'wallet_cash_detailed_summary': generate_wallet_cash_detailed_summary,
    'wallet_unpaid_detailed_summary': generate_wallet_unpaid_detailed_summary,
    'wallet_unpaid_summary': generate_wallet_unpaid_summary,
    'wallet_all_unpaid_summary': generate_wallet_all_unpaid_summary,
    'order_time_summary': generate_order_time_summary,
    'detailed_billing_summary': generate_detailed_billing_summary,
    'billing_summary_by_supply_type': generate_billing_summary_by_supply_type,
    'billing_summary_by_rates': generate_billing_summary_by_rates,
    'billing_taxes_summary': generate_billing_taxes_summary,
    'billing_taxes_detailed_summary': generate_billing_taxes_detailed_summary,
    'billing_detailed_consumption_summary': generate_billing_detailed_consumption_summary,
    'mini_register_billing_summary': generate_mini_register_billing_summary,
    'report_billing_total_by_person': generate_report_billing_total_by_person,
    'report_billing_347': generate_report_billing_347,
    'contracts_export_report': generate_contracts_export_report,
    'contracts_invoice_reading_summary_report': generate_contract_invoice_reading_summary_report,
    'contracts_tariffs_export_report': generate_contract_tariffs_export_report,
    'contracts_termination_export_report': generate_contract_termination_export_report,
    'recaptacio_excel_report': generate_recaptacio_conceptes_excel,
    'cobraments_excel_report': generate_cobraments_report,
    'detailed_typology_periodicity_report': generate_detailed_typology_periodicity_report,
    'general_billing_summary_report': generate_general_billing_summary_report,
    'detailed_concept_report': generate_detailed_concept_report,
    'non_tariff_income_report': generate_non_tariff_income_report,
    'subscriber_evolution_report': generate_subscriber_evolution_report,
    'social_tariff_evolution_report': generate_social_tariff_evolution_report,
    'claim_response_time_report': generate_claim_response_time_report,
    'management_volume_report': generate_management_volume_report,
    'recaptacio_conceptes_report': generate_recaptacio_conceptes_excel,
    'clavegueram_invoices_report': generate_clavegueram_invoices_excel,
    'wincen_export_report': generate_wincen_export_report,
    'incasol_liquidation_report': generate_incasol_liquidation_report,
    'general_accounting_report': generate_general_accounting_report,
    'daily_activity_summary_report': generate_daily_activity_summary_report,
    'billing_by_zone_report': generate_billing_by_zone_report,
  }

  if generator_func_name not in generator_funcs:
    raise ValueError(f"Unknown generator function: {generator_func_name}")

  generator_func = generator_funcs[generator_func_name]
  mock_request = MockRequest(report_data)

  import inspect
  sig = inspect.signature(generator_func)

  report_ctx = without_general_report() if skip_general_report else nullcontext()
  with override(settings.LANGUAGE_CODE), report_ctx:
      if 'task' in sig.parameters:
          result = generator_func(mock_request, black_fill, white_bold_font, task=task)
      else:
          result = generator_func(mock_request, black_fill, white_bold_font)

  from rest_framework.response import Response

  def _raise_if_generator_error(response):
    if not isinstance(response, Response):
      return
    data = response.data if isinstance(response.data, dict) else {}
    if data.get('warning'):
      raise ReportWarning(data['warning'])
    if response.status_code >= 400:
      error_msg = data.get('error', 'Unknown error') if data else str(response.data)
      raise Exception(f"Generator returned error: {error_msg}")

  if isinstance(result, Response):
    _raise_if_generator_error(result)
    raise Exception("Generator returned error: Unknown error")

  response, document_id, filename = result
  _raise_if_generator_error(response)

  if not document_id:
    raise Exception("Generator did not produce a document")

  if not filename:
    from documentmanager.models import Document
    try:
      filename = Document.objects.get(id=document_id).document_name
    except Document.DoesNotExist:
      pass

  return document_id, filename


@shared_task(bind=True)
def run_report_task(self, generator_func_name, report_data, queue_item_id=None):
  from statistics.models import ReportQueue, GeneralReport

  # El task_id ja el desa process_next_report_queue_item en engegar l'item; no se
  # l'autoassigna, perquè una tasca revocada que arrenqués tard es quedaria un item reiniciat.
  q_item = None
  if queue_item_id:
    try:
      q_item = ReportQueue.objects.get(id=queue_item_id)
    except ReportQueue.DoesNotExist:
      pass

  try:
    if not report_data:
      report_data = {}
    else:
      report_data = dict(report_data)

    if q_item and q_item.report:
      if 'name' not in report_data or not report_data.get('name'):
        report_data['name'] = q_item.report.name
      if 'type_id' not in report_data or not report_data.get('type_id'):
        if q_item.report.section_id:
          report_data['type_id'] = q_item.report.section_id

    document_id, filename = execute_report(generator_func_name, report_data, task=self)

    if q_item:
      from django.utils import timezone
      _close_report_queue_item(
        q_item.id, self.request.id, status='completed', completed_at=timezone.now(), document_id=document_id,
      )
      if document_id:
        # GeneralReport i ReportQueue no tenen FK entre ells; comparteixen el mateix
        # document_id un cop generat l'informe (save_report a reports_views.py). Es
        # copien els filtres ja calculats al ReportQueue, sense recalcular-los.
        GeneralReport.objects.filter(document_id=document_id).update(
          filters=q_item.payload,
          filters_display=q_item.filters_display,
        )

    print("✅ Report generated successfully")
    return {
      "status": "success",
      "message": "Report generated successfully",
      "document_id": document_id,
      "filename": filename,
    }
  except ReportWarning as e:
    if q_item:
      from django.utils import timezone
      _close_report_queue_item(q_item.id, self.request.id, status='warning', completed_at=timezone.now(), error_message=str(e))

    print(f"⚠️ Report warning: {e}")
    return {
      "status": "warning",
      "message": str(e),
    }
  except Exception as e:
    if q_item:
      from django.utils import timezone
      _close_report_queue_item(q_item.id, self.request.id, status='failed', completed_at=timezone.now(), error_message=str(e))

    print(f"❌ Error generating report: {e}")
    return {
      "status": "error",
      "message": f"Error generating report: {e}",
    }


def process_next_report_queue_item():
  from statistics.models import ReportQueue
  from django.utils import timezone
  
  if ReportQueue.objects.filter(status='running').exists():
    return

  next_item = ReportQueue.objects.filter(status='pending').order_by('created_at').first()
  if not next_item:
    return

  # El task_id es genera abans d'encuar i es desa amb l'estat `running` en un sol pas:
  # així un kill fet just després d'engegar l'item sempre troba quina tasca ha de matar,
  # i la tasca pot comprovar en acabar que l'item continua sent seu.
  task_id = str(uuid.uuid4())
  next_item.status = 'running'
  next_item.started_at = timezone.now()
  next_item.task_id = task_id
  next_item.save(update_fields=['status', 'started_at', 'task_id'])

  try:
    run_report_task.apply_async(
      args=[next_item.report.function_name, next_item.payload],
      kwargs={'queue_item_id': next_item.id},
      task_id=task_id,
    )
  except Exception as e:
    next_item.status = 'failed'
    next_item.completed_at = timezone.now()
    next_item.error_message = str(e)
    next_item.save(update_fields=['status', 'completed_at', 'error_message'])
    process_next_report_queue_item()


def _close_report_queue_item(queue_item_id, task_id, **fields):
  """
  Tanca l'item de la cua amb `fields` (status, completed_at...) només si continua en
  `running` i assignat a aquesta tasca, i llavors avança la cua. Si mentre corria l'han
  matat, saltat o reiniciat des del frontal, l'item ja no és d'aquesta tasca: no se'n
  trepitja l'estat ni s'engega el següent, que ja ho ha fet `apply_report_queue_action`.
  Retorna si l'ha tancat.
  """
  from statistics.models import ReportQueue

  closed = ReportQueue.objects.filter(id=queue_item_id, status='running', task_id=task_id).update(**fields)
  if closed:
    process_next_report_queue_item()
  return bool(closed)


def apply_report_queue_action(queue_item, action):
  """
  Aplica una acció manual (kill/skip/restart) sobre un ReportQueue.
  - kill: mata la tasca de Celery (si està en running) i el marca com a failed.
  - skip: mata la tasca (si està en running) i el marca com a skipped, sense reintentar-lo.
  - restart: mata la tasca (si està en running) i el torna a encuar des de zero (status=pending),
    conservant el `payload` original. Un cop marcat com a pending, `process_next_report_queue_item`
    el recollirà quan li toqui el torn (ordenat per `created_at`, i sempre que no hi hagi cap altre
    item en `running`).

  Si l'ordre no arriba a Celery es llança `QueueTaskRevokeError` sense tocar res: marcar
  l'item com a aturat engegaria el següent mentre aquest continua corrent.
  """
  from django.utils import timezone
  from customers.queue_utils import revoke_queue_task

  if action not in ('kill', 'skip', 'restart'):
    raise ValueError(f"Acció no vàlida: {action}")

  if queue_item.status == 'running':
    revoke_queue_task(queue_item.task_id)

  now = timezone.now()
  if action == 'kill':
    queue_item.status = 'failed'
    queue_item.error_message = 'Tasca aturada manualment per un usuari.'
    queue_item.completed_at = now
  elif action == 'skip':
    queue_item.status = 'skipped'
    queue_item.error_message = queue_item.error_message or 'Tasca saltada manualment per un usuari.'
    queue_item.completed_at = now
  elif action == 'restart':
    queue_item.status = 'pending'
    queue_item.task_id = None
    queue_item.error_message = None
    queue_item.started_at = None
    queue_item.completed_at = None

  queue_item.save()

  # Allibera/avança la cua FIFO (només actua si no hi ha cap altre item en running).
  process_next_report_queue_item()


@shared_task(bind=True)
def calculate_median_consumption(self):
  try:
    print("Starting daily consumption calculations...")

    active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
    active_contract = ContractStatus.objects.get(token=active_contract_token)

    contracts = Contract.objects.filter(status=active_contract, is_active=True)
    total = contracts.count()
    print(f"Found {total} active contracts.")

    self.update_state(state='PROGRESS', meta={'current': 0, 'total': total, 'percent': 0.0})

    for i, contract in enumerate(contracts.iterator(), start=1):
      # Ara retorna {(year, month): median_daily_value}
      stats = calculate_consumption(contract)

      if not stats:
        pass
      else:
        # Si hem calculat stats noves, eliminem les antigues legacy (sense any) del contracte
        ContractConsumption.objects.filter(contract=contract, year__isnull=True).delete()

        for (year, month), daily_avg in stats.items():
          if daily_avg is None:
              continue

          daily_consumption = Decimal(str(daily_avg)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
          if daily_consumption < 0:
            daily_consumption = 0

          # Mantenim el camp 'consumption' per compatibilitat assumint 30.44 dies
          total_monthly_approx = daily_consumption * Decimal('30.44')

          ContractConsumption.objects.update_or_create(
              contract=contract,
              year=year,
              period=month,
              defaults={
                  'daily_consumption': daily_consumption,
                  'consumption': total_monthly_approx,
                  'is_active': True
              }
          )

      if i % 50 == 0 or i == total:
          percent = round((i / total) * 100, 2) if total > 0 else 100.0
          print(f"Progress: {i}/{total} contracts processed ({percent}%)...")
          self.update_state(state='PROGRESS', meta={'current': i, 'total': total, 'percent': percent})

    print("✅ Finished all daily consumption calculations.")
  except Exception as e:
    print(f"Error in calculate_median_consumption: {e}")

    
def calculate_consumption(contract):
  today = datetime.today()
  five_years_ago = (today - timedelta(days=5*365)).date()

  # Recuperem TOTS els registres actius per tenir la seqüència i poder calcular dies transcorreguts
  readings_qs = Reading.objects.filter(
    contract=contract,
    is_active=True,
    is_control=False,
    is_estimated=False,
    is_initial=False,
    reading_value__isnull=False,
    calculated_value__isnull=False,
    reading_date__isnull=False
  ).order_by('reading_date')

  # Primers càlculs per determinar les mitjanes/medianes base del contracte per detectar anomalies
  # LÒGICA D'INCENDIS
  fire_usage_tokens = get_fire_usage_tokens()

  is_fire_hydrant = contract.use_type and contract.use_type.token in fire_usage_tokens

  all_dailies = []
  all_days = []
  temp_readings = []
  
  prev_reading_date = None
  for r in readings_qs:
      days = r.consumption_days
      if not days or days <= 0:
          if prev_reading_date:
              days = (r.reading_date - prev_reading_date).days
      
      prev_reading_date = r.reading_date
      
      if days and days > 0:
          # Consum net (sense fuites) per a l'estadística
          if is_fire_hydrant:
              net_val = 0
          else:
              net_val = float(r.calculated_value) - float(r.leak_value or 0)
          daily_val = net_val / float(days)
          all_dailies.append(daily_val)
          all_days.append(float(days))
          temp_readings.append((r, daily_val, days))

  if not all_dailies:
      return {}

  baseline_daily = _median(all_dailies)
  baseline_days = _median(all_days)

  # Llindars des de ConfigProject
  try:
      threshold = float(ConfigProject.objects.get(token='stats_consumption_threshold').value)
  except:
      threshold = 50.0
  try:
      days_threshold = float(ConfigProject.objects.get(token='stats_days_threshold').value)
  except:
      days_threshold = 50.0

  period_values = defaultdict(list)

  for r, daily_value, days in temp_readings:
    # Procés de filtratge: només ens interessen els últims 5 anys per a la estadística final
    if r.reading_date < five_years_ago:
      continue
    
    # Comprovar si és una anomalia (disparada en consum I un període fora del normal)
    is_high_consumption = daily_value > baseline_daily * (1 + threshold / 100)
    
    is_anomaly_long_period = is_high_consumption and days > baseline_days * (1 + days_threshold / 100)
    is_anomaly_short_period = is_high_consumption and days < baseline_days * (1 - days_threshold / 100)
    
    if is_anomaly_long_period or is_anomaly_short_period:
        # Excloem aquesta lectura de l'estadística
        continue

    year = r.reading_date.year
    month = r.reading_date.month
    period_values[(year, month)].append(daily_value)

  # Compute medians for each year/month period
  period_medians = {
    period: _median(values)
    for period, values in period_values.items()
    if values
  }

  return period_medians


@shared_task(bind=True)
def generate_daily_documents(self):
  try:
    available_templates = DailyDocumentTemplate.objects.filter(is_active=True).select_related('available_report')
    current_time = datetime.now()
    pending_status_token = ConfigProject.objects.get(token='daily_document_status_pending_token').value
    pending_status = DailyDocumentStatus.objects.get(token=pending_status_token)
    for template in available_templates:
      generate_daily_document(template, current_time, pending_status)
    
  except Exception as e:
    print(f"Error while generating daily documents: {e}")

@shared_task
def regenerate_daily_document(daily_document_id):
  try:
    daily_document = DailyDocument.objects.get(id=daily_document_id)
    current_time = daily_document.document_date
    if not daily_document.template:
      raise ValueError("Daily document has no template")
    now = timezone.now().date()
    document = None
    error_message = None
    try:
      document = execute_available_report(daily_document.template.available_report, {
        'start_date': current_time.strftime('%Y-%m-%d'),
        'end_date': current_time.strftime('%Y-%m-%d'),
        'name': f"{daily_document.template.name} {current_time.strftime('%Y/%m/%d')}",
      })
    except Exception as e:
      error_message = str(e)
      
    if error_message:
      daily_document.creation_error = error_message
    if document:
      daily_document.document = document
      
    daily_document.save()
    
  except Exception as e:
    print(f"Error while generating daily documents: {e}")
  
  

@shared_task
def check_daily_documents_due_date():
  print("check daily documents due date")
  try:
    now = timezone.now().date()
    pending_status_token = ConfigProject.objects.get(token='daily_document_status_pending_token').value
    expired_status_token = ConfigProject.objects.get(token='daily_document_status_expired_token').value
    expired_status = DailyDocumentStatus.objects.get(token=expired_status_token)
    daily_documents = DailyDocument.objects.filter(due_date__lte=now, status__token=pending_status_token)
    print(f"Found {daily_documents.count()} daily documents due date")

    if len(daily_documents) > 0:
      daily_documents.update(status=expired_status)
      with translation.override(settings.LANGUAGE_CODE):
        notification_save = {
          'token': uuid.uuid4(),
          'name': _("Expired daily documents"),
          'description': _("Daily documents declared as expired on %(date)s") % {"date": now.strftime('%d/%m/%Y')},
          'module': 'statistics',
          'entity': 'daily_document',
          'object_id': None,
          'is_active': True
        }
      Notification.objects.create(**notification_save)
  except Exception as e:
    print(f"Error while checking daily documents due date: {e}")
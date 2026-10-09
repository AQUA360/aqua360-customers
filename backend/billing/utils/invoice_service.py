import datetime
from decimal import Decimal
from datetime import date
import math
import os
import time
from billing.utils.confirm_invoice_service import confirm_invoice
from coredata.utils.other_utils import round_ceil
from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.db.models import Sum, F
from django.db import transaction, connection
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from billing.utils.reading_service import calculate_estimated_bag, count_general_meter_billable_targets
from contract.models import Bail, Contract, ContractRequest, ContractTerminationRequest, PaymentType, PiggyBankMovement
from coredata.utils.name_utils import generate_token
from coredata.utils.validators_utils import validate_nif
from logger.models import LogInvoiceChangeStatus, LogInvoiceDataChange
from service.models import Company, CompanyBank, ConnectionRequest, Exploitation, Meter, SupplyPoint, SupplyPointStatus
from claimrequest.models import ClaimRequest
from coredata.models import ConfigProject, Person, PersonBank, PersonContact, PersonPiggyBankMovement
from pricing.models import BillingRange, LineItemType, PriceRate, Product, ProductOrigin, Tax
from pricing.utils.tax_service import tax_by_percent
from billing.models import AppliedAdjustment, EstimatedBag, Payment, Reading, ReadingBatch, InvoiceType, InvoiceCategory, InvoiceStatus, InvoiceSerie, InvoiceClass, Invoice, InvoiceLineItem, PaymentStatus, InvoiceSequence
from django.db.models import Q

from coredata.utils.address_utils import get_address_complete_without_city, get_address_complete_with_city

from billing.utils.adjustment_service import calc_consumption_responsible
from .invoice_line_item_service import create_from_lineitemtype, create_from_lineitemtype_connection, constrain_total_value, get_last_reading
from faker import Faker
fake = Faker()

origin_reading = None
invoice_type_invoice = None
invoice_pending_status = None
invoice_cancelled_status = None
invoice_class = None
default_serie = None
simplified_serie = None
_active_supply_point_status = None

def resolve_selected_company(exploitation, default_company, company_id):
    """Resol l'empresa a assignar a una factura quan l'usuari en tria explícitament
    una entre les vinculades a l'explotació (Exploitation.companies), validant que
    hi pertany; en cas contrari retorna default_company sense canvis."""
    if not company_id:
        return default_company
    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return default_company
    if exploitation and exploitation.companies.filter(id=company_id).exists():
        return Company.objects.filter(id=company_id).first() or default_company
    return default_company


def resolve_selected_category(category_id):
    if not category_id:
        return None
    return InvoiceCategory.objects.filter(id=category_id).first()


def get_simplified_serie():
    global simplified_serie
    if simplified_serie is None:
        simplified_serie = InvoiceSerie.objects.filter(token=ConfigProject.objects.get(token='token_simplified_invoice_serie').value).first()
    return simplified_serie
def get_default_serie():
    global default_serie
    if default_serie is None:
        default_serie = InvoiceSerie.objects.filter(is_default=True).first()
    return default_serie
def get_origin_reading():
    global origin_reading
    if origin_reading is None:
        origin_reading = ProductOrigin.objects.get(token=ConfigProject.objects.get(token='origin_reading_token').value)
    return origin_reading
def get_invoice_type_invoice():
    global invoice_type_invoice
    if invoice_type_invoice is None:
        invoice_type_invoice = InvoiceType.objects.get(token=ConfigProject.objects.get(token='invoice_type_invoice_token').value)
    return invoice_type_invoice
def get_invoice_pending_status():
    global invoice_pending_status
    if invoice_pending_status is None:
        invoice_pending_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_pending_token').value)
    return invoice_pending_status

def get_invoice_cancelled_status():
    global invoice_cancelled_status
    if invoice_cancelled_status is None:
        invoice_cancelled_status = InvoiceStatus.objects.get(
            token=ConfigProject.objects.get(token='invoice_status_cancelled_token').value
        )
    return invoice_cancelled_status

def reading_has_blocking_invoices(reading):
    """
    Returns True if the reading has any invoice with a status different from
    pending or cancelled.
    """
    if not reading:
        return False
    pending_status = get_invoice_pending_status()
    cancelled_status = get_invoice_cancelled_status()
    return reading.invoices.exclude(status__in=[pending_status, cancelled_status]).exists()


def get_close_previous_reading(reading, *, same_contract=False, no_billing=False):
    """
    Return reading.previous_reading when it is a close reading that should be
    folded into the current reading (no blocking invoices).

    Optionally require the same contract and that the previous reading is not
    already billed.
    """
    if not reading or not reading.previous_reading or not reading.previous_reading.is_close:
        return None
    prev = reading.previous_reading
    if reading_has_blocking_invoices(prev):
        return None
    if same_contract and reading.contract.id != prev.contract.id:
        return None
    if no_billing and prev.billing:
        return None
    return prev


def get_close_previous_previous_reading(reading, *, same_contract=False, no_billing=False):
    """
    Return reading.previous_reading.previous_reading when it is a close reading
    that should be folded into the current reading (neither previous nor
    previous.previous has blocking invoices).

    Optionally require the same contract and that previous.previous is not
    already billed.
    """
    if not reading or not reading.previous_reading:
        return None
    prev = reading.previous_reading
    prev_prev = prev.previous_reading
    if not prev_prev or not prev_prev.is_close:
        return None
    if reading_has_blocking_invoices(prev) or reading_has_blocking_invoices(prev_prev):
        return None
    if same_contract and reading.contract.id != prev_prev.contract.id:
        return None
    if no_billing and prev_prev.billing:
        return None
    return prev_prev


def get_leak_value(reading):
    """
    Returns the reading's leak_value as a positive float. leak_value is nullable,
    so absent or negative values are normalised to 0.0.
    """
    if not reading:
        return 0.0
    try:
        leak_value = float(reading.leak_value or 0)
    except (TypeError, ValueError):
        return 0.0
    return leak_value if leak_value > 0 else 0.0

def accumulate_added_leak(added_leak_by_reading, reading, source_reading=None):
    """
    Accumulates source_reading's leak into added_leak_by_reading[reading.id],
    keeping the existing behaviour of only adding while the entry is still 0.

    The entry is always written as a number, so a reading present in the dict can
    never hold None. Pass source_reading=None to just initialise the entry.
    """
    if added_leak_by_reading is None or not reading:
        return added_leak_by_reading
    added_leak = added_leak_by_reading.get(reading.id) or 0.0
    if added_leak == 0:
        added_leak += get_leak_value(source_reading)
    added_leak_by_reading[reading.id] = float(added_leak)
    return added_leak_by_reading

def get_added_leak(added_leak_by_reading, reading):
    """Returns the accumulated leak for a reading as a float, never None."""
    if not added_leak_by_reading or not reading:
        return 0.0
    return float(added_leak_by_reading.get(reading.id) or 0.0)

def get_invoice_class():
    global invoice_class
    if invoice_class is None:
        invoice_class = InvoiceClass.objects.get(token='OO') 
    return invoice_class



def get_reading_estimated_flag():
    """Cache and return the reading_estimated config value as lowercase string."""
    # reuse module-level cache via a global
    global _reading_estimated_cached
    try:
        return _reading_estimated_cached
    except NameError:
        _reading_estimated_cached = ConfigProject.objects.get(token='reading_estimated').value.lower()
        return _reading_estimated_cached


def get_active_supply_point_status():
    global _active_supply_point_status
    if _active_supply_point_status is None:
        _active_supply_point_status = SupplyPointStatus.objects.get(
            token=ConfigProject.objects.get(token='supply_point_status_activate_token').value
        )
    return _active_supply_point_status

def get_totals(invoice, include_zero_percent=False, line_items=None):
    subtotal = 0
    taxes = {}
    taxes_base = {}
    if line_items is None:
        line_items = invoice.line_items.filter(is_active=True).all()
    for line_item in line_items:
        if getattr(line_item, 'is_active', True) is False:
            continue
        # Guard against None/invalid price or tax_price (round_ceil treats them as 0)
        subtotal += round_ceil(line_item.price)
        total = subtotal
        if line_item.tax_percent is None:
            continue
        if not include_zero_percent and int(line_item.tax_percent) == 0:
            continue
        percent = str(line_item.tax_percent)
        if taxes.get(percent) is None:
            taxes[percent] = 0
        if taxes_base.get(percent) is None:
            taxes_base[percent] = 0
        taxes[percent] += round_ceil(line_item.tax_price)
        taxes_base[percent] += round_ceil(line_item.price)
    total_taxes = 0
    for tax in taxes.values():
        total_taxes += round_ceil(tax)
    total = round_ceil(subtotal) + round_ceil(total_taxes)
    return subtotal, taxes, taxes_base, round_ceil(total)



def check_readings_values(readings, invoice, contract):
    try:
        readings_to_update = []
        for reading in readings:
            if not reading.consumption_days:
                if reading.previous_reading and reading.previous_reading.reading_date:
                    # Ensure both dates are date objects
                    prev_date = reading.previous_reading.reading_date
                    if isinstance(prev_date, datetime.datetime):
                        prev_date = prev_date.date()
                    reading.consumption_days = (reading.reading_date - prev_date).days
                else:
                    reading.consumption_days = invoice.consumption_days
                    # "Facturar període complert": no es retalla el període a la data del contracte
                    if contract and not contract.bill_full_period and (contract.registration_date or contract.created_at):
                        # Convert datetime to date for comparison
                        contract_date = contract.registration_date if contract.registration_date else (contract.created_at.date() if isinstance(contract.created_at, datetime.datetime) else contract.created_at)
                        if (reading.reading_date - contract_date).days < invoice.consumption_days:
                            reading.consumption_days = (reading.reading_date - contract_date).days
                readings_to_update.append(reading)
        
        if readings_to_update:
            Reading.objects.bulk_update(readings_to_update, ['consumption_days'])
                    
    except Exception as e:
        pass  # log removed


def pre_check_readings(readings):
    og_prev_reading = None
    reading_to_remove = []  # TEMPORARY FIX
    for reading in sorted(readings, key=lambda r: r.reading_date):
        if og_prev_reading:
            if (
                reading.previous_reading and 
                reading.previous_reading.id == og_prev_reading.id and
                    (
                        not og_prev_reading.previous_reading or
                        (
                            og_prev_reading.previous_reading and
                            og_prev_reading.contract.id != og_prev_reading.previous_reading.contract.id
                        )
                    )
                ):
                reading_to_remove.append(og_prev_reading.id)
        og_prev_reading = reading
        
        if reading.reading_value is None:
            reading.reading_value = 0
            if reading.previous_reading and reading.previous_reading.reading_value:
                reading.reading_value = reading.previous_reading.reading_value

        """ if reading.previous_reading and reading.previous_reading.reading_value is not None and reading.reading_value is not None:
            # Recalculate calculated_value to ensure consistency
            if reading.reading_value >= reading.previous_reading.reading_value:
                new_calc_value = float(reading.reading_value - reading.previous_reading.reading_value)
            else:
                # Potential meter cycle, use check_overflow_value if available or stick to 0
                from billing.utils.reading_service import check_overflow_value
                new_calc_value = float(check_overflow_value(reading, reading.previous_reading))
            
            if reading.calculated_value != new_calc_value:
                reading.calculated_value = new_calc_value """

        if reading.calculated_value < 0:
            reading.calculated_value = 0
            
        contract_date = reading.contract.registration_date if reading.contract and reading.contract.registration_date else (reading.contract.created_at.date() if reading.contract and reading.contract.created_at else None)
        # "Facturar període complert": els dies de consum no es retallen a la data del contracte
        # (la lectura inicial pot ser una lectura del contracte anterior, prèvia a l'alta).
        if reading.contract and reading.contract.bill_full_period:
            contract_date = None
        
        if (contract_date and ((reading.previous_reading and reading.previous_reading.reading_date < contract_date) or not reading.previous_reading)):
            reading.consumption_days = (reading.reading_date - contract_date).days
        else:
            if not reading.previous_reading:
                pass  # log removed
                pass  # log removed
                previous_reading = get_last_reading(reading)
                if previous_reading:
                    reading.previous_reading = previous_reading
                    reading.consumption_days = (reading.reading_date - previous_reading.reading_date).days
                    if previous_reading.meter.id != reading.meter.id:
                        reading.calculated_value = 0
        
        try: 
            estimated_bag = EstimatedBag.objects.get(supply_point=reading.supply_point, contract=reading.contract)
        except:
            estimated_bag = None
            
        if estimated_bag and estimated_bag.total_consumption > 0:
            if not reading.is_estimated and reading.estimated_used == None:
                calculate_estimated_bag(reading.calculated_value, False, reading, estimated_bag)


        if reading.previous_reading:
            expected_days = (reading.reading_date - reading.previous_reading.reading_date).days
            if reading.consumption_days != expected_days:
                reading.consumption_days = expected_days
        reading.real_consumption = float(reading.calculated_value)
        pass  # log removed
        pass  # log removed
        if reading.estimated_used and reading.real_consumption != (float(reading.calculated_value) - float(reading.estimated_used)):
            reading.real_consumption -= float(reading.estimated_used)
        pass  # log removed
        
        reading.save()

    if isinstance(readings, list):
        filtered_readings = [r for r in readings if r.id not in reading_to_remove]
        return filtered_readings
    else:
        return readings.exclude(id__in=reading_to_remove)

def generate_consumption_invoice_multiple(contract, readings, title, refactor_invoice=None, is_budget=False, extra_payment_data=None, billing=None, billing_batch=None, period_months=None, new_holder=None):
    if not any(reading.meter for reading in readings):
        print("[generate_consumption_invoice_multiple] FAILED: No meter found in readings or readings list is empty.")
        return None

    # Resoldre lectures de control a la seva versió modificada activa no-control (p. ex. modificacions a la UI)
    def resolve_reading(r):
        if r and r.is_control:
            active_r = r.modified_readings.filter(is_control=False).first()
            if active_r:
                return resolve_reading(active_r)
        return r
    new_holder_instance = None
    if new_holder:
        try:
            new_holder_instance = Person.objects.get(id=new_holder)
        except:
            pass
    
    added_leak_by_reading = {}
    
    # Resoldre i cachejar en memòria el previous_reading de forma recursiva per evitar enllaços a lectures de control obsoletes (per a canvis de comptador)
    def resolve_and_cache_previous_readings(reading, visited=None):
        if visited is None:
            visited = set()
        if not reading or reading.id in visited:
            return
        visited.add(reading.id)
        
        prev = reading.previous_reading
        if prev:
            if prev.is_control:
                active_prev = prev.modified_readings.filter(is_control=False).first()
                if active_prev:
                    prev = active_prev
            reading.previous_reading = prev
            resolve_and_cache_previous_readings(prev, visited)

    # ESTÀ BÉ SI PASSEM LECTURES DE CONTROL, JA QUE POTSER VOLEM FER UNA REFACTURA DE PROVA D'UNA LECTURA QUE HEM MODIFICAT D'UNA FACTURA ABONADA
    # readings = [resolve_reading(r) for r in readings]
    # 2. Resolem tota la cadena d'enllaços previs (previous_reading) dels comptadors anteriors en memòria
    for r in readings:
        resolve_and_cache_previous_readings(r)

    readings = pre_check_readings(readings)

    consumption_og = sum(reading.calculated_value for reading in readings)
    estimated_used_og = sum(float(reading.estimated_used) if reading.estimated_used and reading.estimated_used > 0 else 0 for reading in readings)
    
    current_reading_date = readings[0].reading_date
    previous_reading_date = readings[0].previous_reading.reading_date if readings[0].previous_reading else None
    
    # print(f"[utils/invoice_service.py] generate_consumption_invoice_multiple() Current reading date: {current_reading_date}")
    try:
        consumption_days = max(reading.consumption_days for reading in readings)
    except:
        consumption_days = None
    
    try:
        min_days = min(reading.consumption_days for reading in readings)
    except:
        min_days = None
    min_days_reading = next((r for r in readings if r.consumption_days == min_days), None)

    print(f"Contract: {contract.token}")
    print(f"Consumption og: {consumption_og}")
    for reading in readings:
        # print(f"Reading is close: {reading.is_close}")
        # print(f"Reading previous reading: {reading.previous_reading.is_close}")
        # print(f"Same contract {reading.contract.id == reading.previous_reading.contract.id}")
        # print(f"Total invoices: {reading.previous_reading.invoices.count()}")
        accumulate_added_leak(added_leak_by_reading, reading)
        added_close_ids = set()

        def _add_close_consumption(close_reading):
            nonlocal consumption_og
            nonlocal estimated_used_og
            if not close_reading or close_reading in readings or close_reading.id in added_close_ids:
                return False
            consumption_og += close_reading.real_consumption if close_reading.real_consumption > 0 else 0
            estimated_used_og += float(close_reading.estimated_used) or 0 if close_reading.estimated_used and close_reading.estimated_used > 0 else 0
            accumulate_added_leak(added_leak_by_reading, reading, close_reading)
            added_close_ids.add(close_reading.id)
            return True

        if (reading.is_close and reading.previous_reading
                and reading.contract.id == reading.previous_reading.contract.id
                and not reading_has_blocking_invoices(reading.previous_reading)
                and not reading.previous_reading.billing):
            _add_close_consumption(reading.previous_reading)
            if reading == min_days_reading:
                min_days += reading.previous_reading.consumption_days if reading.previous_reading.consumption_days else 0
        
        # si es fa un canvi de comptador, ens arriba un previous reading .is_close = True i em d'agafar la lectura anterior.
        close_prev = get_close_previous_reading(reading, same_contract=True, no_billing=True)
        if close_prev:
            _add_close_consumption(close_prev)
            if (close_prev.previous_reading
                    and not reading_has_blocking_invoices(close_prev.previous_reading)
                    and not close_prev.previous_reading.billing):
                _add_close_consumption(close_prev.previous_reading)
            if reading == min_days_reading:
                min_days += close_prev.consumption_days if close_prev.consumption_days else 0
        
        # si la lectura previa té una lectura previa i aquesta és close, agafem la lectura anterior.
        close_prev_prev = get_close_previous_previous_reading(reading, same_contract=True, no_billing=True)
        if close_prev_prev:
            # print("found change meter")
            _add_close_consumption(close_prev_prev)
            if reading == min_days_reading:
                min_days += close_prev_prev.consumption_days or 0
        try:
            # reading.real_consumption = consumption_og
            reading.save()
        except:
            pass

    # si té min_days i consumption_days, agafem el maxim entre les dues
    # print("Consumption days: ", consumption_days)
    # print("Min days: ", min_days)
    if min_days and consumption_days:
        consumption_days = max(consumption_days, min_days)
    else:
        consumption_days = consumption_days if consumption_days else min_days if min_days else None
    

    if not previous_reading_date and not consumption_days:
        previous_reading = get_last_reading(readings[0])
        previous_reading_date = previous_reading.reading_date if previous_reading else None
        if previous_reading_date:
            consumption_days = (current_reading_date - previous_reading_date).days

    total_leak = 0 
    simplified = contract.simplified_invoice
    
    reading_estimated = get_reading_estimated_flag()

    try:
        consumption = 0
        for reading in readings:
            consumption_returned, added_leak_by_reading = recalc_consumption_gen_meter(
                reading, reading.calculated_value, reading.supply_point, added_leak_by_reading, readings
            )
            consumption += consumption_returned
    
    except:
        consumption = consumption_og
    if consumption < 0:
        consumption = 0
    
    consumption_responsible = calc_consumption_responsible(contract, consumption)
    real_consumption = 0

    exploitation = None
    
    # GETTING PERIOD TIME DAYS
    period_type = ['mensual','bimestral','trimestral','semestral','anual']
    period_jumps = [1,2,3,6,12]
    
    period_days = extra_payment_data.get("period_days") if extra_payment_data and 'period_days' in extra_payment_data else period_jumps[period_type.index(billing.biller.period_type)] * 30 if billing else None
    issue_date_str = extra_payment_data.get("issue_date") if extra_payment_data and 'issue_date' in extra_payment_data else None
    if issue_date_str:
        if isinstance(issue_date_str, datetime.datetime):
            issue_date = issue_date_str
        else:
            try:
                issue_date = datetime.datetime.strptime(issue_date_str, '%Y-%m-%d')
            except Exception:
                issue_date = datetime.datetime.now()
    else:
        issue_date = datetime.datetime.now()
    
    try:
        invoice_line_items_data = []
        
        latest_reading_date = max(reading.reading_date for reading in readings if reading.contract == contract)
        contract_date = contract.registration_date if contract.registration_date else (contract.created_at.date() if contract.created_at else None)
        # Un canvi de nom que manté el mateix codi de contracte pot arrossegar
        # lectures (la de tall de la baixa) anteriors a la data d'alta del nou
        # Contract: en aquest cas no s'ha de bloquejar la generació.
        is_keep_same_code_carryover = bool(
            contract.contract_request_id
            and contract.contract_request.is_change_of_name
            and contract.contract_request.keep_same_code
        )
        # "Facturar període complert": s'ignoren les comprovacions de dates del contracte.
        if contract_date and latest_reading_date < contract_date and not is_keep_same_code_carryover and not contract.bill_full_period:
            print(f"[generate_consumption_invoice_multiple] FAILED: Latest reading date {latest_reading_date} is before contract registration date {contract_date}.")
            return None
        
        use_single_price_rate = contract.use_general_price_rates or contract.supply_points.count() == 1
        
        contract_pricerates = contract.price_rates.filter(price_rate__is_active=True).order_by('price_rate__product__position')

        group_by_supply_point = {}
        for price_rate in contract_pricerates:
            if price_rate.supply_point not in group_by_supply_point:
                group_by_supply_point[price_rate.supply_point] = []
            group_by_supply_point[price_rate.supply_point].append(price_rate.price_rate)

        for reading in readings:
            added_leak = get_added_leak(added_leak_by_reading, reading)
            reading_calculated_value = reading.calculated_value
            if reading_estimated.lower() == 'true':
                if reading.estimated_used and reading.estimated_used > 0:
                    reading_calculated_value = float(reading_calculated_value) - float(reading.estimated_used)
            real_consumption = float(real_consumption) + float(reading_calculated_value) if reading_calculated_value > 0 else float(real_consumption)

            # Evitem duplicar si la lectura de tancament ja està en la llista a facturar
            close_prev = get_close_previous_reading(reading)
            if close_prev and close_prev not in readings:
                real_consumption = float(real_consumption) + float(close_prev.real_consumption) if close_prev.real_consumption > 0 else float(real_consumption)
                if added_leak == 0:
                    added_leak += get_leak_value(close_prev)
            close_prev_prev = get_close_previous_previous_reading(reading)
            if close_prev_prev and close_prev_prev not in readings:
                real_consumption = float(real_consumption) + float(close_prev_prev.real_consumption) if close_prev_prev.real_consumption > 0 else float(real_consumption)
                if added_leak == 0:
                    added_leak += get_leak_value(close_prev_prev)
            leak_reading = None
            if reading.leak_value and float(reading.leak_value) > 0:
                leak_reading = float(reading.leak_value)
                total_leak += leak_reading
            total_leak = float(total_leak) + float(added_leak) if total_leak else float(added_leak)
            leak_reading = leak_reading + float(added_leak) if leak_reading else float(added_leak) if added_leak > 0 else None
            reading_supply_point = reading.supply_point
            price_rates = group_by_supply_point.get(reading_supply_point, [])
            if not price_rates or use_single_price_rate:
                # Fallback to rates with no specific supply point or if use_single_price_rate is True
                global_rates = group_by_supply_point.get(None, [])
                for gr in global_rates:
                    if gr not in price_rates:
                        price_rates.append(gr)
            
            # print("price_rates: ", len(price_rates))
            
            for price_rate in price_rates:
                # COMMENTED UNTIL USED, COMPARE RESULTS AND CHECK EVERYTHING IS OK ?¿?¿?
                if use_single_price_rate and not reading.meter.is_general:
                    consumption_total = float(consumption_og) - float(estimated_used_og)
                else:
                    # Passar la llista per evitar dobles sumes del consum de lectures de tancament
                    consumption_total, added_leak_by_reading = recalc_consumption_gen_meter(
                        reading, real_consumption, reading.supply_point, added_leak_by_reading, readings
                    )
                    reading.real_consumption = consumption_total
                    # reading.save()
                
                # consumption_total = int(recalc_consumption_gen_meter(reading, real_consumption, reading.supply_point))
                price_rate_billing_ranges = BillingRange.objects.filter(price_rate=price_rate)
                
                billing_range = price_rate_billing_ranges.filter(start__lte=reading.reading_date).filter(Q(end__gt=reading.reading_date) | Q(end__isnull=True)).order_by('-start').first()
                if not billing_range:
                    # Forat entre l'end d'un rang i el start del seguent: agafem el proper rang futur.
                    billing_range = price_rate_billing_ranges.filter(start__gt=reading.reading_date).order_by('start').first()

                prev_reading = Reading.objects.filter(
                    supply_point=reading_supply_point,
                    meter=reading.meter,
                    reading_date__lt=reading.reading_date,
                    contract=reading.contract,
                    is_control=False
                ).exclude(id=reading.id).order_by('-reading_date').first()
                if prev_reading is None:
                    prev_reading = Reading.objects.filter(
                        supply_point=reading_supply_point,
                        meter=reading.meter,
                        reading_date__lt=reading.reading_date,
                        is_control=False
                    ).exclude(id=reading.id).order_by('-reading_date').first()

                prev_reading_date = prev_reading.reading_date if prev_reading else None

                # Fix for meter changes: ensure we go back to the very first reading of the period
                actual_pr = prev_reading
                close_prev = get_close_previous_reading(actual_pr) if actual_pr else None
                if close_prev:
                    actual_pr = close_prev
                while actual_pr and actual_pr.is_close and not reading_has_blocking_invoices(actual_pr):
                    actual_pr = actual_pr.previous_reading
                if actual_pr:
                    prev_reading_date = actual_pr.reading_date
                
                billing_range = price_rate.billing_range_active if billing_range is None else billing_range
                
                prev_billing_range = None
                change_date = None
                
                if not billing_range:
                    continue
                
                if not prev_reading_date and not prev_reading:
                    prev_reading_date = reading.previous_reading.reading_date if reading.previous_reading and reading.contract == reading.previous_reading.contract else None
                    
                    # Fix for meter changes: go back through sequential close readings to find the original start date
                    close_prev = get_close_previous_reading(reading, same_contract=True)
                    if close_prev:
                        prev_reading_date = close_prev.previous_reading.reading_date if close_prev.previous_reading else prev_reading_date
                    
                    close_prev_prev = get_close_previous_previous_reading(reading, same_contract=True)
                    if close_prev_prev:
                        prev_reading_date = close_prev_prev.previous_reading.reading_date if close_prev_prev.previous_reading else prev_reading_date

                from_contract = False
                
                if not prev_reading_date and contract and (contract.registration_date or contract.created_at):
                    from_contract = True
                    prev_reading_date = contract.registration_date if contract.registration_date else contract.created_at.date()
                
                if not consumption_days:
                    if previous_reading_date:
                        consumption_days = (current_reading_date - previous_reading_date).days
                        close_prev = get_close_previous_reading(readings[0])
                        if close_prev:
                            consumption_days += close_prev.consumption_days or 0
                        close_prev_prev = get_close_previous_previous_reading(readings[0])
                        if close_prev_prev:
                            consumption_days += close_prev_prev.consumption_days or 0
                    elif prev_reading_date and from_contract:
                        consumption_days = (current_reading_date - prev_reading_date).days
                        
                if prev_reading_date and reading.previous_reading:
                    if billing_range.start <= reading.reading_date and billing_range.start > prev_reading_date:
                        try:
                            prev_billing_range = price_rate_billing_ranges.filter(start__lte=reading.reading_date).exclude(id=billing_range.id).order_by('-start').first()
                        except BillingRange.DoesNotExist:
                            prev_billing_range = None
                        # Nomes apliquem el tram anterior si realment cobreix la data d'inici
                        # de l'interval facturat (end exclusiu, com a la resta de filtres de BillingRange).
                        if prev_billing_range and prev_billing_range.end and prev_reading_date < prev_billing_range.end:
                            change_date = billing_range.start
                        else:
                            prev_billing_range = None
                elif prev_reading_date and from_contract:
                    if billing_range.start <= reading.reading_date and billing_range.start > prev_reading_date:
                        try:
                            prev_billing_range = price_rate_billing_ranges.filter(start__lte=reading.reading_date).exclude(id=billing_range.id).order_by('-start').first()
                        except BillingRange.DoesNotExist:
                            prev_billing_range = None
                        if prev_billing_range and prev_billing_range.end and prev_reading_date < prev_billing_range.end:
                            change_date = billing_range.start
                        else:
                            prev_billing_range = None

                line_item_types = billing_range.line_item_types.filter(is_active=True)
                if prev_billing_range:
                    line_item_types = line_item_types.union(prev_billing_range.line_item_types.filter(is_active=True))
                # print("line_item_types: ", len(line_item_types))
                if( not line_item_types ):
                    # raise Exception(f"Billing range {billing_range} doesn't have line item types")
                    # print(f"Billing range {billing_range} doesn't have line item types")
                    continue

                sorted_lit = sorted(line_item_types, key=lambda l: (l.billing_range.start if l.billing_range else date.min, l.name))
                for lit in sorted_lit:
                    line_items = create_from_lineitemtype(contract, lit, reading, consumption_total, consumption_days, invoice_line_items_data, change_date=change_date, leak_reading=leak_reading, billing_correction=period_days, prev_date=prev_reading_date, period_months=period_months)
                    if line_items:
                        for line_item in line_items:
                            # print(f"Line item: {line_item}")
                            if line_item:
                                invoice_line_items_data.append(line_item)
                
                # Ens guardem l'exploitation per a la factura
                if not exploitation and price_rate.product.exploitation:
                    exploitation = price_rate.product.exploitation
        # print("contract: "+contract.token)
        
        ordered_invoice_line_items_data = sorted(
            invoice_line_items_data,
            key=lambda x: (
                x['line_item_type'].billing_range.price_rate.product.position if (x.get('line_item_type') and x['line_item_type'].billing_range and x['line_item_type'].billing_range.price_rate and x['line_item_type'].billing_range.price_rate.product and x['line_item_type'].billing_range.price_rate.product.position ) else 0,
                x['line_item_type'].billing_range.start if (x.get('line_item_type') and x['line_item_type'].billing_range and x['line_item_type'].billing_range.start) else date.min,
                x['name']
            )
        )

    except Exception as e:
        print(f"Error creating line items: {e}")
        raise Exception("Error creating line items")
    
    number = generate_invoice_id()
    # print(f"Creating invoice {number}")
    try:
        payment_type_instance = None
        payment_company_bank_instance = None
        payment_bank_instance = None
        accounting_office_final = None
        managing_body_final = None
        processing_unit_final = None
        command_final = None
        record_final = None
        
        contract_base = contract
        if contract_base.payment:
            payment_type_instance = contract_base.payment.type if contract_base.payment.type else None
            payment_bank_instance = contract_base.payment.IBAN if contract_base.payment.IBAN else None
            payment_company_bank_instance = contract_base.payment.company_iban if contract_base.payment.company_iban else None
            accounting_office_final = contract_base.payment.accounting_office if contract_base.payment and contract_base.payment.accounting_office else None
            managing_body_final = contract_base.payment.managing_body if contract_base.payment and contract_base.payment.managing_body else None
            processing_unit_final = contract_base.payment.processing_unit if contract_base.payment and contract_base.payment.processing_unit else None
            command_final = contract_base.payment.command if contract_base.payment and contract_base.payment.command else None
            record_final = contract_base.payment.record if contract_base.payment and contract_base.payment.record else None
        
        #total_invoices = Invoice.objects.filter(issue_date__year=year, serie=serie).count()
        
        if contract_base.general_invoice:
            address = contract_base.general_invoice.address_billing.address if contract_base.general_invoice.address_billing and contract_base.general_invoice.address_billing.address else None
        else:
            address = contract_base.address_billing.address if contract_base.address_billing and contract_base.address_billing.address else None
        origin = get_origin_reading()
        invoice_type = get_invoice_type_invoice()
        if is_budget:
            invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token='invoice_type_budget_token').value)
        status = get_invoice_pending_status()
        invoice_class = get_invoice_class()
        serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)
        
        from uuid import uuid4
        serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
        
        if contract_base.general_invoice:
            if contract_base.general_invoice.payment and contract_base.general_invoice.payment.IBAN and contract_base.general_invoice.payment.IBAN.person:
                payer_final = f"{contract_base.general_invoice.payment.IBAN.person.name} {contract_base.general_invoice.payment.IBAN.person.surname}" if contract_base.general_invoice.payment.IBAN.person.surname else contract_base.general_invoice.payment.IBAN.person.name
                payer_token_final = contract_base.general_invoice.payment.IBAN.person.token
            else:
                payer_final = f"{contract_base.holder.name} {contract_base.holder.surname}" if contract_base.holder.surname else contract_base.holder.name
                payer_token_final = contract_base.holder.token
        else:
            if contract_base.payment and contract_base.payment.IBAN and contract_base.payment.IBAN:
                payer_final = f"{contract_base.payment.IBAN.name}"
                payer_token_final = contract_base.payment.IBAN.dni
            else:
                payer_final = f"{contract_base.holder.name} {contract_base.holder.surname}" if contract_base.holder.surname else contract_base.holder.name
                payer_token_final = contract_base.holder.token
        person = contract_base.holder
        if new_holder_instance:
            person = new_holder_instance
        if extra_payment_data:
            payment_type_instance = PaymentType.objects.get(id = extra_payment_data.get("type_id")) if extra_payment_data.get("type_id") else None
            payment_bank_instance = PersonBank.objects.get(id = extra_payment_data.get("IBAN")) if extra_payment_data.get("IBAN") else None
            payment_company_bank_instance = CompanyBank.objects.get(id = extra_payment_data.get("company_iban")) if extra_payment_data.get("company_iban") else None
            electronic_data = extra_payment_data.get('electronic_data', None)
            if payment_bank_instance:
                payer_final = f"{payment_bank_instance.name}"
                payer_token_final = payment_bank_instance.dni
            if electronic_data:
                accounting_office_final = electronic_data.get('accounting_office')
                managing_body_final = electronic_data.get('managing_body')
                processing_unit_final = electronic_data.get('processing_unit')
                command_final = electronic_data.get('command')
                record_final = electronic_data.get('record')
        if not exploitation and contract_base.supply_point_default and contract_base.supply_point_default.connection and contract_base.supply_point_default.connection.exploitation:
            exploitation = contract_base.supply_point_default.connection.exploitation
        
        # Link all readings that contributed to the consumption (including close readings from meter changes)
        final_readings = list(readings)
        for r in readings:
            close_prev = get_close_previous_reading(r, same_contract=True)
            if close_prev and close_prev not in final_readings:
                final_readings.append(close_prev)

            close_prev_prev = get_close_previous_previous_reading(r, same_contract=True)
            if close_prev_prev and close_prev_prev not in final_readings:
                final_readings.append(close_prev_prev)

        
        data = {
            'token': number,
            'number': number,
            'contract': contract_base,
            'used_aca': contract_base.use_aca,
            'issue_date': billing_batch.issue_date if billing_batch and billing_batch.issue_date else issue_date.date(),
            'due_date': billing_batch.due_date if billing_batch and billing_batch.due_date else None,
            'send_at': billing_batch.send_at if billing_batch and billing_batch.send_at else None,
            'title_final': title if title else f"{invoice_type.name.upper()} {contract_base.token}",
            'batch': billing_batch if billing_batch else None,
            'billing': billing if billing else None,
            'billing_period_days': period_days,
            'billing_period_month': extra_payment_data.get("period_month") if extra_payment_data and 'period_month' in extra_payment_data else issue_date.month,
            'billing_period_year': extra_payment_data.get("period_year") if extra_payment_data and 'period_year' in extra_payment_data else issue_date.year,
            'exploitation': exploitation,
            'company': contract_base.company if contract_base.company else exploitation.company if exploitation else None,
            'customer_final': f"{person.name} {person.surname if person.surname else ''}",
            'customer_token_final': person.token,
            'person': person,
            'payer_final': payer_final,
            'payer_token_final': payer_token_final,
            'customer_tlf_final': contract_base.person_contact_sms.first().phone if contract_base.person_contact_sms.count() > 0 else None,
            'customer_email_final': contract_base.person_contact_email.email if contract_base.person_contact_email else None,
            "country_final": address.country.iso_code if address else "-",
            "customer_is_juridic": contract_base.holder.is_juridic,
            'address_final': get_address_complete_without_city(address) if address else "-",
            'postal_code_final': address.postal_code if address else None,
            'city_final': address.city.name if address else None,
            'province_final': address.province.name if address else None,
            'location_final': f"{address.postal_code} {address.city}, {address.province} - {address.country}" if address else "-",
            'payment_type': payment_type_instance,
            'payment_type_final': payment_type_instance.name if payment_type_instance else "-",
            'payment_type_token_final': payment_type_instance.token if payment_type_instance else "-",
            'payment_bank': payment_bank_instance,
            'payment_company_bank': payment_company_bank_instance,
            'payment_bank_final': payment_company_bank_instance.iban if payment_company_bank_instance else (payment_bank_instance.iban if payment_bank_instance else None),
            'payment_swift_final': payment_company_bank_instance.swift if payment_company_bank_instance else (payment_bank_instance.swift if payment_bank_instance else None),
            'accounting_office_final': accounting_office_final,
            'managing_body_final': managing_body_final,
            'processing_unit_final': processing_unit_final,
            'command_final': command_final,
            'record_final': record_final,
            'origin': origin,
            'consumption': consumption,
            'consumption_days': consumption_days,
            "is_confirmed": True,
            "type": invoice_type,
            'type_final': invoice_type.token if invoice_type else None,
            "status": status,
            'responsible_consumption': consumption_responsible,
            'persons_final': contract_base.total_persons if contract_base.total_persons > 0 else 3,
            'serie': serie,
            'serie_final': serie_final_provisional,
            'serie_token_final': serie.token,
            'invoice_class': invoice_class,
            'invoice_class_token_final': invoice_class.token,
            'simplified': True if simplified else False,
            'is_general': True if contract_base.general_invoice else False,
            'refactored_token': refactor_invoice,
            'real_consumption': sum([float(reading.calculated_value) - float(reading.estimated_used) if reading.estimated_used else float(reading.calculated_value) for reading in final_readings]),
        }
        
        if not ordered_invoice_line_items_data or len(ordered_invoice_line_items_data) == 0:
            print("[generate_consumption_invoice_multiple] FAILED: No line items were generated.")
            return None

        invoice = Invoice.objects.create(**data)
        
        # =====================================================================
        # NO TOQUIS AQUESTA LINIA -- avis per a programadors I per a IA (Claude)
        # =====================================================================
        # Aqui s'ha de vincular `readings`. MAI `final_readings`.
        #
        # `final_readings` (calculat just aqui a dalt) hi afegeix les lectures de
        # tancament arrossegades (canvi de comptador, lectura de tall d'una baixa)
        # que NO formen part d'aquesta factura: nomes se n'aprofiten alguns valors
        # per calcular el consum, i el seu estat de facturacio ja el gestiona una
        # altra part del codi. Si es vinculen aqui, la facturacio surt malament.
        #
        # Aquesta linia ja ha anat i tornat tres vegades:
        #   425ea687  final_readings -> readings
        #   482f349a  readings -> final_readings  (semblava un fix, no ho era)
        #   5cf187a9  revertit a readings         (l'estat correcte, l'actual)
        #
        # Per tant: si et sembla un bug, o veus `final_readings` com una variable
        # morta que "algu es va deixar", NO es un descuit -- es intencionat. Es calcula
        # perque el bucle de mes amunt hi arrossega les lectures de tancament, pero el
        # que es vincula a la factura son nomes les `readings`.
        # Cap canvi aqui sense validar-lo abans amb en Guillem.
        invoice.readings.set(readings)

        # Control de seguretat del paragraf anterior: si algun canvi futur fa que la
        # factura acabi amb lectures que no son exactament `readings`, avisa fort.
        if set(invoice.readings.values_list('id', flat=True)) != {r.id for r in readings}:
            print("[generate_consumption_invoice_multiple] AVIS GREU: les lectures "
                  f"vinculades a la factura {invoice.id} no coincideixen amb `readings`. "
                  "Aixo trenca la facturacio: repassa el comentari 'NO TOQUIS AQUESTA "
                  "LINIA' de invoice_service.py.")

        k = 0
        for line_item_data in ordered_invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{invoice.number}-{k}"
            line_item_data['invoice'] = invoice
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            if adjustments:
                for adjustment in adjustments:
                    new_adjustment = AppliedAdjustment.objects.create(**adjustment)
                    line_item.adjustments.add(new_adjustment)
            # print(f"line item created: {line_item.id}")

        subtotal, taxes, taxes_base, total = get_totals(invoice)
        total_paid = check_piggy_bank(invoice, total)
        if is_budget and generate_budget_serie_final:
            serie_final = generate_budget_serie_final(serie, invoice)
        else:
            serie_final = f"{serie.token}/{invoice.id}" if serie else None
        invoice.serie_final = serie_final
        invoice.subtotal_final = subtotal
        invoice.total_final = total
        invoice.left_to_pay = float(total) - float(total_paid)
        invoice.save()
        print(f"Invoice created serie_final={invoice.serie_final} total={invoice.total_final}")
        
        confirm_invoice(invoice)
        # check_readings_values(readings, invoice, contract_base)
        
    except Exception as e:
        raise Exception("Error creating invoice")
    return invoice

def invoice_contract_generate(user, contract_request_id, title, payment_type, payment_bank, is_return=False, invoice_id=None, electronic_invoice_data=None, is_budget=False, company_bank=None, company_id=None, category_id=None, new_holder=None):
    # print("creating invoice from contract")
    # print(invoice_type_token)
    try:
        if is_return:
            contract = Contract.objects.get(id=contract_request_id)
        else:
            contract = ContractRequest.objects.get(id=contract_request_id)
        if not contract:
            raise Exception("Contract not found")
        
        pass  # log removed
        pass  # log removed
        
        price_rates = contract.registration_price_rates.filter(is_active=True).order_by('product__position')
        if is_return:
            origin_contract_token = ConfigProject.objects.get(token='origin_contract_token').value
            price_rates = price_rates.filter(product__origin__token=origin_contract_token)
        
        new_holder_instance = None
        if new_holder:
            try:
                new_holder_instance = Person.objects.get(id=new_holder)
            except:
                pass
        
        # bill_cut_reading support removed from registration invoice to separate consumption
        # if not is_return and hasattr(contract, 'bill_cut_reading') and contract.bill_cut_reading:
        #     # Add general price rates for consumption
        #     general_price_rates = contract.price_rates.filter(price_rate__is_active=True).order_by('price_rate__product__position')
        #     # Extract just the PriceRate models
        #     price_rates_list = list(price_rates)
        #     for pr in general_price_rates:
        #         if pr.price_rate not in price_rates_list:
        #             price_rates_list.append(pr.price_rate)
        #     price_rates = price_rates_list
        
        exploitation = None
        try:
            exploitation = contract.supply_point_default.connection.exploitation
        except:
            exploitation = None
            
        invoice_line_items_data = []
        
        try:
            from billing.models import Reading
            # reading = Reading.objects.filter(contract_request=contract, is_active=True).exclude(is_control=True).order_by('-reading_date').first()
            # reading is always empty when is_initial, it should filter another reading in case of this
            reading = None
            
            for price_rate in price_rates:
                billing_range = price_rate.billing_range_active
                if not billing_range:
                    continue
                
                line_item_types = billing_range.line_item_types.all()
                
                consumption_total = None
                consumption_days = None
                if reading and price_rate.product.billing_inactive: # Only for consumption products
                    consumption_total = reading.calculated_value
                    consumption_days = reading.consumption_days
                
                for lit in line_item_types:
                    line_items = create_from_lineitemtype(contract, lit, reading, consumption_total, consumption_days, invoice_line_items_data)
                    if line_items:
                        for line_item in line_items:
                            invoice_line_items_data.append(line_item)
                
                if not exploitation and price_rate.product.exploitation:
                    exploitation = price_rate.product.exploitation
        except Exception as e:
            pass  # log removed
            raise Exception("Error creating line items")
            
        
        number = generate_invoice_id()
        # print(f"Creating invoice {number}")

        invoice = None
        
        if invoice_id is None:
            # year = datetime.datetime.now().year
            payment_type_instance = PaymentType.objects.get(id = payment_type)
            payment_bank_instance = PersonBank.objects.get(id = payment_bank) if payment_bank else (contract.payment.IBAN if contract.payment and contract.payment.IBAN else None)
            payment_company_bank_instance = CompanyBank.objects.get(id = company_bank) if company_bank else (contract.payment.company_iban if contract.payment and contract.payment.company_iban else None)
            invoice_type_token = 'invoice_type_invoice_token' if not is_budget else 'invoice_type_budget_token'
            
            is_invoice = invoice_type_token == ConfigProject.objects.get(token='invoice_type_invoice_token').value
            invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token=invoice_type_token).value)
            invoice_class = InvoiceClass.objects.get(token='OO') 
            origin = ProductOrigin.objects.get(token=ConfigProject.objects.get(token='origin_contract_token').value)
            status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_pending_token').value)
            
            serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)
            
            from uuid import uuid4
            serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
            
            address_billing = contract.address_billing if contract.address_billing and contract.address_billing.address else None
            person = contract.holder
            if new_holder_instance:
                person = new_holder_instance
            
            if payment_bank_instance:
                payer_final = f"{payment_bank_instance.name}"
                payer_token_final = payment_bank_instance.dni
            elif contract.payment and contract.payment.IBAN:
                payer_final = f"{contract.payment.IBAN.name}"
                payer_token_final = contract.payment.IBAN.dni
            else:
                payer_final = f"{person.name} {person.surname}" if person.surname else person.name
                payer_token_final = person.token
            
            default_company = contract.company if contract.company else exploitation.company if exploitation else None
            selected_company = resolve_selected_company(exploitation, default_company, company_id)
            selected_category = resolve_selected_category(category_id)

            data = {
                'token': number,
                'number': number,
                'company': selected_company,
                'category': selected_category,
                'exploitation': exploitation if exploitation else None,
                'issue_date': datetime.datetime.now().date(),
                'title_final': f'{invoice_type.name.upper()} {title}',
                'customer_final': f"{person.name} {person.surname if person.surname else ''}",
                'customer_token_final': person.token,
                'person': person,
                'payer_final': payer_final,
                'payer_token_final': payer_token_final,
                "customer_is_juridic": person.is_juridic,
                'customer_tlf_final': contract.person_contact_sms.first().phone if contract.person_contact_sms.count() > 0 else None,
                'customer_email_final': contract.person_contact_email.email if contract.person_contact_email else None,
                'address_final': get_address_complete_without_city(address_billing.address) if address_billing else "-",
                'location_final': f"{address_billing.address.postal_code} {address_billing.address.city}, {address_billing.address.province} - {address_billing.address.country}" if address_billing else "-",
                'postal_code_final': address_billing.address.postal_code if address_billing else '-',
                'city_final': address_billing.address.city.name if address_billing else '-',
                'province_final': address_billing.address.province.name if address_billing else '-',
                "country_final": address_billing.address.country.iso_code if address_billing else '-',
                'payment_type': payment_type_instance,
                'payment_type_final': payment_type_instance.name,
                'payment_type_token_final': payment_type_instance.token if payment_type_instance else "-",
                'payment_bank': payment_bank_instance,
                'payment_company_bank': payment_company_bank_instance,
                'payment_bank_final': payment_company_bank_instance.iban if payment_company_bank_instance else (payment_bank_instance.iban if payment_bank_instance else None),
                'payment_swift_final': payment_company_bank_instance.swift if payment_company_bank_instance else (payment_bank_instance.swift if payment_bank_instance else None),
                'dir3_final': None,
                'accounting_office_final': electronic_invoice_data.get('accounting_office') if electronic_invoice_data and 'accounting_office' in electronic_invoice_data else None,
                'managing_body_final': electronic_invoice_data.get('managing_body') if electronic_invoice_data and 'managing_body' in electronic_invoice_data else None,
                'processing_unit_final': electronic_invoice_data.get('processing_unit') if electronic_invoice_data and 'processing_unit' in electronic_invoice_data else None,
                'command_final': electronic_invoice_data.get('command') if electronic_invoice_data and 'command' in electronic_invoice_data else None,
                'record_final': electronic_invoice_data.get('record') if electronic_invoice_data and 'record' in electronic_invoice_data else None,
                'exploitation': exploitation,
                'type': invoice_type,
                'type_final': invoice_type.token if invoice_type else None,
                'is_confirmed': is_invoice,
                'origin': origin,
                'status': status,
                'serie': serie,
                'serie_final': serie_final_provisional,
                'serie_token_final': serie.token,
                'invoice_class': invoice_class,
                'invoice_class_token_final': invoice_class.token
            }
            # print(f"Invoice data: {data}")
            invoice = Invoice.objects.create(**data)
        else:
            invoice = Invoice.objects.get(id=invoice_id)
        
        if is_return:
            invoice.contract = contract
        else:
            invoice.contract_request = contract
            # Si la sol·licitud ja s'ha finalitzat, el Contract definitiu ja
            # existeix i el pressupost/factura de l'alta s'hi ha de vincular
            # aquí: `contract_service.create_contract_from_request()` només
            # vincula (`Invoice...update(contract=contract)`) les factures que
            # ja existien en crear el contracte, i si l'alta es genera després
            # de finalitzar la sol·licitud es quedava amb `contract=NULL` per
            # sempre (no comptava al deute del contracte ni a impagats).
            if not invoice.contract:
                invoice.contract = Contract.objects.filter(contract_request=contract).first()
        
        k = 0
        for line_item_data in invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{invoice.number}-{k}"
            line_item_data['invoice'] = invoice
            if is_return:
                if 'price' in line_item_data and line_item_data['price'] is not None:
                    line_item_data['price'] = -abs(line_item_data['price'])
                if 'price_unit' in line_item_data and line_item_data['price_unit'] is not None:
                    line_item_data['price_unit'] = -abs(line_item_data['price_unit'])
                if 'total' in line_item_data and line_item_data['total'] is not None:
                    line_item_data['total'] = -abs(line_item_data['total'])
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            pass  # log removed
        
        if reading:
            invoice.readings.set([reading])

        subtotal, taxes, taxes_base, total = get_totals(invoice)
        
        if is_budget and generate_budget_serie_final:
            serie_final = generate_budget_serie_final(serie, invoice)
        else:
            serie_final = f"{serie.token}/{invoice.id}" if serie else f"{invoice.id}"
        invoice.serie_final = serie_final
        total_paid = check_piggy_bank(invoice, total)
        invoice.subtotal_final = -abs(subtotal) if is_return else subtotal
        invoice.total_final = -abs(total) if is_return else total
        invoice.left_to_pay = float(invoice.total_final) - float(total_paid)
        invoice.save()
        confirm_invoice(invoice)
    
    except Exception as e:
        pass  # log removed
        raise Exception("Error creating invoice")
    return invoice


def invoice_generate_return_bail(user, contract_request_id, title, payment_type, payment_bank, is_return=False, invoice_id=None, electronic_invoice_data=None, is_budget=False, company_bank=None):
    # print("creating invoice from contract")
    # print(invoice_type_token)
    try:
        contract = Contract.objects.get(id=contract_request_id)
        if not contract:
            raise Exception("Contract not found")
        
        
        unreturned_bail_token = ConfigProject.objects.get(token='bail_status_unreturned_token').value
        bails = Bail.objects.filter(contract=contract, is_active=True, status__token=unreturned_bail_token)
        if not bails:
            return None
        
        price_rates = []
        not_found_price_rates = []
        for bail in bails:
            if bail.price_rate:
                price_rates.append(bail.price_rate)
            else:
                not_found_price_rates.append(bail)
        
        exploitation = None
        invoice_line_items_data = []
        # Mateix criteri que la resta de fluxos: emet l'empresa del contracte. L'empresa
        # del producte de la fiança només és el recurs quan el contracte no en té.
        try:
            bail_price_rate = PriceRate.objects.filter(is_bail=True).first()
            default_company = bail_price_rate.product.company
        except:
            default_company = None
        if contract and contract.company:
            default_company = contract.company
        
        no_tax = tax_by_percent(0)
        if no_tax is None:
            raise Tax.DoesNotExist('No hi ha cap impost amb percentatge 0')
            
        try:
            line_item_types = None
            for price_rate in price_rates:
                billing_range = price_rate.billing_range_active
                if not billing_range:
                    raise Exception("No billing range found")
                line_item_types = billing_range.line_item_types.all()
                for lit in line_item_types:
                    line_items = create_from_lineitemtype(contract, lit, None, None, None, invoice_line_items_data)
                    if line_items:
                        for line_item in line_items:
                            invoice_line_items_data.append(line_item)
                
                if not exploitation and price_rate.product.exploitation:
                    exploitation = price_rate.product.exploitation
            for bail in not_found_price_rates:
                line_item_history = LineItemType.objects.get(token=ConfigProject.objects.get(token='history_line_item').value)
                # Constrain total to database field limits (max_digits=10, decimal_places=4)
                constrained_total = constrain_total_value(bail.amount)
                new_invoice_line_data = {
                    'token': line_item_history.token,
                    'company': default_company,
                    'line_item_type': line_item_history,
                    'price_rate_name': "FIANÇA",
                    'product_name': "FIANÇA",
                    'tax': no_tax,
                    'price': bail.amount,
                    'price_unit': bail.amount,
                    'units': 1,
                    'name': "FIANÇA",
                    'description': "FIANÇA",
                    'tax_percent': 0,
                    'tax_price': 0,
                    'total': constrained_total,
                }
                invoice_line_items_data.append(new_invoice_line_data)
                
        except Exception as e:
            pass  # log removed
            raise Exception("Error creating line items")
            
        if not exploitation:
            exploitation = contract.supply_point_default.connection.exploitation
        number = generate_invoice_id()
        # print(f"Creating invoice {number}")

        invoice = None
        
        if invoice_id is None:
            # year = datetime.datetime.now().year
            payment_type_instance = PaymentType.objects.get(id = payment_type)
            payment_bank_instance = PersonBank.objects.get(id = payment_bank) if payment_bank else (contract.payment.IBAN if contract.payment and contract.payment.IBAN else None)
            payment_company_bank_instance = CompanyBank.objects.get(id = company_bank) if company_bank else (contract.payment.company_iban if contract.payment and contract.payment.company_iban else None)
            invoice_type_token = 'invoice_type_invoice_token' if not is_budget else 'invoice_type_budget_token'
            
            is_invoice = invoice_type_token == ConfigProject.objects.get(token='invoice_type_invoice_token').value
            invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token=invoice_type_token).value)
            invoice_class = InvoiceClass.objects.get(token='OO') 
            origin = ProductOrigin.objects.get(token=ConfigProject.objects.get(token='origin_contract_token').value)
            status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_pending_token').value)
            
            serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)

            from uuid import uuid4
            serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
            address_billing = contract.address_billing if contract.address_billing and contract.address_billing.address else None
            
            if contract.payment and contract.payment.IBAN and contract.payment.IBAN:
                payer_final = f"{contract.payment.IBAN.name}"
                payer_token_final = contract.payment.IBAN.dni
            else:
                payer_final = f"{contract.holder.name} {contract.holder.surname}" if contract.holder.surname else contract.holder.name
                payer_token_final = contract.holder.token
            
            data = {
                'token': number,
                'number': number,
                'company': default_company if default_company else None,
                'issue_date': datetime.datetime.now().date(),
                'title_final': f'{invoice_type.name.upper()} {title}',
                'customer_final': f"{contract.holder.name} {contract.holder.surname}",
                'customer_token_final': contract.holder.token,
                'person': contract.holder,
                'payer_final': payer_final,
                'payer_token_final': payer_token_final,
                "customer_is_juridic": contract.holder.is_juridic,
                'customer_tlf_final': contract.person_contact_sms.first().phone if contract.person_contact_sms.count() > 0 else None,
                'customer_email_final': contract.person_contact_email.email if contract.person_contact_email else None,
                'address_final': get_address_complete_without_city(address_billing.address) if address_billing else "-",
                'location_final': f"{address_billing.address.postal_code} {address_billing.address.city}, {address_billing.address.province} - {address_billing.address.country}" if address_billing else "-",
                'postal_code_final': address_billing.address.postal_code if address_billing else "-",
                'city_final': address_billing.address.city.name if address_billing else "-",
                'province_final': address_billing.address.province.name if address_billing else "-",
                "country_final": address_billing.address.country.iso_code if address_billing else "-",
                'payment_type': payment_type_instance,
                'payment_type_final': payment_type_instance.name,
                'payment_type_token_final': payment_type_instance.token if payment_type_instance else "-",
                'payment_bank': payment_bank_instance,
                'payment_company_bank': payment_company_bank_instance,
                'payment_bank_final': payment_company_bank_instance.iban if payment_company_bank_instance else (payment_bank_instance.iban if payment_bank_instance else None),
                'payment_swift_final': payment_company_bank_instance.swift if payment_company_bank_instance else (payment_bank_instance.swift if payment_bank_instance else None),
                'dir3_final': None,
                'accounting_office_final': electronic_invoice_data.get('accounting_office') if electronic_invoice_data and 'accounting_office' in electronic_invoice_data else None,
                'managing_body_final': electronic_invoice_data.get('managing_body') if electronic_invoice_data and 'managing_body' in electronic_invoice_data else None,
                'processing_unit_final': electronic_invoice_data.get('processing_unit') if electronic_invoice_data and 'processing_unit' in electronic_invoice_data else None,
                'command_final': electronic_invoice_data.get('command') if electronic_invoice_data and 'command' in electronic_invoice_data else None,
                'record_final': electronic_invoice_data.get('record') if electronic_invoice_data and 'record' in electronic_invoice_data else None,
                'exploitation': exploitation,
                'type': invoice_type,
                'type_final': invoice_type.token if invoice_type else None,
                'is_confirmed': is_invoice,
                'origin': origin,
                'status': status,
                'serie': serie,
                'serie_final': serie_final_provisional,
                'serie_token_final': serie.token,
                'invoice_class': invoice_class,
                'invoice_class_token_final': invoice_class.token
            }
            # print(f"Invoice data: {data}")
            invoice = Invoice.objects.create(**data)
        else:
            invoice = Invoice.objects.get(id=invoice_id)
        
        if is_return:
            invoice.contract = contract
        else:
            invoice.contract_request = contract
        
        k = 0

        for line_item_data in invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{invoice.number}-{k}"
            line_item_data['invoice'] = invoice
            if is_return:
                if 'price' in line_item_data and line_item_data['price'] is not None:
                    line_item_data['price'] = -abs(line_item_data['price'])
                if 'price_unit' in line_item_data and line_item_data['price_unit'] is not None:
                    line_item_data['price_unit'] = -abs(line_item_data['price_unit'])
                if 'total' in line_item_data and line_item_data['total'] is not None:
                    line_item_data['total'] = -abs(line_item_data['total'])
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            pass  # log removed

        subtotal, taxes, taxes_base, total = get_totals(invoice)

        if is_budget and generate_budget_serie_final:
            serie_final = generate_budget_serie_final(serie, invoice)
        else:
            serie_final = f"{serie.token}/{invoice.id}" if serie else f"{invoice.id}"
        invoice.serie_final = serie_final

        invoice.subtotal_final = -abs(subtotal) if is_return else subtotal
        invoice.total_final = -abs(total) if is_return else total
        invoice.left_to_pay = -abs(total) if is_return else total
        invoice.save()
        
        confirm_invoice(invoice)
    
    except Exception as e:
        pass  # log removed
        raise Exception("Error creating invoice")
    return invoice

def invoice_return_charge(invoice, title, return_reason=None):
    try:
        origin_reading_token = ConfigProject.objects.get(token='origin_reading_token').value
        origin_contract_token = ConfigProject.objects.get(token='origin_contract_token').value
        #origin_other_token = ConfigProject.objects.get(token='origin_other_token').value
        
        contract = invoice.contract if invoice.contract else invoice.contract_request
        if invoice.origin.token == origin_reading_token:
            price_rates = contract.price_rates.filter(price_rate__is_active=True).order_by('price_rate__product__position')
        elif invoice.origin.token == origin_contract_token:
            price_rates = contract.registration_price_rates.filter(is_active=True).order_by('product__position')
        else:
            raise Exception("Origin not found")
        invoice_return_price_rate = PriceRate.objects.get(token=ConfigProject.objects.get(token='invoice_return_price_rate_token').value)
        pass  # log removed
        price_rates = [invoice_return_price_rate]
        
        exploitation = invoice.exploitation
        
        invoice_line_items_data = []
        try:
            line_item_types = None
            for price_rate in price_rates:
                billing_range = price_rate.billing_range_active
                if not billing_range:
                    continue
                line_item_types = billing_range.line_item_types.all()
                
                for lit in line_item_types:
                    # print(f"Line item type: {lit}")
                    line_items = create_from_lineitemtype(contract, lit, None,None,None,invoice_line_items_data, None, invoice)
                    # print("\n\ncreated line items")
                    # print(line_items)
                    if line_items:
                        for line_item in line_items:
                            invoice_line_items_data.append(line_item)
                
                if not exploitation and price_rate.product.exploitation:
                    exploitation = price_rate.product.exploitation
        except Exception as e:
            pass  # log removed
            raise Exception("Error creating line items")
        
        
        number = '02' + generate_invoice_id()
        # print(f"Creating invoice surcharge {number}")
        
        # year = datetime.datetime.now().year
        
        status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_pending_token').value)
        serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)
        
        from uuid import uuid4
        serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
        
        today = date.today()
        invoice_surcharge_days = ConfigProject.objects.get(token='invoice_surcharge_days').value
        issue_date = datetime.datetime.now().date()
        due_date = issue_date + datetime.timedelta(days=int(invoice_surcharge_days))
        
        origin = ProductOrigin.objects.get(token=ConfigProject.objects.get(token='origin_other_token').value)
        
        address_billing = contract.address_billing if contract.address_billing and contract.address_billing.address else None
        invoice_child = invoice
        child_found = False
        while not child_found :
            try:
                invoice_child = Invoice.objects.get(parent_invoice=invoice_child)
            except:
                invoice_child = invoice_child
                child_found = True
        
        data = {
            'token': '02' + invoice.token[-9:],
            'number': number,
            'issue_date': issue_date,
            'billing_period_month': invoice.billing_period_month,
            'billing_period_year': invoice.billing_period_year,
            'billing_period_days': invoice.billing_period_days,
            'due_date': due_date,
            'title_final': title if title else f"CÀRREC PER DEVOLUCIÓ {invoice.token}",
            'contract': invoice.contract,
            'used_aca': invoice.used_aca,
            'contract_request': invoice.contract_request,
            'customer_final': invoice.customer_final,
            'payer_final': invoice.payer_final,
            'payer_token_final': invoice.payer_token_final,
            "customer_is_juridic": invoice.customer_is_juridic,
            'customer_token_final': invoice.customer_token_final,
            'person': invoice.person,
            'customer_tlf_final': invoice.customer_tlf_final,
            'customer_email_final': invoice.customer_email_final,
            'address_final': invoice.address_final,
            'location_final': invoice.location_final,
            'postal_code_final': invoice.postal_code_final,
            'city_final': invoice.city_final,
            'province_final': invoice.province_final,
            "country_final": invoice.country_final,
            'payment_type': invoice.payment_type,
            'payment_type_final': invoice.payment_type_final,
            'payment_type_token_final': invoice.payment_type_token_final,
            'payment_bank': invoice.payment_bank,
            'payment_bank_final': invoice.payment_bank_final,
            'payment_swift_final': invoice.payment_swift_final,
            'exploitation': exploitation,
            'company': invoice.company if invoice.company else exploitation.company if exploitation else None,
            'type': invoice.type,
            'type_final': invoice.type_final,
            'is_confirmed': True,
            'origin': origin,
            'status': status,
            'serie': serie,
            'serie_final': serie_final_provisional,
            'serie_token_final': serie.token,
            'invoice_class': invoice.invoice_class,
            'invoice_class_token_final': invoice.invoice_class_token_final,
            'parent_invoice': invoice_child,
            'is_general': invoice.is_general,
            'reject': return_reason,
        }
        #print(f"Invoice data: {data}")
        surcharge = Invoice.objects.create(**data)
        surcharge.general_contracts.set(invoice.general_contracts.all())
        invoice.due_date = due_date
        invoice._skip_signal = True
        invoice.save()
        
        
        status_confirmed = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
        
        k = 0
        for line_item_data in invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{surcharge.number}-{k}"
            line_item_data['invoice'] = surcharge
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            # print(f"line item created: {line_item.id}")
            

        subtotal, taxes, taxes_base, total = get_totals(surcharge)
        serie_final = f"{serie.token}/{surcharge.id}" if serie else f"{surcharge.id}"
        surcharge.serie_final = serie_final
        surcharge.subtotal_final = subtotal
        surcharge.total_final = total
        surcharge.left_to_pay = total
        surcharge.status = status_confirmed
        surcharge.save()
        # Marca transitòria (no persistida) perquè generate_serie_final personalitzat
        # identifiqui aquesta factura com a recàrrec de retorn i assigni la categoria 0.
        surcharge._is_return_surcharge = True
        confirm_invoice(surcharge)
        
    except Exception as e:
        import traceback
        pass  # log removed
        traceback.print_exc()
        raise Exception(f"Error creating invoice surcharge: {e}")
    
    return surcharge


def invoice_connection_generate(user, connection_request_id, title, payment_type, payment_bank, company_bank, is_budget=False, electronic_invoice_data=None):
    # print("creating invoice from connection request")
    exploitation = None
    connection_request = None
    try:
        connection_request = ConnectionRequest.objects.get(id=connection_request_id)
        exploitation = connection_request.exploitation if connection_request.exploitation else None
    except ConnectionRequest.DoesNotExist:
        raise Exception("Connection request not found")
    try:
        product = Product.objects.get(token=ConfigProject.objects.get(token='product_connection_token').value)
        price_rates = product.price_rates.filter(is_active=True).order_by('product__position')
        invoice_line_items_data = []
        for price_rate in price_rates:
            # print(f"Price rate: {price_rate}")
            
            billing_range = price_rate.billing_range_active
            if not billing_range:
                # raise Exception(f"PriceRate {price_rate} doesn't have Billing range active")
                pass  # log removed
                continue
            
            line_item_types = billing_range.line_item_types.all()
            if( not line_item_types ):
                pass  # log removed
                continue

            for lit in line_item_types:
                # print(f"Line item type: {lit}")
                line_items = create_from_lineitemtype_connection(connection_request, lit, invoice_line_items_data)
                if line_items:
                    for line_item in line_items:
                        # print(f"Line item: {line_item}")
                        invoice_line_items_data.append(line_item)
            
            # Ens guardem l'exploitation per a la factura
            if not exploitation and price_rate.product.exploitation:
                exploitation = price_rate.product.exploitation

    except Exception as e:
        pass  # log removed
        raise Exception("Error creating line items")
    
    
    number = generate_invoice_id()
    try:
        # year = datetime.datetime.now().year
        
        origin = ProductOrigin.objects.get(token=ConfigProject.objects.get(token='origin_connection_token').value)
        invoice_type_token = 'invoice_type_invoice_token' if not is_budget else 'invoice_type_budget_token'
        invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token=invoice_type_token).value)
        status = InvoiceStatus.objects.get(is_default=True)
        
        payment_type_instance = PaymentType.objects.get(id = payment_type)
        payment_person_bank_instance = PersonBank.objects.get(id = payment_bank) if payment_bank else None
        payment_company_bank_instance = CompanyBank.objects.get(id = company_bank) if company_bank else None
        company = Company.objects.get(id=connection_request.company_id) if connection_request.company_id else None
        person = Person.objects.get(id=connection_request.person_id) if connection_request.person_id else None
        invoice_class = InvoiceClass.objects.get(token='OO') 
        if company:
            customer_final = f"{company.alias}"
            customer_token_final = company.vat
            payer_final = f"{company.alias}"
            payer_token_final = company.vat
            payment_bank_final = payment_company_bank_instance.iban if payment_company_bank_instance else None
            payment_swift_final = payment_company_bank_instance.swift if payment_company_bank_instance else None
            address = company.address if company else None
            phone_final = company.contact_phone if company.contact_phone else company.phone
            email_final = company.contact_email if company.contact_email else company.email
        elif person:
            customer_final = f"{person.name} {person.surname}" if person.surname else person.name
            customer_token_final = person.token
            payment_bank_final = payment_company_bank_instance.iban if payment_company_bank_instance else (payment_person_bank_instance.iban if payment_person_bank_instance else None)
            payer_final = payment_person_bank_instance.name if payment_person_bank_instance else customer_final
            payer_token_final = payment_person_bank_instance.dni if payment_person_bank_instance else customer_token_final
            payment_swift_final = payment_company_bank_instance.swift if payment_company_bank_instance else (payment_person_bank_instance.swift if payment_person_bank_instance else None)
            address = connection_request.address_billing.address if connection_request.address_billing else None
            person_contact = PersonContact.objects.filter(person=person, is_default=True).first()
            phone_final = person_contact.phone if person_contact else None
            email_final = person_contact.email if person_contact else None
        
        """ if validate_nif(customer_token_final):
            serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_ordinary_invoice_serie').value)
        else:
            serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_simplified_invoice_serie').value) """
        serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)
        from uuid import uuid4
        serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
        
        data = {
            'token': number,
            'number': number,
            'connection_request': connection_request,
            'issue_date': datetime.datetime.now().date(),
            'title_final': f'{invoice_type.name.upper()} {title}',
            'exploitation': exploitation,
            'company': exploitation.company,
            'customer_final': customer_final,
            'customer_token_final': customer_token_final,
            'person': person,
            'payer_final': payer_final,
            'payer_token_final': payer_token_final,
            "customer_is_juridic": True if company or person.is_juridic else False,
            'customer_tlf_final': phone_final,
            'customer_email_final': email_final,
            'address_final': get_address_complete_without_city(address) if address else "-",
            'location_final': f"{address.postal_code} {address.city}, {address.province} - {address.country}" if address else "-",
            'postal_code_final': address.postal_code if address else None,
            'city_final': address.city.name if address else None,
            'province_final': address.province.name if address else None,
            "country_final": address.country.iso_code,
            'payment_type': payment_type_instance,
            'payment_type_final': payment_type_instance.name if payment_type_instance else "-",
            'payment_type_token_final': payment_type_instance.token if payment_type_instance else "-",
            'payment_bank': payment_person_bank_instance,
            'payment_company_bank': payment_company_bank_instance,
            'payment_bank_final': payment_bank_final,   
            'payment_swift_final': payment_swift_final,
            'dir3_final': None,
            'accounting_office_final': connection_request.payment.accounting_office if connection_request.payment.accounting_office else None,
            'managing_body_final': connection_request.payment.managing_body if connection_request.payment.managing_body else None,
            'processing_unit_final': connection_request.payment.processing_unit if connection_request.payment.processing_unit else None,
            'command_final': connection_request.payment.command if connection_request.payment.command else None,
            'record_final': connection_request.payment.record if connection_request.payment.record else None,
            'origin': origin,   
            "is_confirmed": True,
            "type": invoice_type,
            'type_final': invoice_type.token if invoice_type else None,
            "status": status,
            'serie': serie,
            'serie_final': serie_final_provisional,
            'serie_token_final': serie.token,
            'invoice_class': invoice_class,
            'invoice_class_token_final': invoice_class.token
        }

        invoice = Invoice.objects.create(**data)
        # print(f"invoice created: {invoice.id}")

        k = 0
        for line_item_data in invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{invoice.number}-{k}"
            line_item_data['invoice'] = invoice
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            # print(f"line item created: {line_item.id}")
            

        subtotal, taxes, taxes_base, total = get_totals(invoice)

        serie_final = f"{serie.token}/{invoice.id}" if serie else f"{invoice.id}"
        invoice.serie_final = serie_final
        invoice.subtotal_final = subtotal   
        invoice.total_final = total
        invoice.left_to_pay = total
        invoice.save()
        confirm_invoice(invoice)
    except Exception as e:
        pass  # log removed
        raise Exception("Error creating invoice")

    return invoice

def return_invoice(invoice, payment_type_id):
    from billing.signals import check_paid_invoice, create_payment_invoice
    post_save.disconnect(check_paid_invoice, Invoice)
    post_save.disconnect(create_payment_invoice, Invoice)
    # payment_status_cancelled = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_cancelled_token').value)
    # status_cancelled = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_cancelled_token').value)
    status_confirmed = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
    status_payoff = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_payoff_token').value)
    invoice_class = InvoiceClass.objects.get(token=ConfigProject.objects.get(token='invoice_class_or').value)
    serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_returned_invoice_serie').value)
    from uuid import uuid4
    serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
    #payment_type = PaymentType.objects.get(id=payment_type_id)
    today = datetime.datetime.now().date()
    
    data = {
            'token': generate_invoice_id(),
            'number': invoice.number,
            'contract': invoice.contract,
            'used_aca': invoice.used_aca,
            'contract_request': invoice.contract_request,
            'contract_termination': invoice.contract_termination,
            'connection': invoice.connection,
            'connection_request': invoice.connection_request,
            'issue_date': today,
            'title_final': f"{_('Abonament')} {invoice.title_final}",
            'exploitation': invoice.exploitation,
            'company': invoice.company,
            'customer_final': invoice.customer_final,
            'customer_token_final': invoice.customer_token_final,
            'person': invoice.person,
            'payer_final': invoice.payer_final,
            'payer_token_final': invoice.payer_token_final,
            "customer_is_juridic": invoice.customer_is_juridic,
            'customer_tlf_final': invoice.customer_tlf_final,
            'customer_email_final': invoice.customer_email_final,
            'address_final': invoice.address_final,
            'location_final': invoice.location_final,
            'postal_code_final': invoice.postal_code_final,
            'city_final': invoice.city_final,
            'province_final': invoice.province_final,
            "country_final": invoice.country_final,
            'payment_type': None,
            'payment_type_final': _("Sense pagament configurat"),
            'payment_type_token_final': _("Sense pagament configurat"),
            'payment_bank': None,
            'payment_company_bank': None,
            'payment_bank_final': None,
            'payment_swift_final': None,
            'dir3_final': None,
            'accounting_office_final': invoice.accounting_office_final,
            'managing_body_final': invoice.managing_body_final,
            'processing_unit_final': invoice.processing_unit_final,
            'command_final': invoice.command_final,
            'record_final': invoice.record_final,
            'origin': invoice.origin,
            "is_confirmed": invoice.is_confirmed,
            "simplified": invoice.simplified,
            "manually_modified": invoice.manually_modified,
            "consumption": invoice.consumption,
            "consumption_days": invoice.consumption_days,
            "responsible_consumption": invoice.responsible_consumption,
            "persons_final": invoice.persons_final,
            "type": invoice.type,
            "type_final": invoice.type_final,
            "status": invoice.status,
            'serie': serie,
            'serie_final': serie_final_provisional,
            'serie_token_final': invoice.serie_token_final,
            'invoice_class': invoice_class,
            'invoice_class_token_final': invoice_class.token,
            'subtotal_final': -invoice.subtotal_final,
            'total_final': -invoice.total_final,
            'total_final': -invoice.total_final,
            'budget_token': invoice.budget_token,
            'is_suppressed': True,
            'real_consumption': invoice.real_consumption,
        }
    
    new_invoice = Invoice.objects.create(**data)
    new_invoice.readings.set(invoice.readings.all())
    new_invoice.save()
    """ invoice_payments = Payment.objects.filter(invoice=invoice)
    for invoice_payment in invoice_payments:
        invoice_payment.status = payment_status_cancelled
        invoice_payment.save() """
    invoice.return_token = new_invoice.token
    invoice.save()
    invoice_lines = InvoiceLineItem.objects.filter(invoice=invoice, is_active=True)
    k=0
    for invoice_line in invoice_lines:
        k += 1
        # Filter out Django internal attributes like _state
        """ line_item_data = {k: v for k, v in invoice_line.__dict__.items() if not k.startswith('_')}
        line_item_data['id'] = None
        line_item_data['pk'] = None
        line_item_data['invoice'] = new_invoice
        line_item_data['token'] = f"{new_invoice.number}-{k}"
        line_item_data['units'] = -invoice_line.units
        line_item_data['price'] = -invoice_line.price """
        # Constrain total to database field limits (max_digits=10, decimal_places=4)
        constrained_total = constrain_total_value(-invoice_line.total if invoice_line.total else 0)
        line_item_data = {
            'token': f"{new_invoice.number}-{k}",
            'company': invoice_line.company,
            'invoice': new_invoice,
            'reading': invoice_line.reading,
            'line_item_type': invoice_line.line_item_type,
            'price_rate': invoice_line.price_rate,
            'price_rate_name': invoice_line.price_rate_name,
            'product': invoice_line.product,
            'product_name': invoice_line.product_name,
            'tax': invoice_line.tax,
            'price': -invoice_line.price,
            'price_unit': invoice_line.price_unit,
            'units': -invoice_line.units,
            'name': invoice_line.name,
            'description': invoice_line.description,
            'tax_percent': invoice_line.tax_percent,
            'tax_price': -invoice_line.tax_price if invoice_line.tax_price is not None else None,
            'total': constrained_total,
            'interval': invoice_line.interval,
            'end_stretch': invoice_line.end_stretch,
            'contract': invoice_line.contract,
        }
        line_item = InvoiceLineItem.objects.create(**line_item_data)
        line_item.adjustments.set(invoice_line.adjustments.all())
    post_save.connect(create_payment_invoice, Invoice)
    serie_final = f"{serie.token}/{new_invoice.id}" if serie else f"{new_invoice.id}"
    new_invoice.serie_final = serie_final
    new_invoice.status = status_payoff
    new_invoice.left_to_pay = new_invoice.total_final
    new_invoice.save()
    confirm_invoice(new_invoice)
    
    return new_invoice

def recalc_consumption_gen_meter(reading, consumption_og, supply_point_instance, added_leak_by_reading = None, readings_list=None):
    """
    Recalculates consumption for a general meter by subtracting sub-meter
    consumption and dividing by the number of contracts.
    
    """
    consumption = consumption_og
    if added_leak_by_reading is None:
        added_leak_by_reading = {}
    accumulate_added_leak(added_leak_by_reading, reading)
    meter_instance = supply_point_instance.meter
    if not meter_instance:
        return consumption_og, added_leak_by_reading
    
    def _close_already_included(close_reading):
        # Evitem duplicar si la lectura de tancament ja està en la llista a facturar
        return bool(readings_list) and close_reading in readings_list

    if (reading.is_close and reading.previous_reading
            and not reading_has_blocking_invoices(reading.previous_reading)
            and not _close_already_included(reading.previous_reading)):
        consumption = float(consumption_og) + float(reading.previous_reading.real_consumption) if reading.previous_reading.real_consumption > 0 else float(consumption_og)
        accumulate_added_leak(added_leak_by_reading, reading, reading.previous_reading)
    close_prev = get_close_previous_reading(reading)
    if close_prev and not _close_already_included(close_prev):
        consumption = float(consumption_og) + float(close_prev.real_consumption) if close_prev.real_consumption > 0 else float(consumption_og)
        accumulate_added_leak(added_leak_by_reading, reading, close_prev)
    close_prev_prev = get_close_previous_previous_reading(reading)
    if close_prev_prev and not _close_already_included(close_prev_prev):
        consumption = float(consumption_og) + float(close_prev_prev.real_consumption) if close_prev_prev.real_consumption > 0 else float(consumption_og)
        accumulate_added_leak(added_leak_by_reading, reading, close_prev_prev)
    if not meter_instance.is_general:
        return recalc_consumption_meter_multiple_contracts(reading, consumption, supply_point_instance), added_leak_by_reading

    general_meter = meter_instance
    total_meter_general = 1

    active_status = get_active_supply_point_status()

    child_meters = meter_instance.sub_meters.all()
    child_supply_points = SupplyPoint.objects.filter(meter__in=child_meters, status=active_status)
    if child_supply_points.count() == 0:
        return recalc_consumption_general_meter_no_submeters(reading, consumption, general_meter, active_status), added_leak_by_reading

    consumption_sub_meters = 0.0

    # Bulk fetch readings for all child supply points
    sp_meter_pairs = [(sp.id, sp.meter.id) for sp in child_supply_points if sp.meter]
    sub_meter_readings_dict = {}
    revised_readings_dict = {}
    close_extra_dict = {}

    if reading.batch and reading.batch.token and reading.billing and sp_meter_pairs:
        supply_point_ids = [pair[0] for pair in sp_meter_pairs]
        meter_ids = [pair[1] for pair in sp_meter_pairs]

        sub_meter_readings = Reading.objects.filter(
            batch__token=reading.batch.token,
            billing__id=reading.billing.id,
            supply_point_id__in=supply_point_ids,
            meter_id__in=meter_ids,
            is_control=False,
            is_initial=False,
        ).select_related('previous_reading__previous_reading').only(
            'calculated_value', 'supply_point_id', 'meter_id', 'is_revised',
            'previous_reading__previous_reading__is_close',
            'previous_reading__previous_reading__calculated_value',
            'previous_reading__previous_reading__real_consumption',
            'previous_reading__previous_reading__leak_value',
        )

        for sr in sub_meter_readings:
            key = (sr.supply_point_id, sr.meter_id)
            sub_meter_readings_dict[key] = float(sr.calculated_value or 0)
            revised_readings_dict[key] = sr.is_revised
            extra = 0.0
            close_prev_prev = get_close_previous_previous_reading(sr)
            if close_prev_prev:
                extra = float(close_prev_prev.real_consumption or 0)
                accumulate_added_leak(added_leak_by_reading, reading, close_prev_prev)
            close_extra_dict[key] = extra

    def _get_sub_meter_consumption_invoice(parent_meter, batch_token, billing_id, act_status, visited=None, added_leak_by_reading=None):
        """Recursively sum calculated_value of sub-meter readings for a non-revised parent meter."""
        if visited is None:
            visited = set()
        if parent_meter.id in visited:
            return 0.0, added_leak_by_reading
        visited.add(parent_meter.id)

        total = 0.0
        c_meters = parent_meter.sub_meters.all()
        if not c_meters.exists():
            return 0.0, added_leak_by_reading

        c_sps = SupplyPoint.objects.filter(
            meter__in=c_meters, status=act_status
        ).select_related('meter')

        for sp in c_sps:
            if not sp.meter:
                continue
            child_reading = Reading.objects.filter(
                batch__token=batch_token,
                billing__id=billing_id,
                supply_point=sp,
                meter=sp.meter,
                is_control=False,
                is_initial=False,
            ).select_related('previous_reading__previous_reading').first()
            if child_reading:
                total += float(child_reading.calculated_value or 0)
                close_prev_prev = get_close_previous_previous_reading(child_reading)
                if close_prev_prev:
                    total += float(close_prev_prev.real_consumption or 0)
                    accumulate_added_leak(added_leak_by_reading, reading, close_prev_prev)
                if not child_reading.is_revised:
                    total_returned, added_leak_by_reading = _get_sub_meter_consumption_invoice(
                        sp.meter, batch_token, billing_id, act_status, visited, added_leak_by_reading
                    )
                    total += total_returned
        return total, added_leak_by_reading

    for supply_point in child_supply_points:
        if supply_point.meter:
            key = (supply_point.id, supply_point.meter.id)
            if key in sub_meter_readings_dict:
                consumption_sub_meters += sub_meter_readings_dict[key]
                consumption_sub_meters += close_extra_dict.get(key, 0.0)
                if not revised_readings_dict.get(key, False) and reading.batch and reading.batch.token and reading.billing:
                    total_returned, added_leak_by_reading = _get_sub_meter_consumption_invoice(
                        supply_point.meter, reading.batch.token, reading.billing.id, active_status,
                        added_leak_by_reading=added_leak_by_reading
                    )
                    consumption_sub_meters += total_returned

    pass  # log removed
    if consumption_sub_meters > 0:
        if not reading.is_revised:
            consumption = float(consumption_og) - consumption_sub_meters if float(consumption_og) - consumption_sub_meters > 0 else 0
            pass  # log removed
    return consumption, added_leak_by_reading

def recalc_consumption_general_meter_no_submeters(reading, consumption, general_meter, sp_active_status):
    """
    Divide total consumption by the number of active supply points that have an
    active billable contract (block_billing=False). Non-billable contracts are
    excluded from the divisor and from fan-out.
    """
    try:
        divisor = count_general_meter_billable_targets(
            general_meter, active_sp_status=sp_active_status
        )
        if divisor == 0:
            # Fallback: active SPs only (no billable contracts resolved)
            supply_points = SupplyPoint.objects.filter(
                meter=general_meter,
                status=sp_active_status
            ).distinct()
            divisor = supply_points.count()
        if divisor == 0:
            return consumption
        consumption = float(consumption) / float(divisor)
        return round_ceil(consumption)
    except Exception as e:
        print(f"Error: {e}")
        return consumption
    

def recalc_consumption_meter_multiple_contracts(reading, consumption, supply_point_instance):
    """
    Recalculates consumption for a meter with multiple contracts

    """
    meter_instance = supply_point_instance.meter
    
    if not meter_instance:
        return consumption 
    
    try:
        contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
        contract_termination_pending_token = ConfigProject.objects.get(token='contract_termination_pending_token').value
        contract_termination_draft = ConfigProject.objects.get(token='contract_termination_draft').value
        
    except ConfigProject.DoesNotExist:
        pass  # log removed
        return consumption
    
    total_contracts = supply_point_instance.contracts.filter(
        status__token=contract_active_token
        ).exclude(
            contractterminationrequest__status__token__in=[contract_termination_pending_token, contract_termination_draft]
            ).count()
    
    # Prevent division by zero
    if total_contracts == 0:
        pass  # log removed
        return consumption
    
    consumption = float(consumption) / float(total_contracts)
    
    return consumption

def invoice_claim_paid_generate(invoice_id, title):
    pass  # log removed
    try:
        invoice_item = Invoice.objects.get(id=invoice_id)
        if not invoice_item:
            raise Exception("Invoice not found")
        contract = Contract.objects.get(id=invoice_item.contract.id)
        if not contract:
            raise Exception("Contract not found")
        
        #TODO: Check if this is correct???
        invoice_connection_price_rate = PriceRate.objects.get(token=ConfigProject.objects.get(token='connection_rights_price_rate_token').value)
        price_rates = [invoice_connection_price_rate]
        
        if not price_rates:
            raise Exception("No price rates found")
        exploitation = None
        invoice_line_items_data = []
        try:
            line_item_types = None
            for price_rate in price_rates:
                
                billing_range = price_rate.billing_range_active
                if not billing_range:
                    #raise Exception("No billing range found")
                    pass  # log removed
                    continue
                line_item_types = billing_range.line_item_types.all()
                
                for lit in line_item_types:
                    line_items = create_from_lineitemtype(contract, lit, None, None, None, invoice_line_items_data)
                    if line_items:
                        for line_item in line_items:
                            pass  # log removed
                            invoice_line_items_data.append(line_item)
                
                if not exploitation and price_rate.product.exploitation:
                    exploitation = price_rate.product.exploitation
        except Exception as e:
            pass  # log removed
            raise Exception("Error creating line items")
            
        
        number = generate_invoice_id()
        pass  # log removed
        
        invoice = None
        # year = datetime.datetime.now().year
        status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_pending_token').value)
        serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)
        from uuid import uuid4
        serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
        
        data = {
            'token': number,
            'number': number,
            'company': invoice_item.company if invoice_item else None,
            'exploitation': invoice_item.exploitation if invoice_item else None,
            'issue_date': datetime.datetime.now().date(),
            'billing_period_month': invoice_item.billing_period_month,
            'billing_period_year': invoice_item.billing_period_year,
            'billing_period_days': invoice_item.billing_period_days,
            'title_final': title,
            'customer_final': invoice_item.customer_final,
            'customer_token_final': invoice_item.customer_token_final,
            'person': invoice_item.person,
            'payer_final': invoice_item.payer_final,
            'payer_token_final': invoice_item.payer_token_final,
            "customer_is_juridic": invoice_item.customer_is_juridic,
            'customer_tlf_final': invoice_item.customer_tlf_final,
            'customer_email_final': invoice_item.customer_email_final,
            'address_final': invoice_item.address_final,
            'location_final': invoice_item.location_final,
            'postal_code_final': invoice_item.postal_code_final,
            'city_final': invoice_item.city_final,
            'province_final': invoice_item.province_final,
            "country_final": invoice_item.country_final,
            'payment_type': invoice_item.payment_type,
            'payment_type_final': invoice_item.payment_type_final,
            'payment_type_token_final': invoice_item.payment_type_token_final,
            'payment_bank': invoice_item.payment_bank,
            'payment_bank_final': invoice_item.payment_bank_final,
            'payment_swift_final': invoice_item.payment_swift_final,
            'dir3_final': invoice_item.dir3_final,
            'accounting_office_final': invoice_item.accounting_office_final,
            'managing_body_final': invoice_item.managing_body_final,
            'processing_unit_final': invoice_item.processing_unit_final,
            'command_final': invoice_item.command_final,
            'record_final': invoice_item.record_final,
            'exploitation': invoice_item.exploitation,
            'type': invoice_item.type,
            'type_final': invoice_item.type_final,
            'is_confirmed': invoice_item.is_confirmed,
            'origin': invoice_item.origin,
            'status': status,
            'serie': serie,
            'serie_final': serie_final_provisional,
            'serie_token_final': serie.token,
            'invoice_class': invoice_item.invoice_class,
            'invoice_class_token_final': invoice_item.invoice_class_token_final,
            'contract': invoice_item.contract,
            'used_aca': invoice_item.used_aca,
        }
        pass  # log removed
        invoice = Invoice.objects.create(**data)
        
        
        k = 0
        for line_item_data in invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{invoice.number}-{k}"
            line_item_data['invoice'] = invoice
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            pass  # log removed

        subtotal, taxes, taxes_base, total = get_totals(invoice)
        serie_final = f"{serie.token}/{invoice.id}" if serie else f"{invoice.id}"
        invoice.serie_final = serie_final
        invoice.subtotal_final = subtotal
        invoice.total_final = total
        invoice.left_to_pay = total
        invoice.save()
        confirm_invoice(invoice)
    except Exception as e:
        pass  # log removed
        raise Exception("Error creating invoice")
    return invoice

def invoice_contract_termination_generate(
    user, 
    contract_termination_id, 
    payment_type, 
    payment_bank, 
    is_budget=False, 
    electronic_invoice_data={}, 
    billing_entity=None,
    is_initiation=False,
    bill_termination_requester=False,
    company_bank=None
):
    # print("creating invoice from connection request")
    #TODO REFACTOR SINCE THERE COULD BE MORE THAN ONE SP
    exploitation = None
    contract_termination = None
    contract = None
    readings = []
    meter = None
    
    reading_estimated = ConfigProject.objects.get(token='reading_estimated').value
    
    try:
        contract_termination = ContractTerminationRequest.objects.get(id=contract_termination_id)
        contract = contract_termination.contract
        if contract.supply_point_default and contract.supply_point_default.connection and contract.supply_point_default.connection.exploitation:
            exploitation = contract.supply_point_default.connection.exploitation
        readings = contract_termination.readings.filter(is_active=True, is_control=False)
        meter = contract.supply_point_default.meter if contract.supply_point_default and contract.supply_point_default.meter else None
        if not readings or len(readings) == 0:
            readings = []
            for supply_point in contract.supply_points.all():
                reading_query = Reading.objects.filter(
                    # batch__isnull=False, 
                    supply_point=supply_point, 
                    meter=supply_point.meter, 
                    is_control=False,
                    is_active=True,
                    is_initial=False
                )
                if reading_query.filter(contract=contract).exists():
                    reading_query = reading_query.filter(contract=contract)
                if contract.registration_date:
                    reading_query = reading_query.filter(reading_date__gte=contract.registration_date)
                elif contract.created_at:
                    reading_query = reading_query.filter(reading_date__gte=contract.created_at.date())
                
                reading = reading_query.order_by('-reading_date').first()
                if reading:
                    readings.append(reading)
    except ContractTerminationRequest.DoesNotExist:
        raise Exception("Contract termination request not found")

    added_leak_by_reading = {}

    if readings and len(readings) > 0:
        if not any(reading.meter for reading in readings):
            return None
        pre_check_readings(readings)
        consumption = sum(reading.calculated_value for reading in readings)
        
        consumption_days = max(reading.consumption_days for reading in readings)
        min_days = min(reading.consumption_days for reading in readings)
        min_days_reading = next((r for r in readings if r.consumption_days == min_days), None)
        consumption_og = consumption
        for reading in readings:
            accumulate_added_leak(added_leak_by_reading, reading)
            added_close_ids = set()

            def _add_close_consumption(close_reading):
                nonlocal consumption_og
                if not close_reading or close_reading in readings or close_reading.id in added_close_ids:
                    return False
                consumption_og = float(consumption_og) + float(close_reading.real_consumption) if close_reading.real_consumption > 0 else float(consumption_og)
                accumulate_added_leak(added_leak_by_reading, reading, close_reading)
                added_close_ids.add(close_reading.id)
                return True

            close_prev = get_close_previous_reading(reading)
            if close_prev:
                _add_close_consumption(close_prev)
                if reading == min_days_reading:
                    min_days += close_prev.consumption_days if close_prev.consumption_days else 0
            close_prev_prev = get_close_previous_previous_reading(reading)
            if close_prev_prev:
                _add_close_consumption(close_prev_prev)
                if reading == min_days_reading:
                    min_days += close_prev_prev.consumption_days if close_prev_prev.consumption_days else 0
                    
        if min_days and consumption_days:
            consumption_days = max(consumption_days, min_days)
        else:
            consumption_days = consumption_days if consumption_days else min_days if min_days else None
        
        try:
            consumption = 0
            for reading in readings:
                consumption_returned, added_leak_by_reading = recalc_consumption_gen_meter(
                    reading, reading.calculated_value, reading.supply_point, added_leak_by_reading, readings
                )
                consumption += consumption_returned
        except:
            consumption = consumption_og
    else:
        if not contract.supply_points.filter(meter__isnull=False).exists():
            return None
        consumption = 0
        start_date = contract.registration_date if contract.registration_date else contract.created_at.date()
        end_date = contract_termination.requested_at.date() if contract_termination.requested_at else contract_termination.created_at.date()
        consumption_days = (end_date - start_date).days
        if consumption_days < 0:
            consumption_days = 0
    
    consumption_responsible = calc_consumption_responsible(contract, consumption)
    total_leak = 0
    real_consumption = 0
    
    try:
        use_single_price_rate = contract.use_general_price_rates
        
        # Use billing_entity (ContractRequest) for price rates if provided (Alta/Surrogation case)
        if billing_entity and hasattr(billing_entity, 'price_rates') and billing_entity.price_rates.exists():
            contract_pricerates = billing_entity.price_rates.filter(price_rate__is_active=True).order_by('price_rate__product__position')
        else:
            contract_pricerates = contract.price_rates.filter(price_rate__is_active=True).order_by('price_rate__product__position')
            
        group_by_supply_point = {}
        for price_rate in contract_pricerates:
            if price_rate.supply_point not in group_by_supply_point:
                group_by_supply_point[price_rate.supply_point] = []
            group_by_supply_point[price_rate.supply_point].append(price_rate.price_rate)
        invoice_line_items_data = []
        
        if readings and len(readings) > 0:
            for reading in readings:
                added_leak = get_added_leak(added_leak_by_reading, reading)
                reading_calculated_value = reading.calculated_value
                if reading_estimated.lower() == 'true':
                    if reading.estimated_used and reading.estimated_used > 0:
                        reading_calculated_value = float(reading_calculated_value) - float(reading.estimated_used)
                real_consumption += reading_calculated_value
                leak_reading = None
                if reading.leak_value and float(reading.leak_value) > 0:
                    leak_reading = float(reading.leak_value)
                    total_leak += leak_reading
                total_leak = float(total_leak) + float(added_leak) if total_leak else float(added_leak)
                leak_reading = leak_reading + float(added_leak) if leak_reading else float(added_leak) if added_leak > 0 else None
                
                reading_supply_point = reading.supply_point
                price_rates = group_by_supply_point.get(reading_supply_point, [])
                for price_rate in price_rates:
                    if use_single_price_rate and not reading.supply_point.meter.is_general:
                        consumption_total = consumption
                    else:
                        consumption_total, added_leak_by_reading = recalc_consumption_gen_meter(
                            reading, reading_calculated_value, reading.supply_point, added_leak_by_reading, readings
                        )
                        reading.real_consumption = consumption_total
                        reading.save()
                    
                    price_rate_billing_ranges = BillingRange.objects.filter(price_rate=price_rate)
                    
                    billing_range = price_rate_billing_ranges.filter(start__lte=reading.reading_date).filter(Q(end__gt=reading.reading_date) | Q(end__isnull=True)).order_by('-start').first()
                    if not billing_range:
                        # Forat entre l'end d'un rang i el start del seguent: agafem el proper rang futur.
                        billing_range = price_rate_billing_ranges.filter(start__gt=reading.reading_date).order_by('start').first()

                    prev_readings = Reading.objects.filter(supply_point=reading_supply_point, meter=reading.meter, reading_date__lt=reading.reading_date, contract=reading.contract, is_control=False).exclude(id=reading.id).order_by('-reading_date')
                    if prev_readings.count() == 0:
                        prev_readings = Reading.objects.filter(supply_point=reading_supply_point, meter=reading.meter, reading_date__lt=reading.reading_date, is_control=False).exclude(id=reading.id).order_by('-reading_date')
                    prev_reading = None
                    if prev_readings.count() > 0:
                        prev_reading = prev_readings.first()
                    prev_reading_date = prev_reading.reading_date if prev_reading else None
                    prev_billing_range = None
                    change_date = None
                    if not billing_range:
                        continue
                    
                    if not prev_reading_date and contract and (contract.registration_date or contract.created_at):
                        prev_reading_date = contract.registration_date if contract.registration_date else contract.created_at.date()
                    
                    if prev_reading_date and billing_range.start <= reading.reading_date and billing_range.start > prev_reading_date and reading.previous_reading and billing_range.start > reading.previous_reading.reading_date:
                        try:
                            prev_billing_range = price_rate_billing_ranges.filter(start__lte=reading.reading_date).exclude(id=billing_range.id).order_by('-start').first()
                        except BillingRange.DoesNotExist:
                            prev_billing_range = None
                        if prev_billing_range and prev_billing_range.end and prev_reading_date < prev_billing_range.end:
                            change_date = billing_range.start
                        else:
                            prev_billing_range = None
                    
                    line_item_types = billing_range.line_item_types.all()
                    if prev_billing_range:
                        line_item_types = line_item_types.union(prev_billing_range.line_item_types.all())
                    if not line_item_types:
                        continue
     
                    for lit in line_item_types:
                        line_items = create_from_lineitemtype(contract, lit, reading, consumption_total, consumption_days, invoice_line_items_data, change_date=change_date, leak_reading=leak_reading, is_termination=True)
                        if line_items:
                            for line_item in line_items:
                                invoice_line_items_data.append(line_item)
        else:
            target_date = contract_termination.requested_at.date() if contract_termination.requested_at else contract_termination.created_at.date()
            for supply_point, price_rates in group_by_supply_point.items():
                for price_rate in price_rates:
                    price_rate_billing_ranges = BillingRange.objects.filter(price_rate=price_rate)
                    billing_range = price_rate_billing_ranges.filter(start__lte=target_date).filter(Q(end__gt=target_date) | Q(end__isnull=True)).order_by('-start').first()
                    if not billing_range:
                        continue
                    line_item_types = billing_range.line_item_types.all()
                    if not line_item_types:
                        continue
                    for lit in line_item_types:
                        line_items = create_from_lineitemtype(contract, lit, None, 0, consumption_days, invoice_line_items_data, is_termination=True)
                        if line_items:
                            for line_item in line_items:
                                invoice_line_items_data.append(line_item)
                    
                if not exploitation and price_rate.product.exploitation:
                    exploitation = price_rate.product.exploitation
        ordered_invoice_line_items_data = sorted(invoice_line_items_data, key=lambda x: x['price_rate'].id)

    except Exception as e:
        pass  # log removed
        raise Exception("Error creating line items")
    
    number = generate_invoice_id()
    # print(f"Creating invoice {number}")
    try:
        if billing_entity and not bill_termination_requester:
            person = billing_entity.holder
            address = billing_entity.address_billing.address if billing_entity.address_billing else None
            payment_source = billing_entity
        elif bill_termination_requester and contract_termination.person:
            person = contract_termination.person
            address = contract.address_billing.address if contract.address_billing else None
            payment_source = contract
        else:
            person = Person.objects.get(id=contract.holder.id) if contract.holder else None
            address = contract.address_billing.address if contract.address_billing else None
            payment_source = contract

        payment_bank_instance = PersonBank.objects.get(id = payment_bank) if payment_bank else (payment_source.payment.IBAN if payment_source.payment and payment_source.payment.IBAN else None)
        payment_company_bank_instance = CompanyBank.objects.get(id = company_bank) if company_bank else (payment_source.payment.company_iban if payment_source.payment and payment_source.payment.company_iban else None)

        # year = datetime.datetime.now().year
        #total_invoices = Invoice.objects.filter(issue_date__year=year).count()

        origin = get_origin_reading()

        invoice_type_token = 'invoice_type_invoice_token' if not is_budget else 'invoice_type_budget_token'
        invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token=invoice_type_token).value)
        status = InvoiceStatus.objects.get(is_default=True)
        payment_type_instance = PaymentType.objects.get(id = payment_type)
        invoice_class = InvoiceClass.objects.get(token='OO')

        if person:
            customer_final = f"{person.name} {person.surname}" if person.surname else person.name
            customer_token_final = person.token
            payment_bank_final = payment_company_bank_instance.iban if payment_company_bank_instance else (payment_bank_instance.iban if payment_bank_instance else None)
            payment_swift_final = payment_company_bank_instance.swift if payment_company_bank_instance else (payment_bank_instance.swift if payment_bank_instance else None)
            phone_final = payment_source.person_contact_sms.first().phone if payment_source.person_contact_sms.count() > 0 else None
            email_final = payment_source.person_contact_email.email if payment_source.person_contact_email else None
        
        serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)
        
        from uuid import uuid4
        serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"
        
        if payment_source.payment and payment_source.payment.IBAN and payment_source.payment.IBAN:
            payer_final = f"{payment_source.payment.IBAN.name}"
            payer_token_final = payment_source.payment.IBAN.dni
        else:
            payer_final = customer_final
            payer_token_final = customer_token_final

        with translation.override(settings.LANGUAGE_CODE):
            title_final = _("%(invoice_type)s Contract termination") % {"invoice_type": invoice_type.name.upper()}
        
        final_readings = list(readings)
        try:
            for r in readings:
                close_prev = get_close_previous_reading(r, same_contract=True)
                if close_prev and close_prev not in final_readings:
                    final_readings.append(close_prev)

                close_prev_prev = get_close_previous_previous_reading(r, same_contract=True)
                if close_prev_prev and close_prev_prev not in final_readings:
                    final_readings.append(close_prev_prev)
        except Exception as e:
            pass
        
        data = {
            'token': number,
            'number': number,
            'contract_termination': contract_termination,
            'contract': contract if not billing_entity or bill_termination_requester else Contract.objects.filter(contract_request=billing_entity).first(),
            # El consum facturat és el del contracte que es dona de baixa, també quan la
            # factura s'emet a l'alta (billing_entity). Abans, sense billing_entity, la
            # branca "else" acabava llegint Contract.objects.filter(contract_request=None)
            # i agafava el use_aca d'un contracte qualsevol.
            'used_aca': contract.use_aca or None,
            'contract_request': billing_entity if billing_entity and not bill_termination_requester and isinstance(billing_entity, ContractRequest) else None,
            'issue_date': datetime.datetime.now().date(),
            'title_final': title_final, 
            'exploitation': exploitation,
            'company': contract.company if contract.company else exploitation.company if exploitation else None,
            'customer_final': customer_final,
            'customer_token_final': customer_token_final,
            'person': person,
            'payer_final': payer_final,
            'payer_token_final': payer_token_final,
            "customer_is_juridic": True if person.is_juridic else False,
            'customer_tlf_final': phone_final,
            'customer_email_final': email_final,
            'address_final': get_address_complete_without_city(address) if address else "-",
            'location_final': f"{address.postal_code} {address.city}, {address.province} - {address.country}" if address else "-",
            'postal_code_final': address.postal_code if address else None,
            'city_final': address.city.name if address else None,
            'province_final': address.province.name if address else None,
            "country_final": address.country.iso_code if address else None,
            'payment_type': payment_type_instance,
            'payment_type_final': payment_type_instance.name if payment_type_instance else "-",
            'payment_type_token_final': payment_type_instance.token if payment_type_instance else "-",
            'payment_bank': payment_bank_instance,
            'payment_company_bank': payment_company_bank_instance,
            'payment_bank_final': payment_bank_final,
            'payment_swift_final': payment_swift_final,
            'dir3_final': None,
            'accounting_office_final': electronic_invoice_data.get('accounting_office') if electronic_invoice_data and 'accounting_office' in electronic_invoice_data else None,
            'managing_body_final': electronic_invoice_data.get('managing_body') if electronic_invoice_data and 'managing_body' in electronic_invoice_data else None,
            'processing_unit_final': electronic_invoice_data.get('processing_unit') if electronic_invoice_data and 'processing_unit' in electronic_invoice_data else None,
            'command_final': electronic_invoice_data.get('command') if electronic_invoice_data and 'command' in electronic_invoice_data else None,
            'record_final': electronic_invoice_data.get('record') if electronic_invoice_data and 'record' in electronic_invoice_data else None,
            'origin': origin,
            'is_registration': is_initiation,
            'consumption': consumption,
            'consumption_days': consumption_days,
            'responsible_consumption': consumption_responsible,
            "is_confirmed": True,
            "type": invoice_type,
            "type_final": invoice_type.token,
            "status": status,
            'serie': serie,
            'serie_final': serie_final_provisional,
            'serie_token_final': serie.token,
            'invoice_class': invoice_class,
            'invoice_class_token_final': invoice_class.token,
            'real_consumption': sum([float(reading.calculated_value) - float(reading.estimated_used) if reading.estimated_used else float(reading.calculated_value) for reading in final_readings]),
        }

        invoice = Invoice.objects.create(**data)
        # print(f"invoice created: {invoice.id}")
        invoice.readings.set(readings)

        k = 0
        for line_item_data in ordered_invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{invoice.number}-{k}"
            line_item_data['invoice'] = invoice
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            if adjustments:
                for adjustment in adjustments:
                    new_adjustment = AppliedAdjustment.objects.create(**adjustment)
                    line_item.adjustments.add(new_adjustment)
            # print(f"line item created: {line_item.id}")
            

        subtotal, taxes, taxes_base, total = get_totals(invoice)
        total_paid = check_piggy_bank(invoice, total)
        
        if is_budget and generate_budget_serie_final:
            serie_final = generate_budget_serie_final(serie, invoice)
        else:
            serie_final = f"{serie.token}/{invoice.id}" if serie else f"{invoice.id}"
        invoice.serie_final = serie_final

        invoice.subtotal_final = subtotal
        invoice.total_final = total
        invoice.left_to_pay = float(total) - float(total_paid)
        invoice.save()

        confirm_invoice(invoice)
        # check_readings_values(readings, invoice, contract)

    except Exception as e:
        pass  # log removed
        raise Exception(f"Error creating invoice {e}")

    return invoice


def personalize_budget_to_invoice_data(budget, data):
    """Hook per client (no-op per defecte): permet afegir o ajustar els camps de la
    factura que es crea a partir d'un pressupost, just abans de l'`Invoice.objects.create()`
    de `pass_budget_to_invoice`.

    Es personalitza amb `billing/utils/budget_to_invoice_personalized.py` (repo
    customers-clients-data). Serveix per heretar la `category` del pressupost quan
    aquesta determina el digit de serie del serie_final."""
    return data


def pass_budget_to_invoice(invoice):
    try:
    
        invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token='invoice_type_invoice_token').value)
        budget_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token='invoice_type_budget_token').value)
        status_confirmed = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
        new_issue_date = invoice.batch.issue_date if invoice.batch and invoice.batch.issue_date else datetime.datetime.now().date()
        pass  # log removed
        pass  # log removed
        token = check_existing_token(invoice.token)
        data = {
                'token': token,
                'number': invoice.number,
                'contract': invoice.contract,
                'used_aca': invoice.used_aca,
                'contract_request': invoice.contract_request,
                'contract_termination': invoice.contract_termination,
                'connection': invoice.connection,
                'connection_request': invoice.connection_request,
                'issue_date': new_issue_date,
                'billing_period_month': invoice.billing_period_month,
                'billing_period_year': invoice.billing_period_year,
                'billing_period_days': invoice.billing_period_days,
                'title_final': invoice.title_final.replace(budget_type.name.upper(), invoice_type.name.upper()) if invoice.title_final else f"{invoice_type.name.upper()} {invoice.number}",
                'exploitation': invoice.exploitation,
                'company': invoice.company,
                'customer_final': invoice.customer_final,
                'customer_token_final': invoice.customer_token_final,
                'person': invoice.person,
                'payer_final': invoice.payer_final,
                'payer_token_final': invoice.payer_token_final,
                "customer_is_juridic": invoice.customer_is_juridic,
                'customer_tlf_final': invoice.customer_tlf_final,
                'customer_email_final': invoice.customer_email_final,
                'address_final': invoice.address_final,
                'location_final': invoice.location_final,
                'postal_code_final': invoice.postal_code_final,
                'city_final': invoice.city_final,
                'province_final': invoice.province_final,
                "country_final": invoice.country_final,
                'payment_type': invoice.payment_type,
                'payment_type_final': invoice.payment_type_final,
                'payment_type_token_final': invoice.payment_type_token_final,
                'payment_bank': invoice.payment_bank,
                'payment_company_bank': invoice.payment_company_bank,
                'payment_bank_final': invoice.payment_bank_final,
                'payment_swift_final': invoice.payment_swift_final,
                'dir3_final': invoice.dir3_final,
                'accounting_office_final': invoice.accounting_office_final,
                'managing_body_final': invoice.managing_body_final,
                'processing_unit_final': invoice.processing_unit_final,
                'command_final': invoice.command_final,
                'record_final': invoice.record_final,
                'origin': invoice.origin,
                'batch': invoice.batch,
                'billing': invoice.billing,
                "is_confirmed": invoice.is_confirmed,
                "simplified": invoice.simplified,
                "manually_modified": invoice.manually_modified,
                "consumption": invoice.consumption,
                "consumption_days": invoice.consumption_days,
                "responsible_consumption": invoice.responsible_consumption,
                "persons_final": invoice.persons_final,
                "type": invoice_type,
                "type_final": invoice_type.token,
                "status": invoice.status,
                'serie': invoice.serie,
                'serie_final': token,      # TEMPORARY TO AVOID UNIQUENESS ERROR SINCE IT'S IMMEDIATELY CONFIRMED AND SET A DIFFERENT SERIE/NUM
                'serie_token_final': invoice.serie_token_final,
                'invoice_class': invoice.invoice_class,
                'invoice_class_token_final': invoice.invoice_class_token_final,
                'subtotal_final': invoice.subtotal_final,
                'total_final': invoice.total_final,
                'total_final': invoice.total_final,
                'budget_token': invoice.token,
                'return_token': invoice.return_token,
                'refactored_token': invoice.refactored_token,
                'left_to_pay': invoice.left_to_pay,
                'real_consumption': invoice.real_consumption,
                'is_general': invoice.is_general,
                'due_date': invoice.due_date,
                'send_at': invoice.send_at,
                'budget_comment': invoice.budget_comment,
            }
        
        # `or data`: si una implementacio personalitzada modifica el diccionari pero
        # no el retorna, no s'ha de petar amb Invoice.objects.create(**None).
        data = personalize_budget_to_invoice_data(invoice, data) or data

        invoice_created = Invoice.objects.create(**data)
        invoice_created.readings.set(invoice.readings.all())
        invoice_created.general_contracts.set(invoice.general_contracts.all())
        budget_line_items = InvoiceLineItem.objects.filter(invoice=invoice, is_active=True)
        #create duplicate from budget_line_items and set invoice to invoice_created
        for budget_line_item in budget_line_items:
            budget_line_item.id = None
            budget_line_item.pk = None
            budget_line_item.invoice = invoice_created
            budget_line_item.save()
        
        invoice.budget_token = invoice_created.token
        
        invoice_created.status = status_confirmed
        invoice_created._generate_verifactu = True
        invoice_created.save()

        confirm_invoice(invoice_created)
        
        return invoice_created
    except Exception as e:
        raise Exception(f"Error creating invoice from budget: {e}")

def check_piggy_bank(invoice, total, generate_payment=False):
    if total <=0:
        return 0
    contract = None
    if invoice.contract:
        contract = invoice.contract
    elif invoice.contract_termination:
        contract = invoice.contract_termination.contract
    elif invoice.contract_request:
        contract = Contract.objects.filter(contract_request=invoice.contract_request).first()
    if not contract:
        return check_person_piggy_bank(invoice, total, generate_payment)
        
    piggy_bank = contract.piggy_bank
    if not piggy_bank or piggy_bank.amount <= 0:
        return 0
    piggy_bank_amount = piggy_bank.amount
    paid_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
    pending_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
    total_paid = 0
    if piggy_bank_amount >= total:
        total_paid = total
    else:
        total_paid = piggy_bank_amount
    if generate_payment:
        payment_type = PaymentType.objects.get(token="BALANCE")
        new_payment = Payment.objects.create(
            token=generate_payment_id('01'),
            name=f"{invoice.title_final}",
            status=paid_status,
            contract=contract,
            invoice=invoice,
            amount=float(total_paid),
            due_date=timezone.now() + timedelta(days=30),
            payment_type=payment_type.name,
            payment_type_token=payment_type.token,
            payment_date=timezone.now(),
            payment_bank=invoice.payment_bank_final,
            payment_swift=invoice.payment_swift_final,
            address_final=invoice.address_final,
            location_final=invoice.location_final,
            customer_final=invoice.customer_final,
            customer_token_final=invoice.customer_token_final,
            payer_final=invoice.payer_final if invoice.payer_final else invoice.customer_final,
            payer_token_final=invoice.payer_token_final if invoice.payer_token_final else invoice.customer_token_final,
        )
        from billing.utils.payment_service import generate_payment_movement
        new_payment.status = pending_status
        generate_payment_movement(new_payment, paid_status, new_payment.payment_date, payment_type.token, None, None)
        piggy_bank.amount -= total_paid
        piggy_bank.save()
        new_movement = PiggyBankMovement.objects.create(
            token=generate_token(PiggyBankMovement),
            piggy_bank=piggy_bank,
            amount=total_paid,
            is_positive=False,
            movement_date=timezone.now(),
            payment=new_payment,
        )
    return total_paid


def normalize_person_name(value):
    return " ".join(str(value or "").strip().lower().split())


def person_name_variations(person):
    return [
        f"{person.name} {person.surname if person.surname else ''}".strip(),
        f"{person.name}{person.surname if person.surname else ''}",
        f"{person.name}{person.surname}" if person.surname else person.name,
    ]


def person_matches_customer_final(person, customer_final):
    target_full_name = normalize_person_name(customer_final)
    if not target_full_name:
        return False

    variations = {normalize_person_name(v) for v in person_name_variations(person)}
    if target_full_name in variations:
        return True

    candidate_full_name = normalize_person_name(
        f"{person.name} {person.surname}" if person.surname else person.name
    )
    if candidate_full_name == target_full_name:
        return True

    words = target_full_name.split()
    for split_idx in range(1, len(words) + 1):
        possible_name = " ".join(words[:split_idx])
        possible_surname = " ".join(words[split_idx:])
        candidate_name = normalize_person_name(person.name)
        candidate_surname = normalize_person_name(person.surname)
        if candidate_name == possible_name and candidate_surname == possible_surname:
            return True

    return False


def person_candidates_for_customer_final(customer_final, exclude_token=None):
    target = normalize_person_name(customer_final)
    if not target:
        return Person.objects.none()

    queryset = Person.objects.all()
    if exclude_token:
        queryset = queryset.exclude(token=exclude_token)

    words = target.split()
    if len(words) == 1:
        word = words[0]
        return queryset.filter(Q(name__iexact=word) | Q(surname__iexact=word))

    return queryset.filter(name__icontains=words[0])


def find_person_for_invoice_customer(invoice):
    if not invoice or not invoice.customer_token_final:
        return None

    people = list(Person.objects.filter(token=invoice.customer_token_final).order_by('id'))
    if people:
        target_full_name = normalize_person_name(invoice.customer_final)
        if not target_full_name:
            return people[0] if len(people) == 1 else None

        for candidate in people:
            variations = {normalize_person_name(v) for v in person_name_variations(candidate)}
            if target_full_name in variations:
                return candidate

        for candidate in people:
            candidate_full_name = normalize_person_name(
                f"{candidate.name} {candidate.surname}" if candidate.surname else candidate.name
            )
            if candidate_full_name == target_full_name:
                return candidate

        words = target_full_name.split()
        for split_idx in range(1, len(words) + 1):
            possible_name = " ".join(words[:split_idx])
            possible_surname = " ".join(words[split_idx:])
            for candidate in people:
                candidate_name = normalize_person_name(candidate.name)
                candidate_surname = normalize_person_name(candidate.surname)
                if candidate_name == possible_name and candidate_surname == possible_surname:
                    return candidate

        return None

    if not invoice.customer_final:
        return None

    matches = [
        candidate for candidate in person_candidates_for_customer_final(invoice.customer_final)
        if person_matches_customer_final(candidate, invoice.customer_final)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def check_person_piggy_bank(invoice, total, generate_payment=False):
    try:
        selected_person = find_person_for_invoice_customer(invoice)
        if not selected_person:
            return 0

        piggy_bank = selected_person.piggy_bank
        if not piggy_bank or piggy_bank.amount <= 0:
            return 0
        total_paid = min(piggy_bank.amount, total)
        if generate_payment:
            paid_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
            pending_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
            payment_type = PaymentType.objects.get(token="BALANCE")
            new_payment = Payment.objects.create(
                token=generate_payment_id('01'),
                name=f"{invoice.title_final}",
                status=paid_status,
                person=selected_person,
                invoice=invoice,
                amount=float(total_paid),
                due_date=timezone.now() + timedelta(days=30),
                payment_type=payment_type.name,
                payment_type_token=payment_type.token,
                payment_date=timezone.now(),
                payment_bank=invoice.payment_bank_final,
                payment_swift=invoice.payment_swift_final,
                address_final=invoice.address_final,
                location_final=invoice.location_final,
                customer_final=invoice.customer_final,
                customer_token_final=invoice.customer_token_final,
                payer_final=invoice.payer_final if invoice.payer_final else invoice.customer_final,
                payer_token_final=invoice.payer_token_final if invoice.payer_token_final else invoice.customer_token_final,
            )
            from billing.utils.payment_service import generate_payment_movement
            new_payment.status = pending_status
            generate_payment_movement(new_payment, paid_status, new_payment.payment_date, payment_type.token, None, None)
            piggy_bank.amount = piggy_bank.amount - total_paid
            piggy_bank.save()
            PersonPiggyBankMovement.objects.create(
                token=generate_token(PersonPiggyBankMovement),
                person_piggy_bank=piggy_bank,
                amount=total_paid,
                is_positive=False,
                movement_date=timezone.now(),
                payment=new_payment,
            )
        
        return total_paid
    except Exception as e:
        print(f"Error checking person piggy bank: {e}")
        return 0
    

def generate_empty_invoice(contract, connection_request, person, title, payment_data, exploitation_instance, billing=None, billing_batch=None, price_rates=None, is_budget=True, invoice=None):
    pass  # log removed
    simplified = contract.simplified_invoice if contract else False
    exploitation = exploitation_instance
    
    try:
        if contract:
            exploitation = Exploitation.objects.get(id=contract.supply_point_default.connection.exploitation.id)
    except Exploitation.DoesNotExist:
        pass
    
    issue_date_str = payment_data.get("issue_date") if payment_data and 'issue_date' in payment_data else None
    if issue_date_str:
        if isinstance(issue_date_str, datetime.datetime):
            issue_date = issue_date_str
        else:
            try:
                issue_date = datetime.datetime.strptime(issue_date_str, '%Y-%m-%d')
            except Exception:
                issue_date = datetime.datetime.now()
    else:
        issue_date = datetime.datetime.now()
    
    invoice_line_items_data = []
    if price_rates:
        try:
            for price_rate in price_rates:
                billing_range = price_rate.billing_range_active
                if not billing_range:
                    continue
                line_item_types = billing_range.line_item_types.all()
                if not line_item_types:
                    continue
                for lit in line_item_types:
                    line_items = create_from_lineitemtype(contract, lit, None, None, None, invoice_line_items_data)
                    if line_items:
                        for line_item in line_items:
                            if line_item:
                                invoice_line_items_data.append(line_item)
        except Exception as e:
            pass  # log removed
            raise Exception("Error creating line items")

        invoice_line_items_data = sorted(
            invoice_line_items_data,
            key=lambda x: (
                x['line_item_type'].billing_range.price_rate.product.position if (x.get('line_item_type') and x['line_item_type'].billing_range and x['line_item_type'].billing_range.price_rate and x['line_item_type'].billing_range.price_rate.product) else 0,
                x['line_item_type'].billing_range.start if (x.get('line_item_type') and x['line_item_type'].billing_range and x['line_item_type'].billing_range.start) else date.min,
                x['name']
            )
        )

    number = generate_invoice_id()
    # print(f"Creating invoice {number}")
    try:
        payment_type_instance = None
        payment_company_bank_instance = None
        payment_bank_instance = None
        accounting_office_final = None
        managing_body_final = None
        processing_unit_final = None
        command_final = None
        record_final = None
        if payment_data:
            payment_type_instance = PaymentType.objects.get(id = payment_data.get("type_id")) if payment_data.get("type_id") else None
            payment_bank_instance = PersonBank.objects.get(id = payment_data.get("IBAN")) if payment_data.get("IBAN") else None
            payment_company_bank_instance = CompanyBank.objects.get(id = payment_data.get("company_iban")) if payment_data.get("company_iban") else None
            electronic_data = payment_data.get('electronic_data', None)
            if electronic_data:
                accounting_office_final = electronic_data.get('accounting_office')
                managing_body_final = electronic_data.get('managing_body')
                processing_unit_final = electronic_data.get('processing_unit')
                command_final = electronic_data.get('command')
                record_final = electronic_data.get('record')
            
        serie = get_default_serie() if not simplified else get_simplified_serie()
        #total_invoices = Invoice.objects.filter(issue_date__year=year, serie=serie).count()
        if contract and contract.address_billing:
            address = contract.address_billing.address
        elif person and person.addresses.count() > 0:
            try:
                billing_address = person.addresses.get(is_billing=True)
            except:
                billing_address = person.addresses.first()
            address = billing_address.address if billing_address else None
        else:
            address = None
        origin = ProductOrigin.objects.get(token=ConfigProject.objects.get(token='origin_other_token').value)
        invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token='invoice_type_budget_token').value) if is_budget else InvoiceType.objects.get(token=ConfigProject.objects.get(token='invoice_type_invoice_token').value)

        # L'empresa emissora la mana el contracte, com a
        # generate_consumption_invoice_multiple() i invoice_contract_generate(); l'explotació només és el recurs quan no hi ha
        # contracte. Amb `exploitation.company` sol, una explotació que serveix més d'una
        # empresa emet sempre en nom de la seva empresa per defecte: les despeses
        # d'impagament de contractes d'una segona empresa (claimrequest/tasks.py, que
        # entra per aquí) sortien amb la capçalera de l'empresa per defecte.
        default_company = contract.company if contract and contract.company else (exploitation.company if exploitation else None)
        selected_company = resolve_selected_company(exploitation, default_company, payment_data.get('company_id') if payment_data else None)
        selected_category = resolve_selected_category(payment_data.get('category_id') if payment_data else None)

        status = get_invoice_pending_status()
        invoice_class = get_invoice_class()
        serie = InvoiceSerie.objects.get(token=ConfigProject.objects.get(token='token_pre_invoice_serie').value)
        
        
        from uuid import uuid4
        serie_final_provisional = f"{serie.token}/PROV/{uuid4().hex}"

        
        customer_final = ""
        
        if contract and contract.holder:
            customer_final = f"{contract.holder.name} {contract.holder.surname}"
            
        elif person and person.name:
            customer_final = f"{person.name} {person.surname}" if person.surname else person.name
        
        if contract and contract.payment and contract.payment.IBAN:
            payer_final = f"{contract.payment.IBAN.name}"
            payer_token_final = contract.payment.IBAN.dni
        else:
            payer_final = customer_final
            payer_token_final = contract.holder.token if contract and contract.holder else person.token if person else None
        pass  # log removed
        data = {
            'token': number,
            'number': number,
            'contract': contract,
            'used_aca': contract.use_aca if contract else None,
            'connection_request': connection_request,
            'issue_date': billing_batch.issue_date if billing_batch and billing_batch.issue_date else issue_date.date(),
            'due_date': billing_batch.due_date if billing_batch and billing_batch.due_date else payment_data.get('due_date') if payment_data and payment_data.get('due_date') else None,
            'send_at': billing_batch.send_at if billing_batch and billing_batch.send_at else None,
            'title_final': title if title else f"{invoice_type.name.upper()}",
            'batch': billing_batch,
            'billing': billing,
            'exploitation': exploitation,
            'company': selected_company,
            'category': selected_category,
            'customer_final': customer_final,
            'customer_token_final': contract.holder.token if contract and contract.holder else person.token if person else None,
            'person': contract.holder if contract and contract.holder else person if person else None,
            'payer_final': payer_final,
            'payer_token_final': payer_token_final,
            'customer_tlf_final': contract.person_contact_sms.first().phone if contract and contract.person_contact_sms.count() > 0 else None,
            'customer_email_final': contract.person_contact_email.email if contract and contract.person_contact_email else None,
            'customer_is_juridic': contract.holder.is_juridic if contract and contract.holder else person.is_juridic if person else False,
            "country_final": address.country.iso_code if address else "-",
            "customer_is_juridic": contract.holder.is_juridic if contract and contract.holder else person.is_juridic if person else False,
            'address_final': get_address_complete_without_city(address) if address else "-",
            'postal_code_final': address.postal_code if address else None,
            'city_final': address.city.name if address else None,
            'province_final': address.province.name if address else None,
            'location_final': f"{address.postal_code} {address.city}, {address.province} - {address.country}" if address else "-",
            'payment_type': payment_type_instance,
            'payment_type_final': payment_type_instance.name if payment_type_instance else "-",
            'payment_type_token_final': payment_type_instance.token if payment_type_instance else "-",
            'payment_bank': payment_bank_instance,
            'payment_company_bank': payment_company_bank_instance,
            'payment_bank_final': payment_company_bank_instance.iban if payment_company_bank_instance else (payment_bank_instance.iban if payment_bank_instance else None),
            'payment_swift_final': payment_company_bank_instance.swift if payment_company_bank_instance else (payment_bank_instance.swift if payment_bank_instance else None),
            'accounting_office_final': accounting_office_final,
            'managing_body_final': managing_body_final,
            'processing_unit_final': processing_unit_final,
            'command_final': command_final,
            'record_final': record_final,
            'origin': origin,
            "is_confirmed": True,
            "type": invoice_type,
            'type_final': invoice_type.token if invoice_type else None,
            "status": status,
            'persons_final': contract.total_persons if contract and contract.total_persons > 0 else 3,
            'serie': serie,
            'serie_final': serie_final_provisional,
            'serie_token_final': serie.token,
            'invoice_class': invoice_class,
            'invoice_class_token_final': invoice_class.token,
            'simplified': True if simplified else False,
            'refactored_token': None,
            'real_consumption': None,
        }

        invoice = Invoice.objects.create(**data)
        pass  # log removed
        # print(f"invoice created: {invoice.id}")

        k = 0
        for line_item_data in invoice_line_items_data:
            k += 1
            adjustments = line_item_data.pop('adjustments', None)
            line_item_data['token'] = f"{invoice.number}-{k}"
            line_item_data['invoice'] = invoice
            line_item = InvoiceLineItem.objects.create(**line_item_data)
            if adjustments:
                for adjustment in adjustments:
                    new_adjustment = AppliedAdjustment.objects.create(**adjustment)
                    line_item.adjustments.add(new_adjustment)

        subtotal, taxes, taxes_base, total = get_totals(invoice)
        total_paid = check_piggy_bank(invoice, total)

        serie_final = f"{serie.token}/{invoice.id}" if serie else f"{invoice.id}"
        invoice.serie_final = serie_final

        invoice.subtotal_final = subtotal
        invoice.total_final = total
        invoice.left_to_pay = float(total) - float(total_paid)
        invoice.save()
        confirm_invoice(invoice)
    except Exception as e:
        pass  # log removed
        raise Exception("Error creating invoice")

    return invoice

def change_status_logger(user, invoice, status):
    LogInvoiceChangeStatus.objects.create(
        object=invoice,
        previous_status=invoice.status,
        current_status=status,
        user=user,
        timestamp=timezone.now()
    )
    
def update_invoice_totals(invoice):
    is_return = False
    if invoice.total_final is not None and invoice.total_final < 0:
        is_return = True
    elif invoice.subtotal_final is not None and invoice.subtotal_final < 0:
        is_return = True

    if is_return:
        for line_item in invoice.line_items.filter(is_active=True):
            # Temporarily disable _skip_signal or save logic overrides if any, 
            # but standard save() will align tax_price automatically.
            price_changed = False
            line_item.price = round_ceil(line_item.price) if line_item.price else 0.00
            line_item.total = round_ceil(line_item.total) if line_item.total else 0.0
            if line_item.price is not None and line_item.price > 0:
                line_item.price = -abs(line_item.price)
                price_changed = True
            if line_item.price_unit is not None and line_item.price_unit > 0:
                line_item.price_unit = -abs(line_item.price_unit)
                price_changed = True
            if line_item.total is not None and line_item.total > 0:
                line_item.total = -abs(line_item.total)
                price_changed = True
            if price_changed:
                line_item.save()

    subtotal, taxes, taxes_base, total = get_totals(invoice)
    total_paid = check_piggy_bank(invoice, total)
    if is_return:
        invoice.subtotal_final = -abs(subtotal)
        invoice.total_final = -abs(total)
        invoice.left_to_pay = float(invoice.total_final) - float(total_paid)
    else:
        invoice.subtotal_final = subtotal
        invoice.total_final = total
        invoice.left_to_pay = float(total) - float(total_paid)
    invoice.save()
    
def get_invoice_status(status_token):
    try:
        status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token=status_token).value)
        return status
    except InvoiceStatus.DoesNotExist:
        raise Exception(f"Invoice status with token {status_token} not found")

def generate_invoice_id(used_token = '01'):
    """Generate a unique incremental invoice token using an atomic sequence row.
    - used_token: the prefix (serie) to use for the token.
    """
    from django.db import transaction
    from django.db.models import Max

    with transaction.atomic():
        # Lock or create the sequence row for this prefix
        seq = InvoiceSequence.objects.select_for_update().filter(prefix=used_token).first()
        if seq is None:
            # Initialize from existing max token for the prefix, if any
            max_token = Invoice.objects.filter(token__startswith=used_token).aggregate(max_token=Max('token'))['max_token']
            start_from = 0
            if max_token:
                try:
                    start_from = int(max_token[len(used_token):])
                except (ValueError, IndexError):
                    start_from = 0
            seq = InvoiceSequence.objects.create(prefix=used_token, last_number=start_from)

        # Increment and build token
        seq.last_number = seq.last_number + 1
        next_num = seq.last_number
        ident = str(next_num).zfill(9)
        new_token = used_token + ident

        # In the extremely unlikely case of legacy duplicates, keep bumping within the lock
        while Invoice.objects.filter(token=new_token).exists():
            seq.last_number = seq.last_number + 1
            next_num = seq.last_number
            ident = str(next_num).zfill(9)
            new_token = used_token + ident

        seq.save(update_fields=['last_number'])

    return new_token


def generate_serie_final(serie_token, date_str, invoice_type=None, exclude_status_token=None, invoice=None):
    """Generate a unique serie_final using an atomic sequence.
    Uses select_for_update to prevent race conditions when multiple invoices are confirmed concurrently.
    Pass invoice= to use invoice fields (e.g. exploitation.token) in personalized implementations.
    """
    from django.db.models import Max

    sequence_prefix = f"{serie_token}/{date_str}"
    if invoice_type:
        sequence_prefix = f"{sequence_prefix}/{invoice_type}"
    prefix = f"{serie_token}/{date_str}"
    with transaction.atomic():
        seq = InvoiceSequence.objects.select_for_update().filter(prefix=sequence_prefix).first()
        if seq is None:
            # Exclude pending invoices (they may be cancelled and free the number)
            qs = Invoice.objects.filter(
                serie_final__startswith=prefix + "/",
            ).exclude(serie_final__isnull=True).exclude(serie_final="")
            if invoice_type:
                qs = qs.filter(type_final=invoice_type)
            if exclude_status_token:
                qs = qs.exclude(status__token=exclude_status_token)
            max_serie = qs.aggregate(max_serie=Max('serie_final'))['max_serie']
            start_from = 0
            if max_serie:
                try:
                    last_part = max_serie.split('/')[-1]
                    start_from = int(last_part)
                except (ValueError, IndexError):
                    start_from = 0
            seq = InvoiceSequence.objects.create(prefix=sequence_prefix, last_number=start_from)

        seq.last_number = seq.last_number + 1
        next_num = seq.last_number
        seq.save(update_fields=['last_number'])
        return f"{prefix}/{next_num:06d}"


# Permet personalitzar per client: si existeix generate_serie_final_personalized,
# s'usa la seva generate_serie_final en lloc de la d'aquest mòdul.
try:
    from billing.utils import generate_serie_final_personalized
    if hasattr(generate_serie_final_personalized, 'generate_serie_final'):
        generate_serie_final = generate_serie_final_personalized.generate_serie_final
except ImportError:
    pass


# Permet personalitzar per client: si existeix budget_to_invoice_personalized, s'usa
# la seva personalize_budget_to_invoice_data en lloc de la d'aquest modul (no-op).
try:
    from billing.utils import budget_to_invoice_personalized
    if hasattr(budget_to_invoice_personalized, 'personalize_budget_to_invoice_data'):
        personalize_budget_to_invoice_data = budget_to_invoice_personalized.personalize_budget_to_invoice_data
except ImportError:
    pass

# Permet personalitzar per client: si existeix generate_budget_serie_final_personalized,
# s'usa la seva generate_budget_serie_final en lloc de la lògica per defecte per a pressupostos.
generate_budget_serie_final = None
try:
    from billing.utils import generate_budget_serie_final_personalized
    if hasattr(generate_budget_serie_final_personalized, 'generate_budget_serie_final'):
        generate_budget_serie_final = generate_budget_serie_final_personalized.generate_budget_serie_final
except ImportError:
    pass

# 01 - Invoice
# 02 - 
# 03 - Commitment Deposit
# 04 - Balance

def generate_payment_id(used_token):
    from django.db.models import Max
    
    max_token = Payment.objects.filter(
        token__startswith=used_token
    ).aggregate(
        max_token=Max('token')
    )['max_token']
    
    if max_token:
        try:
            current_num = int(max_token[len(used_token):])
            next_num = current_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    ident = str(next_num).zfill(11)
    new_token = used_token + ident
    
    max_attempts = 100
    attempts = 0
    while Payment.objects.filter(token=new_token).exists() and attempts < max_attempts:
        next_num += 1
        ident = str(next_num).zfill(11)
        new_token = used_token + ident
        attempts += 1
    
    if attempts >= max_attempts:
        raise Exception(f"Unable to generate unique payment ID after {max_attempts} attempts")
    
    return new_token

def check_existing_token(token):
    try:
        invoice_type = InvoiceType.objects.get(token=ConfigProject.objects.get(token='invoice_type_invoice_token').value)
        if Invoice.objects.filter(token=token, type=invoice_type).exists():
            return generate_invoice_id()
        else:
            return token
    except Exception as e:
        raise Exception("Error while checking existing token: ", e)

def log_invoice_data_change(user, invoice, new_address, new_payment_type, new_payment_bank=None):
    if (new_address == invoice.address_final and 
        new_payment_type == invoice.payment_type_final and 
        new_payment_bank == invoice.payment_bank_final):
        pass  # log removed
        return
    pass  # log removed
    LogInvoiceDataChange.objects.create(
        object=invoice,
        current_address=new_address,
        previous_address=invoice.address_final if new_address and new_address != '' else None,
        current_payment_type=new_payment_type,
        previous_payment_type=invoice.payment_type_final if new_payment_type and new_payment_type != '' else None,
        current_iban=new_payment_bank,
        previous_iban=invoice.payment_bank_final if new_payment_bank and new_payment_bank != '' else None,
        user=user,
        timestamp=timezone.now()
    )


def get_electronic_invoices_data(request):
    try:
        
        """ 
        const searchData = {
            exploitation: selectedExploitation.value ? selectedExploitation.value.value : null,
            billing: selectedBilling.value ? selectedBilling.value.value : null,
            origin: selectedOrigins.value ? selectedOrigins.value.value : null,

            contracts: selectedContracts.value.map(contract => contract.id),
            invoices: selectedInvoices.value.map(invoice => invoice.id),
            invoice_statuses: selectedInvoiceStatuses.value.map(status => status.value),

            issue_date_start: filter_issue_date_start.value,
            issue_date_end: filter_issue_date_end.value,
            }
        """
        
        exploitation = request.data.get('exploitation', None)
        billing = request.data.get('billing', None)
        origin = request.data.get('origin', None)
        contracts = request.data.get('contracts', [])
        persons = request.data.get('persons', [])
        invoices = request.data.get('invoices', [])
        invoice_statuses = request.data.get('invoice_statuses', [])
        issue_date_start = request.data.get('issue_date_start', None)
        issue_date_end = request.data.get('issue_date_end', None)
        download = request.data.get('download', False)
        
        invoice_type_invoice_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        
        filters = Q(accounting_office_final__isnull=False, type_final=invoice_type_invoice_token)
        if exploitation:
            filters &= Q(exploitation__id=exploitation)
        if billing:
            filters &= Q(billing__id=billing)
        if origin:
            filters &= Q(origin__id=origin)
        if contracts:
            filters &= Q(contract__id__in=contracts)
        if invoices:
            filters &= Q(id__in=invoices)
        if persons:
            persons = Person.objects.filter(id__in=persons)
            filters &= (
                Q(person__in=persons)
                | Q(customer_token_final__in=persons.values_list('token', flat=True))
            )
        if invoice_statuses:
            filters &= Q(status__id__in=invoice_statuses)
        if issue_date_start:
            filters &= Q(issue_date__gte=issue_date_start)
        if issue_date_end:
            filters &= Q(issue_date__lte=issue_date_end)
        
        print(f"Filters: {filters}")

        invoices = Invoice.objects.filter(filters).order_by('-issue_date')
        
        if not download:
            from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
            serialized_invoices = InvoiceMinimalSerializer(invoices, many=True)
            
            return {'invoices': serialized_invoices.data}
        
        invoice_ids = list(invoices.values_list('id', flat=True))
        base_url = request.build_absolute_uri('/')
        from billing.tasks import generate_electronic_invoices
        task_result = generate_electronic_invoices.delay(None, base_url, invoice_ids=invoice_ids)
        print(f"Task result: {task_result.id}")
        return {'task_id': task_result.id}
    except Exception as e:
        raise Exception("Error while getting electronic invoices data: ", e)
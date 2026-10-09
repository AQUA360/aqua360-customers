import decimal
import math
import os
import re
from datetime import datetime, timedelta
import uuid
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from coredata.utils.other_utils import round_ceil
from service.models import ConnectionDiameter, MeterCaliber

from contract.models import Contract, VariableType
from service.models import ConnectionDiameter
from ..models import AppliedAdjustment, Invoice, InvoiceLineItem, Reading
from coredata.models import ConfigProject
from coredata.utils.invoice_tram_config import should_show_all_consumption_trams
from pricing.models import LineItemType, Product
from contract.utils.contract_service import get_meter_caliber, get_variables_actives, get_connection_diameter
from billing.utils.adjustment_service import adjustment_eval_conditions, convert_value, evaluate_formula, calc_consumption_responsible, generate_variables, get_contract_variable, get_line_item_type_adjustments, get_tram_adjustments, adjustment_has_interval_stretches

_invoice_percentage_correction_cached = None
_default_connection_diameter_cached = None


def get_invoice_percentage_correction():
    global _invoice_percentage_correction_cached
    if _invoice_percentage_correction_cached is None:
        try:
            _invoice_percentage_correction_cached = int(
                ConfigProject.objects.get(token='invoice_percentage_correction').value
            )
        except Exception:
            _invoice_percentage_correction_cached = 20
    return _invoice_percentage_correction_cached


def get_default_connection_diameter_value():
    global _default_connection_diameter_cached
    if _default_connection_diameter_cached is None:
        _default_connection_diameter_cached = int(
            float(ConnectionDiameter.objects.get(is_default=True).name)
        )
    return _default_connection_diameter_cached


def get_value_by_change_price_rate_date(value, reading, billing_days, dies_consum, billing_range, change_date, last_reading_date, fixed_consumption_days = None):
    
    if reading.previous_reading and reading.contract == reading.previous_reading.contract:
        if reading.previous_reading.reading_date < reading.contract.created_at.date() and reading.consumption_days != (reading.reading_date - reading.previous_reading.reading_date).days:
            compare_days = (reading.reading_date - reading.previous_reading.reading_date).days
        else:
            compare_days = dies_consum
    else:
        compare_days = max(billing_days, dies_consum)
    
    if billing_range.end and billing_range.end <= reading.reading_date:
        reading_last  = last_reading_date if last_reading_date else reading.previous_reading.reading_date if reading.previous_reading else None
        if not reading_last:
            return int(value), dies_consum
        value = round_ceil(float(value) * float(((change_date - reading_last).days/compare_days)), True, True)
        dies_consum = (change_date - reading_last).days
    else:
        value = round_ceil(float(value) * float(((reading.reading_date - change_date).days/compare_days)), True, True)
        dies_consum = (reading.reading_date - change_date).days
    return int(value), dies_consum

def get_last_reading(reading):
    last_reading = Reading.objects.filter(meter=reading.meter, supply_point=reading.supply_point, reading_date__lt=reading.reading_date, is_control=False, is_initial=False).exclude(id=reading.id).order_by('-reading_date').first()
    # print(f"Last reading: {last_reading} with reading.reading_date: {reading.reading_date}")
    
    if last_reading is None:
        # print(f"No tenim last_reading: {last_reading}, potser que se sigui alta nova amb nou comptador, hauriem de buscar per punt de subministrament")
        last_reading = Reading.objects.filter(supply_point=reading.supply_point, reading_date__lt=reading.reading_date, is_control=False, is_initial=False).exclude(id=reading.id).order_by('-reading_date').first()
        # if not last_reading:
        #     print(f"No hem trobat lectura mitjançant SupplyPoint")
        # else:
        #     print(f"Hem trobat lectura mitjançant SupplyPoint: Last reading: {last_reading} with reading.reading_date: {reading.reading_date}")
    return last_reading if last_reading else None


def constrain_total_value(value):
    """
    Constrain a total value to the InvoiceLineItem.total field limits.
    Field is DecimalField(max_digits=10, decimal_places=4), so max is 9,999,999.9999
    """
    if value is None:
        return None
    
    # Convert to Decimal for precise rounding
    decimal_value = Decimal(str(value))
    
    # Maximum value for max_digits=11, decimal_places=4 is 9,999,999.9999
    MAX_TOTAL = Decimal('9999999.9999')
    MIN_TOTAL = Decimal('-9999999.9999')
    
    # Clamp the value to the allowed range
    if decimal_value > MAX_TOTAL:
        decimal_value = MAX_TOTAL
    elif decimal_value < MIN_TOTAL:
        decimal_value = MIN_TOTAL
    
    # Round to 4 decimal places (safe since we've already clamped the value)
    decimal_value = decimal_value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    
    return float(decimal_value)

def calc_consum(reading, last_reading):
    if not last_reading:
        return reading.reading_value
    
    # TODO: si reading és més petit que last_reading, pot voler dir que el comptador a donat la volta. Ho avaluarem.

    return reading.reading_value - last_reading.reading_value


def do_calc_operation(value, operation, quantity, contract = None, variable_type = None):
    if operation == 'min':
        return max(value, quantity)
    if operation == 'max':
        return min(value, quantity)
    if operation == 'ptg':
        try:
            return float(value) * float(quantity)
        except Exception as e:
            print(f"Error doing ptg operation, returning multiplier: {quantity}")
            return quantity
    if operation == 'set':
        if variable_type:
            variable = get_contract_variable(contract, variable_type)
            return float(variable.value) if variable else value
        else:
            return float(quantity)
    if operation == 'var':
        try:
            variable = get_contract_variable(contract, variable_type)
            return float(variable.value) * float(value) if variable else value
        except Exception as e:
            return None
    return value


def calc_correctors_variables_calcul(variables, variable_types, line_item_type, consum, dies_consum, diferencia_fuita, days_correction = None, contract = None, units_adjusted = None, reading_batch_id = None):
    # Ajustaments

    applied_adjustments = []
    description = ""
    if line_item_type.adjustments:
        # print("line_item_type.adjustments: ", line_item_type.adjustments.all())
        price = None
        for adj in get_line_item_type_adjustments(line_item_type):
            # Li evaluem les condicions
            condition_vulnerable = False
            if adj and adj.conditions:
                # print("evaluating conditions: ", adj.conditions)
                # for condition in adj.conditions.all():
                #     print("condition: ", condition)
                # print("variables: ", variables)
                conditions_check, condition_vulnerable = adjustment_eval_conditions(adj, variables, variable_types, reading_batch_id)
                # print(f"Conditions check: {conditions_check}")
                if not conditions_check:
                    continue # passem d'aquest corrector i continuem mirant correctors
            
            # Si es sobre una Variable de càlcul:
            if adj.variable_calculation:
                #print(f"Variable de càlcul: {adj.variable_calculation.token}")
                #print(f"Variable de càlcul: {adj.variable_calculation.token}")
                # print(f"Operació: {adj.operation.token}")
                # print(f"Quantitat: {adj.quantity}")
                # print(f"Formula: {adj.formula}")

                # Ajustem la quantitat en funció de la fórmula i el days_correction
                total_applied = 0
                adj_quantity = adj.quantity if adj.quantity else 0
                if adj.formula and adj.formula is not None:
                    adj_quantity = evaluate_formula(adj.formula, variables)
                    total_applied = adj_quantity
                if days_correction:
                    adj_quantity = adj_quantity * days_correction
                    total_applied = adj_quantity
                    # Aquesta lògica assegura que per l'operació 'min', si el resultat (total_applied) és menor que 1, es força a 1.
                    # Això evita que, per períodes llargs (p.ex. 1 dia de consum d'un període de 90 dies donant valors com 0.2 o 0.4), s'acabi aplicant 0 en comptes d'1.
                    if adj.operation.token == 'min' and total_applied < 1:
                        adj_quantity = 1
                        total_applied = 1

                # Apliquem l'ajustament en funció de la variable de càlcul
                if adj.variable_calculation.token == 'consum':
                    og_consum = consum
                    consum = do_calc_operation(consum, adj.operation.token, adj_quantity, contract, adj.variable_type)
                    total_applied = consum if og_consum != consum else None
                elif adj.variable_calculation.token == 'dies_consum':
                    og_dies_consum = dies_consum
                    dies_consum = do_calc_operation(dies_consum, adj.operation.token, adj_quantity, contract, adj.variable_type)
                    total_applied = dies_consum if og_dies_consum != dies_consum else None
                elif adj.variable_calculation.token == 'price':
                    og_price = price
                    price = do_calc_operation(price, adj.operation.token, adj_quantity, contract, adj.variable_type)
                    total_applied = price if og_price != price else None
                elif adj.variable_calculation.token == 'units':
                    # continue
                    og_units = units_adjusted or 0
                    units_adjusted = do_calc_operation(units_adjusted, adj.operation.token, adj_quantity, contract, adj.variable_type)
                    total_applied = units_adjusted if og_units != units_adjusted else None
                else:
                    raise Exception(f"Error en calcular ajustament: {adj.adjustment_type}.")

                if total_applied is not None:
                    if adj.operation.token == 'min':
                        description += f"{adj.name}" if adj.name else ""
                    applied_adjustments.append({
                        'token': uuid.uuid4(),
                        'name': adj.name,
                        'adjustment': adj,
                        'is_vulnerable': condition_vulnerable,
                        'total_applied': total_applied,
                    })
    return consum, dies_consum, diferencia_fuita, price, applied_adjustments, description, units_adjusted


def calc_correctors_price(line_item_type, price, variables, variable_types, contract, reading_batch_id = None):
    # Ajustaments
    preu_corregit = price
    description = None
    applied_adjustments = []
    if line_item_type.adjustments:
        for adj in get_line_item_type_adjustments(line_item_type):
            # La quantitat pot venir definida pel camp quantity o pel camp formula (quantity quedarà deprecated)
            adj_quantity = adj.quantity if adj.quantity else 0
            if adj.formula and adj.formula is not None:
                adj_quantity = evaluate_formula(adj.formula, variables)
                
            # Si es sobre una Variable de càlcul, no es fa aquí, passem
            if adj.variable_calculation:
                if adj.variable_calculation.token != 'price':
                    continue

            # print(f"Corrector: {adj}")
            # Li evaluem les condicions
            condition_vulnerable = False
            if adj and adj.conditions:
                # print(f"Evaluating conditions for adjustment - calc_correctors_price - {adj.token}")
                conditions_check, condition_vulnerable = adjustment_eval_conditions(adj, variables, variable_types, reading_batch_id)
                # print(f"Conditions check: {conditions_check}")
                if not conditions_check:
                    continue # passem d'aquest corrector i continuem mirant correctors

            # Actuem sobre el preu, mirem si té un preu fix.
            if not adjustment_has_interval_stretches(adj):
                # print(f"Corrector no té intervals: {adj}")
                og_price = price
                preu_corregit = do_calc_operation(price, adj.operation.token, adj_quantity, contract, adj.variable_type)
                if og_price != preu_corregit:
                    description = adj.name if adj.name else adj.token
                    
                applied_adjustments.append({
                    'token': uuid.uuid4(),
                    'name': description,
                    'adjustment': adj,
                    'is_vulnerable': condition_vulnerable,
                    'total_applied': preu_corregit,
                })

    return preu_corregit, description, applied_adjustments

def calc_correctors_tram(variables, variable_types, tram, line_item=None, reading_batch_id = None):
    # mirem si hi ha algun corrector de tram
    adjustment_name = None
    corrected_price = None
    applied_adjustments = []
    if tram.adjustments:
        # variables_formula, variable_types = generate_variables(contract, consum, dies_consum)
        for adj_interval in get_tram_adjustments(tram, line_item):
            adj = adj_interval.adjustment
            
            # Si no hi ha adjustment, passem al següent
            if not adj:
                continue
                
            # print(f"Corrector Interval: {adj_interval}; Operacio: {adj.operation.token}; Coeficient/Valor: {adj_interval.coefficient}")

            # Li evaluem les condicions
            condition_vulnerable = False
            if adj.conditions:
                # print(f"Evaluating conditions for adjustment - calc_correctors_tram - {adj.token}")
                conditions_check, condition_vulnerable = adjustment_eval_conditions(adj, variables, variable_types, reading_batch_id)
                # print(f"Conditions check: {conditions_check}")
                if not conditions_check:
                    # print("\n\nNo conditions met")
                    continue # passem d'aquest corrector i continuem mirant correctors

            adjustment_name = adj.name
            total_applied = 0
            if adj.operation.token == 'ptg': # si és percentatge, l'apliquem al preu
                coeff = adj_interval.coefficient if adj_interval.coefficient else 1
                if adj_interval.formula and adj_interval.formula is not None:
                    coeff = evaluate_formula(adj_interval.formula, variables)
                if tram.price:
                    # print(f"Apliquem el coefficent {adj_interval.coefficient} al preu tram.price {tram.price}")
                    tram.price = coeff * tram.price
                    total_applied = tram.price
                if tram.proportional_price:
                    # print(f"Apliquem el coefficent {adj_interval.coefficient} al preu tram.proportional_price {tram.proportional_price}")
                    tram.proportional_price = coeff * tram.proportional_price
                    total_applied = tram.proportional_price
                applied_adjustments.append({
                    'token': uuid.uuid4(),
                    'name': adjustment_name,
                    'adjustment': adj,
                    'is_vulnerable': condition_vulnerable,
                    'total_applied': total_applied,
                })
            if adj.operation.token == 'ext' or adj.operation.token == 'var': # amplicació de tram, modifiquem el end_stretch
                if adj_interval.formula and adj_interval.formula is not None:
                    value = int(evaluate_formula(adj_interval.formula, variables))
                    total_applied = value
                    if adj.variable_calculation and adj.variable_calculation.token == 'price':
                        corrected_price = value
                    else:
                        tram.end_stretch = value

    # print(f"calc_correctors_tram: Retorn: {tram.price}, {tram.proportional_price}, {tram.end_stretch}")
    return tram.price, tram.proportional_price, tram.end_stretch, adjustment_name, corrected_price, applied_adjustments

def _translated_name(obj, lang, default_name):
    if not obj:
        return default_name
    translation = obj.translations.filter(language=lang).first()
    return translation.name if translation and translation.name else default_name


def create_line_item_data(contract, line_item_type, price_unit, price, units, name=None, description=None, do_taxes=True, reading=None, adjustments=None, stretch=0, end_stretch=None, correction_multiplier=None, units_adjusted=None, units_multiplier=None):
    # print("in create_line_item_data")
    # print(line_item_type.name)
    
    # Correction for not prorrates lineitemtypes
    
    if correction_multiplier:
        units = correction_multiplier
        price = price_unit * correction_multiplier
    # ADJUSTMENTS OVERRIDE ANYTHING ELSE
    if units_adjusted:
        units = units_adjusted
        price = price_unit * units_adjusted
    
    if units_multiplier:
        units = units * units_multiplier
        price = price_unit * units

    if not line_item_type:
        raise Exception("Line item type is required")
    # print("\n\n\nadjustments: ", adjustments)s
    try:
        tax_price = 0
        if line_item_type.tax and do_taxes:
            # print(f"Tax: {line_item_type.tax}; Tax percent: {line_item_type.tax.percent}")
            tax_price = round_ceil(price) * (line_item_type.tax.percent / 100)
        total = float(round_ceil(price)) + float(round_ceil(tax_price))
        # Constrain total to database field limits (max_digits=10, decimal_places=4)
        # total = constrain_total_value(total)
    except Exception as e:
        raise Exception(f"Error en calcular tax: {e}")
    
    if adjustments:
        #clean adjustments from none values and repeated adjustments (same name, total_applied and adjustment)
        adjustments = [adj for adj in adjustments if adj is not None]
        # Deduplicate: keep only first occurrence of each unique combination
        seen = set()
        unique_adjustments = []
        for adj in adjustments:
            # Create a unique key from name, total_applied, and adjustment object
            key = (adj.get('name'), adj.get('total_applied'), adj.get('adjustment'))
            if key not in seen:
                seen.add(key)
                unique_adjustments.append(adj)
        adjustments = unique_adjustments
  
    invoice_lang = contract.language if isinstance(contract, Contract) and contract.language else settings.LANGUAGE_CODE
    product = line_item_type.billing_range.price_rate.product if line_item_type.billing_range.price_rate else None
    price_rate = line_item_type.billing_range.price_rate

    line_data = {
        'token': line_item_type.token if line_item_type.token else '',
        'line_item_type': line_item_type,
        'name': name if name else _translated_name(line_item_type, invoice_lang, line_item_type.name),
        'company': product.company if product else None,

        'product': product,
        'product_name': _translated_name(product, invoice_lang, product.name) if product else None,

        'price_rate': price_rate,
        'price_rate_name': _translated_name(price_rate, invoice_lang, price_rate.name) if price_rate else None,

        'price_unit': price_unit if line_item_type.is_positive else -price_unit,
        'units': units,
        'price': (round_ceil(price)) if line_item_type.is_positive else -(round_ceil(price)),
        
        'interval': stretch,
        'end_stretch': end_stretch,
        'adjustments': adjustments,
         
        'tax': line_item_type.tax if do_taxes else None,
        'tax_percent': line_item_type.tax.percent if line_item_type.tax and do_taxes else 0,
        'tax_price': round_ceil(tax_price) if line_item_type.is_positive else -round_ceil(tax_price),

        'total': round_ceil(total) if line_item_type.is_positive else -round_ceil(total),
        'description': description if description and description.replace(" ", "") != "" else None,
        
        'reading': reading,
        'contract': contract if isinstance(contract, Contract) else None,
    }
    # print("line data")
    # print(line_data)
    
    return line_data


def calculate_billing_days_for_period(billing_period_token, last_reading_date, reading_date):
    PERIOD_MONTHS_MAP = {
        'trimestral': 3,
        'semestral': 6,
        'bimestral': 2,
        'quadrimestral': 4,
        'anual': 12,
        'mensual': 1,
    }
    
    #TODO: FALTA DIARIA (?)
    
    if billing_period_token in PERIOD_MONTHS_MAP:
        months = PERIOD_MONTHS_MAP[billing_period_token]
        # debug log removed: last reading date
        
        expected_billing_date = last_reading_date + relativedelta(months=months)
        actual_days = (expected_billing_date - last_reading_date).days
        return actual_days
    
    return None

def return_billing_months_for_lineitemtype(billing_period_token):
    PERIOD_MONTHS_MAP = {
        'trimestral': 3,
        'semestral': 6,
        'bimestral': 2,
        'quadrimestral': 4,
        'anual': 12,
        'mensual': 1,
    }
    
    if billing_period_token in PERIOD_MONTHS_MAP:
        return PERIOD_MONTHS_MAP[billing_period_token]

    
    return None


# Create Contract from ContractRequest
def create_from_lineitemtype(contract, line_item_type, reading, consumption, consumption_days, existing_line_items=None, change_date=None, prev_invoice = None, leak_reading=None, is_termination=False, billing_correction=None, prev_date = None, period_months=None):
    # log removed
    # print(f"Contract: {contract}")
    # print(f"Reading: {reading}")
    # print(f"Consumption: {consumption}")
    # print(f"Consumption days: {consumption_days}")
    # print(f"Change date: {change_date}")
    # print(f"Prev invoice: {prev_invoice}")
    # print(f"Leak reading: {leak_reading}")
    # print(f"Is termination: {is_termination}")

    from billing.utils.invoice_service import (
        get_close_previous_reading,
        get_close_previous_previous_reading,
    )
    
    estimated_value = 0

    invoice_lang = contract.language if isinstance(contract, Contract) and contract.language else settings.LANGUAGE_CODE
    line_item_type_name = _translated_name(line_item_type, invoice_lang, line_item_type.name)

    billing_range = line_item_type.billing_range
    
    billing_days = line_item_type.billing_period.days if line_item_type.billing_period else None
    
    percentage_correction = get_invoice_percentage_correction()
    min_correction = (100 - percentage_correction)/100
    max_correction = (100 + percentage_correction)/100
    
    # print("line item type: ", line_item_type_name)
    # print("in create from line item")
    corrected_price = None
    days_correction = None
    last_reading_date = None
    applied_adjustments = []
    description=""
    has_correction = False
    print(" - "+line_item_type_name)
    # To detect new contracts, we check if consumption days are 10 days less than expected
    if reading:
        is_first_invoice = (
            (reading.previous_reading and reading.previous_reading.contract != contract) or
            (reading.previous_reading and reading.previous_reading.is_initial) or
            (reading.previous_reading and reading.previous_reading.is_close) or
            (reading.previous_reading and reading.previous_reading.contract_termination_requests.exclude(contract=reading.previous_reading.contract).exists()) or
            (not reading.previous_reading)
        )
    else:
        is_first_invoice = True

    if is_first_invoice and contract and getattr(contract, 'bill_full_period', False):
        is_first_invoice = False

    line_item_type_months = return_billing_months_for_lineitemtype(line_item_type.billing_period.token) if line_item_type.billing_period else None

    should_correct = line_item_type_months != period_months and not line_item_type.is_prorated and not ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination))

    fixed_consumption_days = consumption_days

    if should_correct and period_months:
        correction_multiplier = period_months / line_item_type_months
        consumption_days = period_months * 30
    else:
        correction_multiplier = None
    
    reading_batch_id = reading.batch.id if reading and reading.batch else None
    # print("\n\n\n\n")
    # print("product: ", line_item_type.billing_range.price_rate.product.name)
    # print("price rate: ", line_item_type.billing_range.price_rate.name)
    if reading: # és una factura recurrent de l'aigua
        
        
        if reading.supply_point:
            # <Albert> Comento aquesta linia treient el batch de la lectura. Ja que en contractes nous, pot ser que la lectura no tingui batch (perquè encara no s'ha facturat la baixa)
            # last_reading = Reading.objects.filter(batch__isnull=False, meter=reading.meter, supply_point=reading.supply_point, reading_date__lt=reading.reading_date, is_control=False).exclude(id=reading.id).order_by('-reading_date').first()
            last_reading = get_last_reading(reading)
            if last_reading:
                last_reading_date = last_reading.reading_date
        
        dies_consum = consumption_days
        if not dies_consum:
            dies_consum = billing_days

        if prev_date:
            last_reading_date = prev_date
        elif not last_reading_date:
            pass # Keep what was found in get_last_reading


        billing_correction = 1 if billing_correction == 0 or not billing_correction else billing_correction
        should_match_days = not (dies_consum/billing_correction < min_correction or dies_consum/billing_correction > max_correction)
        # print("reading consumption days: ", reading.consumption_days)
        og_dies_consum = dies_consum
        days_to_match = None
        diferencia_fuita = 0
        calculated_value = reading.calculated_value
        close_prev = get_close_previous_reading(reading)
        if close_prev:
            calculated_value = float(calculated_value) + float(close_prev.calculated_value) if close_prev.calculated_value > 0 else float(calculated_value)
        close_prev_prev = get_close_previous_previous_reading(reading)
        if close_prev_prev:
            calculated_value = float(calculated_value) + float(close_prev_prev.calculated_value) if close_prev_prev.calculated_value > 0 else float(calculated_value)
        if change_date:
            # WITH MULTIPLE BILLING RANGES WE PORCE PRORRATED
            should_correct = False
            correction_multiplier = None
            line_item_type.is_prorated = True

            consumption, dies_consum = get_value_by_change_price_rate_date(
                consumption, reading, billing_days,
                og_dies_consum, billing_range, change_date,
                last_reading_date, fixed_consumption_days
            )
            if dies_consum <= 0:
                return []
            days_to_match = period_months * 30 if should_match_days else og_dies_consum
            
        has_correction = dies_consum/billing_correction < min_correction or dies_consum/billing_correction > max_correction
        if leak_reading:
            consumption_percentage = float(consumption)/float(calculated_value)
            # print("consumption percentage: ", consumption_percentage)
            correction = (dies_consum/billing_days) if has_correction else (billing_correction/billing_days)
            # print("\n\ncorrection: ", correction)
            if (correction < min_correction or correction > max_correction) and (line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated):
                correction = 1
            # REMOVED CORRECTION. NO SENSE IN CORRECTING CONSUMPTION HERE
            # diferencia_fuita = (float(leak_reading) * consumption_percentage) 
            diferencia_fuita = float(leak_reading)
            if change_date:
                diferencia_fuita, _ = get_value_by_change_price_rate_date(
                    diferencia_fuita, reading, billing_days,
                    og_dies_consum, billing_range, change_date,
                    last_reading_date
                )
            
        consum = float(consumption) - float(diferencia_fuita)
        if line_item_type.quantity and line_item_type.quantity.token == 'diferencia_fuita_consum':
            consum = consumption
        if line_item_type.quantity and line_item_type.quantity.token == 'prev_consum':
            if reading.previous_reading and reading.contract == reading.previous_reading.contract:
                consum = reading.previous_reading.calculated_value - reading.previous_reading.leak_value if reading.previous_reading.leak_value else reading.previous_reading.calculated_value
                close_prev = get_close_previous_reading(reading)
                if close_prev:
                    consum = close_prev.previous_reading.calculated_value if close_prev.previous_reading else 0
                close_prev_prev = get_close_previous_previous_reading(reading)
                if close_prev_prev:
                    consum = close_prev_prev.previous_reading.calculated_value if close_prev_prev.previous_reading else 0
            else:
                return None
        consumption_responsible = calc_consumption_responsible(contract, consum) if contract else None
        variables, variable_types = generate_variables(contract, consum, dies_consum, diferencia_fuita, consumption_responsible, prev_invoice)

        # Correctors de variables de càlcul
        if line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated:
            if ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination) or line_item_type.is_prorated) and billing_days:
                days_correction = (dies_consum/billing_days) if has_correction else (billing_correction/billing_days)
                # print("\n\ndays_correction: ", days_correction)
                if days_correction >= min_correction and days_correction <= max_correction:
                    # print("passed correction")
                    days_correction = 1
    
        units_adjusted = None
        
        consum, dies_consum, diferencia_fuita, _, var_adjustments, description, units_multiplier = calc_correctors_variables_calcul(variables, variable_types, line_item_type, consum, dies_consum, diferencia_fuita, days_correction, contract, units_adjusted, reading_batch_id)

        if var_adjustments:
            applied_adjustments.extend(var_adjustments)
        consum = round(consum)
        # print("after cal correctors consum: ", consum)
        # print(f"[Amb correctors] Consum: {consum}; Dies consum: {dies_consum}")
        # print(f"\nProduct: {line_item_type.billing_range.price_rate.product.token}")
        # print(f"Token: {ConfigProject.objects.get(token='token_water_water_consumption').value}")
        
        # Si no és consum no fem servir la bossa de consum estimat
            
        quantitat = consum
        
        """ if line_item_type.active_choice or line_item_type.inactive_choice:
            if (line_item_type.active_choice == 'DAYS' or line_item_type.inactive_choice == 'DAYS' ) and billing_days:
                if dies_consum and dies_consum > 0:
                    quantitat = quantitat * (dies_consum/billing_days)
                    dies_consum = dies_consum * (dies_consum/billing_days) """
        
        es_prorratejat = False
        prorratejat_quantitat = None
        """ if leak_reading:
            diferencia_fuita = quantitat - leak_reading """
        
    else:
        quantitat = 0 if is_termination else 1
        consum = 0
        dies_consum = 0
        billing_days = 1
        diferencia_fuita = 0
        es_prorratejat = False
        prorratejat_quantitat = None
        consumption_responsible = calc_consumption_responsible(contract, consum) if contract else None
        variables, variable_types = generate_variables(contract, consum, dies_consum, diferencia_fuita, consumption_responsible, prev_invoice)
        units_multiplier = None
        units_adjusted = None
    # print("got initial data\n")
    # print(f"Line item type: {line_item_type}")
    
    # print("billing days: ", billing_days)
    # print("dies consum: ", dies_consum)
    # print("quantitat: ", quantitat)
    # es_prorratejat = line_item_type.is_prorated
    if line_item_type.quantity and line_item_type.quantity.token == 'dies_consum':
        quantitat = dies_consum
        prorratejat_quantitat = line_item_type.billing_period.days
        
    if line_item_type.quantity and line_item_type.quantity.token == 'total_persons':
        quantitat = contract.total_persons if contract else 3
    # print("passed reading")
    
    # Càlcul del preu
    price_unit = 0
    price = 0
    units = 0
    
    linies = []
    # print("\n\ndiferencia fuita: ", diferencia_fuita)
    # print("line item quantity: ", line_item_type.quantity)
    # print("line always show: ", line_item_type.always_show)

    if line_item_type.quantity and line_item_type.quantity.token == 'diferencia_fuita':
        if diferencia_fuita <= 0 and not line_item_type.always_show:
            return linies
        else:
            quantitat = diferencia_fuita
    if billing_correction != 0 and billing_correction is not None:
        correction_ptg = billing_correction/billing_days if not has_correction else dies_consum/billing_days
        if days_to_match:
            days = dies_consum * days_to_match / og_dies_consum
            period = days_to_match / billing_days
            correction_ptg = days * period / days_to_match
    else:
        correction_ptg = 1

    try: 
        meter_caliber = int(get_meter_caliber(contract)) if contract else 13
        try:
            if reading:
                connection = reading.supply_point.connection if reading.supply_point else None
                if connection and connection.diameter:
                    connection_diameter = int(float(connection.diameter.name))
                else:
                    # print("Error: Connection or diameter not found from reading")
                    connection_diameter = 63
            else:
                connection_diameter = int(float(get_connection_diameter(contract)))
        except Exception as e:
            # print(f"Error in creating line item data - connection diameter: {e}")
                    connection_diameter = get_default_connection_diameter_value()
            
            
        if( line_item_type.price != None ): # preu fix
            
            price_unit = line_item_type.price
            price_unit, description, cal_adjustments = calc_correctors_price(line_item_type, price_unit, variables, variable_types, contract, reading_batch_id) # mirem si hi ha una correcció de preu
            if cal_adjustments:
                applied_adjustments.extend(cal_adjustments)
            units = 1
            # print("\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nmin_correction: ", min_correction)
            # print("max_correction: ", max_correction)
            # print("line_item_type.active_choice: ", line_item_type.billing_range.price_rate.product.name)
            if es_prorratejat:
                units = dies_consum
                price_unit = price_unit / prorratejat_quantitat # el preu diari
            # print("units: ", units)
            if (line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated) and billing_days:
                if (line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination) or line_item_type.is_prorated:
                    if dies_consum and dies_consum > 0:
                        if correction_ptg < min_correction or correction_ptg > max_correction:
                            units = units * (correction_ptg)

            units = round_ceil(units or 0)
            price = float(price_unit or 0) * float(units or 0)
            _, _, _, corrected_price, var_adjustments, extra_description, _ = calc_correctors_variables_calcul(variables, variable_types, line_item_type, consum, dies_consum, diferencia_fuita, days_correction, contract, units_adjusted=units_adjusted, reading_batch_id=reading_batch_id)
            if extra_description and extra_description.replace(" ", "") != "":
                description = extra_description
            if corrected_price:
                price = corrected_price
            if var_adjustments:
                applied_adjustments.extend(var_adjustments)
            linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, None, description, True, reading, applied_adjustments, 0, None, correction_multiplier, units_adjusted, units_multiplier))
            
        elif line_item_type.proportional_price != None: # preu proporcional
            
            price_unit = line_item_type.proportional_price
            price_unit, description, cal_adjustments = calc_correctors_price(line_item_type, price_unit, variables, variable_types, contract, reading_batch_id) # mirem si hi ha una correcció de preu
            if cal_adjustments:
                applied_adjustments.extend(cal_adjustments)
            units = quantitat
            if es_prorratejat:
                units = dies_consum
                price_unit = price_unit / prorratejat_quantitat # el preu diari
            if line_item_type.quantity and line_item_type.quantity.token in ['consum', 'diferencia_fuita_consum', 'diferencia_fuita']:
                units = round_ceil(units, to_int=True)
            """ if line_item_type.active_choice or line_item_type.inactive_choice:
                
                if (line_item_type.active_choice == 'DAYS' or line_item_type.inactive_choice == 'DAYS') and billing_days:
                    if dies_consum and dies_consum > 0:
                        units = units * (dies_consum/billing_days) """
            units = round_ceil(units or 0)
            price = float(price_unit) * float(units)
            # print("\n\n\nunits", units)
            _, _, _, corrected_price, var_adjustments, extra_description, _ = calc_correctors_variables_calcul(variables, variable_types, line_item_type, consum, dies_consum, diferencia_fuita, days_correction, contract, units_adjusted=units_adjusted, reading_batch_id=reading_batch_id)
            if extra_description and extra_description.replace(" ", "") != "":
                description = extra_description
            if corrected_price:
                price = corrected_price
            if var_adjustments:
                applied_adjustments.extend(var_adjustments)
            linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, None, description, True, reading, applied_adjustments, 0, None, correction_multiplier, units_adjusted))
        
        elif line_item_type.price_interval: # preu interval (trams)
            og_quantitat = quantitat
            # Ens ve una taula: tram, limit, preu prop: --> tram 1; 30; 0.1;
            # Si el consum és 20, el preu serà 20 * 0.1
            # Si el consum és 35, el preu serà 30 * 0.1 + 5 * 0.2 (segon tram);  --> dues linies
           
            trams = line_item_type.price_interval.price_interval_stretches.all().order_by('stretch')
            
            # mirem les unitats (line_item_type.price_interval.units): 
            # si són "m3" vol dir que ho hem de fer sobre el consum, 
            # si són "dm" vol dir que ho hem de fer sobre el diametre del comptador
            
            # canviem la quantitat si és per diametre del comptador
            if line_item_type.price_interval.units == 'dm_met':
                try:
                    quantitat = meter_caliber
                except Exception as e:
                    raise Exception(f"Error en calcular preu - meter caliber: {e}")
            if line_item_type.price_interval.units == 'dm_con':
                try:
                    quantitat = connection_diameter if connection_diameter else 63
                except Exception as e:
                    raise Exception(f"Error en calcular preu - connection diameter: {e}")

            show_all_consumption_trams = should_show_all_consumption_trams()
            previous_stretch_end = 0
            for tram in trams:
                if quantitat <= 0 and tram.stretch != 1: # vol dir que ja li hem restat tot i ja no hi ha més a facturar
                    if show_all_consumption_trams:
                        # Mostrem aquest tram (i la resta) sense consum, en lloc de tallar el bucle
                        empty_tram_name = f"{line_item_type_name} - {tram.name_stretch}"
                        if tram.end_stretch and tram.end_stretch < 9999:
                            empty_tram_name += f"; Límit: {tram.end_stretch}"
                        linies.append(create_line_item_data(contract, line_item_type, tram.price if tram.price else tram.proportional_price, 0, 0, empty_tram_name, empty_tram_name, True, reading, None, tram.stretch, tram.end_stretch, correction_multiplier, units_adjusted))
                        previous_stretch_end = tram.end_stretch
                        continue
                    if line_item_type.always_show:
                        if previous_stretch_end <= 0:
                            linies.append(create_line_item_data(contract, line_item_type, tram.price if tram.price else tram.proportional_price, 0, 0, line_item_type_name, line_item_type_name, True, reading, None, tram.stretch, tram.end_stretch, correction_multiplier, units_adjusted))
                    break

                # mirem si hi ha algun corrector de tram
                price_original = tram.price
                price_proporcional_original = tram.proportional_price
                end_stretch_original = tram.end_stretch

                tram.price, tram.proportional_price, end_stretch_original, adjustment_name, corrected_price_tram, tram_adjustments = calc_correctors_tram(variables, variable_types, tram, line_item_type.id, reading_batch_id)


                if tram_adjustments:
                    applied_adjustments.extend(tram_adjustments)
                if line_item_type.price_interval.units == 'm3' and (line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated):
                    if ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination) or line_item_type.is_prorated) and billing_days:
                        if dies_consum and dies_consum > 0:
                            # print("\n\ndies_consum/billing_days: ", dies_consum/billing_days)

                            # If two billing ranges are active, we force prorating
                            if correction_ptg < min_correction or correction_ptg > max_correction or change_date is not None:
                                # print("passed correction")
                                end_stretch_original = end_stretch_original * (correction_ptg)
                            end_stretch_original = math.ceil(end_stretch_original)
                
                
                stretch_width = math.ceil(end_stretch_original - previous_stretch_end)

                # avaluem el tram:
                name = f"{line_item_type_name} - {tram.name_stretch};"
                if adjustment_name:
                    name += f" - {adjustment_name}"
                
                if end_stretch_original < 9999:
                    
                    name += f" Límit: {end_stretch_original}"
                if description:
                    name = description
                
                # Si el tram té preu fix 0 i preu proporcional 0, el tractem com a proporcional per mantenir les unitats de consum
                tram_preu_zero = price_original == 0 and price_proporcional_original == 0

                if stretch_width <= quantitat: # vol dir que el tram és ample 30 i tenim quantitat de 35, hem de facturar 30 unitats del tram.
                    if price_original:
                        price_unit = tram.price
                        units = 1  # 1 unitat perquè és preu fix
                        if line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated:
                            if ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination) or line_item_type.is_prorated) and billing_days:
                                if dies_consum and dies_consum > 0:
                                    if correction_ptg < min_correction or correction_ptg > max_correction:
                                        units = units * (correction_ptg)
                        if line_item_type.quantity and line_item_type.quantity.token in ['consum', 'diferencia_fuita_consum', 'diferencia_fuita']:
                            units = round_ceil(units, to_int=True)
                        units = round_ceil(units or 0)
                        price = float(price_unit) * float(units)
                        name = f"{line_item_type_name} - {tram.name_stretch} "
                        
                        if adjustment_name:
                            name += f" - {adjustment_name}"
                        if end_stretch_original < 9999:
                            name += f" ({stretch_width} {line_item_type.price_interval.units}); Límit: {end_stretch_original}" # informem de la quantitat
                        if corrected_price_tram:
                            price = corrected_price_tram
                        
                        linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, name, name, True, reading, applied_adjustments, tram.stretch, end_stretch_original, correction_multiplier, units_adjusted))
                    elif price_proporcional_original or tram_preu_zero:
                        price_unit = tram.proportional_price
                        units = stretch_width
                        if es_prorratejat:
                            units = dies_consum
                            price_unit = price_unit / prorratejat_quantitat
                        """ if line_item_type.active_choice or line_item_type.inactive_choice:
                            if (line_item_type.active_choice == 'DAYS' or line_item_type.inactive_choice == 'DAYS') and billing_days:
                                if dies_consum and dies_consum > 0:
                                    units = units * (dies_consum/billing_days) """
                        if line_item_type.quantity and line_item_type.quantity.token in ['consum', 'diferencia_fuita_consum', 'diferencia_fuita']:
                            units = round_ceil(units, to_int=True)
                        units = round_ceil(units or 0)
                        price = float(price_unit) * float(units)
                        if corrected_price_tram:
                            price = corrected_price_tram
                        # print("name: ", name)
                        linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, name, name, True, reading, applied_adjustments, tram.stretch, end_stretch_original, correction_multiplier, units_adjusted))
                else: # vol dir que el tram és 30 i tenim quantitat de 5, hem de facturar 5 unitats.
                    name = f"{line_item_type_name} - {tram.name_stretch} ({quantitat} {line_item_type.price_interval.units})" # informem de la quantitat
                    if end_stretch_original < 9999:
                        name += f"; Límit: {end_stretch_original}"
                    if description:
                        name = description

                    if price_original is not None and not price_proporcional_original and not tram_preu_zero:
                        price_unit = tram.price
                        units = 1  # 1 unitat perquè és preu fix
                        if line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated:
                            if ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination) or line_item_type.is_prorated) and billing_days:
                                if dies_consum and dies_consum > 0:
                                    if correction_ptg < min_correction or correction_ptg > max_correction:
                                        units = units * (correction_ptg)
                        if line_item_type.quantity and line_item_type.quantity.token in ['consum', 'diferencia_fuita_consum', 'diferencia_fuita']:
                            units = round_ceil(units, to_int=True)
                        units = round_ceil(units or 0)
                        price = float(price_unit) * float(units)
                        if corrected_price_tram:
                            price = corrected_price_tram
                        print("add new line item: ", name)
                        linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, name, name, True, reading, applied_adjustments, tram.stretch, end_stretch_original, correction_multiplier, units_adjusted))
                        print(linies)
                    elif price_proporcional_original is not None:
                        price_unit = tram.proportional_price
                        units = quantitat
                        
                        """ if line_item_type.active_choice or line_item_type.inactive_choice:
                            if (line_item_type.active_choice == 'DAYS' or line_item_type.inactive_choice == 'DAYS') and billing_days:
                                if dies_consum and dies_consum > 0:
                                    units = units * (dies_consum/billing_days) """
                        if line_item_type.quantity and line_item_type.quantity.token in ['consum', 'diferencia_fuita_consum', 'diferencia_fuita']:
                            units = round_ceil(units, to_int=True)
                        units = round_ceil(units or 0)
                        price = float(price_unit) * float(units)
                        if corrected_price_tram:
                            price = corrected_price_tram
                        linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, name, name, True, reading, applied_adjustments, tram.stretch, end_stretch_original, correction_multiplier, units_adjusted))
                
                # quantitat -= end_stretch_original
                quantitat -= stretch_width
                previous_stretch_end = end_stretch_original

                

        elif line_item_type.price_variable: # preu variable 
            
            # Ens ve una taula (amb preu proporcional): tram, limit, preu prop.: --> tram 1; 30; 0.1€;  tram 2; 60; 0.2€;  
            # Si el consum és 20, el preu serà 20 * 0.1
            # Si el consum és 35, el preu serà 35 * 0.2 (segon tram);  --> una sola linia

            # Ens ve una taula (amb preu fix): tram, limit, preu.: --> tram 1; 30; 8€;   tram 2; 60; 16€;
            # Si el consum és 20, el preu serà 8€
            # Si el consum és 35, el preu serà 16€ (segon tram);  --> una sola linia

            trams = line_item_type.price_variable.price_variable_interval_stretches.all().order_by('stretch')

            # mirem les unitats (line_item_type.price_interval.units): 
            # si són "m3" vol dir que ho hem de fer sobre el consum, 
            # si són "dm" vol dir que ho hem de fer sobre el diametre del comptador
            
            quantitat = round(consum)
            es_prorratejat = False
            if line_item_type.price_variable.units == 'dm_met':
                try:
                    quantitat = meter_caliber
                except Exception as e:
                    raise Exception(f"Error en calcular preu - meter caliber: {e}")
            if line_item_type.price_variable.units == 'dm_con':
                try:
                    quantitat = connection_diameter if connection_diameter else 63
                except Exception as e:
                    raise Exception(f"Error en calcular preu - connection diameter: {e}")
            if line_item_type.quantity and line_item_type.quantity.token == 'dies_consum':
                quantitat = dies_consum
                es_prorratejat = line_item_type.is_prorated
            for tram in trams:
                
                
                # mirem si hi ha algun corrector de tram
                price_original = tram.price
                price_proporcional_original = tram.proportional_price
                end_stretch_original = tram.end_stretch
                tram.price, tram.proportional_price, end_stretch_original, adjustment_name, corrected_price_tram, tram_adjustments = calc_correctors_tram(variables, variable_types, tram, line_item_type.id, reading_batch_id)
                if tram_adjustments:
                    applied_adjustments.extend(tram_adjustments)
                
                if line_item_type.price_variable.units == 'm3' and (line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated or correction_multiplier):
                    if ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination) or line_item_type.is_prorated or correction_multiplier) and billing_days:
                        if dies_consum and dies_consum > 0:
                            if correction_multiplier:
                                end_stretch_original = end_stretch_original * correction_multiplier
                            elif correction_ptg < min_correction or correction_ptg > max_correction:
                                end_stretch_original = math.ceil(end_stretch_original * (correction_ptg))
                if quantitat > end_stretch_original: # vol dir que estem superant el tram, hem de passar al següent
                    continue

                name = f"{line_item_type_name} - {tram.name_stretch}"
                if adjustment_name:
                    name += f" - {adjustment_name}"

                if price_original:
                    price_unit = tram.price
                    units = 1 # 1 unitat perquè és preu fix
                    if line_item_type.active_choice or line_item_type.inactive_choice or line_item_type.is_prorated:
                        if ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination) or line_item_type.is_prorated) and billing_days:
                            if dies_consum and dies_consum > 0:
                                if correction_ptg < min_correction or correction_ptg > max_correction:
                                    units = units * (correction_ptg)
                    
                    #no longer handling consumption, but 1
                    """ if line_item_type.quantity and line_item_type.quantity.token == 'consum':
                        units = round(units) """
                    units = round_ceil(units or 0)    
                    price = float(price_unit) * float(units)
                    if corrected_price_tram:
                        price = corrected_price_tram
                    if es_prorratejat:
                        units = dies_consum
                        price_unit = price_unit / prorratejat_quantitat
                    name += f" ({ quantitat } {line_item_type.price_variable.units})" # informem de la quantitat
                    
                    linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, name, "", True, reading, applied_adjustments, tram.stretch, end_stretch_original, correction_multiplier, units_adjusted))
                elif price_proporcional_original:
                    price_unit = tram.proportional_price
                    units = quantitat
                    if es_prorratejat:
                        units = dies_consum
                        price_unit = price_unit / prorratejat_quantitat
                    """ if line_item_type.active_choice or line_item_type.inactive_choice:
                        if (line_item_type.active_choice == 'DAYS' or line_item_type.inactive_choice == 'DAYS') and billing_days:
                            if dies_consum and dies_consum > 0:
                                units = units * (dies_consum/billing_days) """
                    if line_item_type.quantity and line_item_type.quantity.token in ['consum', 'diferencia_fuita_consum', 'diferencia_fuita']:
                        units = round_ceil(units, to_int=True)
                    units = round_ceil(units or 0)
                    price = float(price_unit) * float(units)
                    name = f"{line_item_type_name} - {tram.name_stretch}"
                    if corrected_price_tram:
                        price = corrected_price_tram
                    if adjustment_name:
                        name += f" - {adjustment_name}"
                    
                    linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, name,"", True, reading, applied_adjustments, tram.stretch, end_stretch_original, correction_multiplier, units_adjusted))
                break


        elif line_item_type.formula:
            
            formula = line_item_type.formula
            # print("\n\n IN FORMULA")
            # print(formula)

            """ if "%invoice.total_final" in formula:
                invoice_total_final = sum(
                    line_item['total'] for line_item in existing_line_items
                )
                formula = formula.replace("%invoice.total_final", str(invoice_total_final))
                # print(formula) """

            #matches = re.findall(r'%product\.(\w)', formula)
            matches = re.findall(r'%product\.([\w]+)', formula)
            products = []
            formula_fixed = formula
            if matches:
                for match in matches:
                    product = Product.objects.get(token=match)
                    products.append(product)
                
                related_prices = {}
                for line_item in existing_line_items:
                    if line_item['product'] in products:
                        token = line_item['product'].token
                        # Si un producte té trams/intervals (diverses línies), cal usar el sumatori
                        # del producte (no només l'últim tram).
                        related_prices[token] = related_prices.get(token, 0) + float(line_item.get('price') or 0)
                
                # Prepare the formula for evaluation
                for product in products:
                    token = product.token
                    if token in related_prices:
                        formula = formula.replace(f'%product.{token}', str(related_prices[token]))
                
                formula_fixed = replace_percentage(formula)
                
                # print(f"Evaluating formula: {formula_fixed}")
                
            try:
                if formula_fixed is not None:
                    formula_result = evaluate_formula(formula_fixed, variables)
                # print(f"Formula result: {formula_result}")
            except Exception as e:
                raise Exception(f"Error evaluating formula {formula_fixed}: {e}") 
            
            price_unit = formula_result
            og_price_unit = price_unit
            
            price_unit, description, cal_adjustments = calc_correctors_price(line_item_type, price_unit, variables, variable_types, contract, reading_batch_id) # mirem si hi ha una correcció de preu
            if cal_adjustments:
                applied_adjustments.extend(cal_adjustments)
            if prev_invoice:
                if description:
                    description += f" FACTURA PARE: {prev_invoice.serie_final}"
                else:
                    description = f"FACTURA PARE: {prev_invoice.serie_final}"
            units = 1

            if es_prorratejat:
                units = dies_consum
                price_unit = price_unit / prorratejat_quantitat
            
            if line_item_type.active_choice or line_item_type.inactive_choice:
                if ((line_item_type.active_choice == 'DAYS' and is_first_invoice) or (line_item_type.inactive_choice == 'DAYS' and is_termination)) and billing_days:
                    if dies_consum and dies_consum > 0:
                        if correction_ptg < min_correction or correction_ptg > max_correction:
                            units = units * (correction_ptg)
            
            if line_item_type.quantity and line_item_type.quantity.token == 'consum':
                units = round_ceil(units, to_int=True)
            units = round_ceil(units or 0)
            price = float(price_unit) * float(units)
            
            linies.append(create_line_item_data(contract, line_item_type, price_unit, price, units, None, description, True, reading, applied_adjustments, 0, None, correction_multiplier, units_adjusted))
            
        else:
            return None 
    except Exception as e:
        raise Exception(f"Error en calcular preu: {e}")
    
    # print(f"Price: {price}; Units: {units}; Price unit: {price_unit}")
    # print(f"Linies: {linies}")
    return linies


def create_from_lineitemtype_connection(connection, line_item_type, existing_line_items=None):
    quantitat = 1
    price_unit = 0
    price = 0
    units = 0

    linies = []

    invoice_lang = getattr(connection, 'language', None) or settings.LANGUAGE_CODE
    line_item_type_name = _translated_name(line_item_type, invoice_lang, line_item_type.name)

    try:
        if connection and connection.diameter and connection.diameter.token:
            connection_diameter = int(connection.diameter.token)
        else:
            # Use default connection diameter if not available
            connection_diameter = get_default_connection_diameter_value()
        
        # print("line_item_type: ", line_item_type)
        # print("price_interval: ", line_item_type.price_interval)
        # print("price_variable: ", line_item_type.price_variable)
        # print("price: ", line_item_type.price)
        # print("proportional_price: ", line_item_type.proportional_price)
        # print("formula: ", line_item_type.formula)
        
        
        
        if line_item_type.price_interval: 
            
            trams = line_item_type.price_interval.price_interval_stretches.all()

            # canviem la quantitat si és per diametre del comptador
            if line_item_type.price_interval.units == 'dm_con':
                try:
                    quantitat = connection_diameter
                except Exception as e:
                    raise Exception(f"Error en calcular preu - diametre d'escomesa: {e}")
            
            
            for tram in trams:
                # print("\n\ntram")
                # print(tram.__dict__)
                if quantitat <= 0: 
                    break
                # print("\n\nquantitat")
                # print(quantitat)
                price_original = tram.price
                price_proporcional_original = tram.proportional_price
                
                tram.price, tram.proportional_price, tram.end_stretch, adjustment_name, corrected_price, _ = calc_correctors_tram({}, {}, tram, line_item_type.id)

                name = f"{line_item_type_name} - {tram.name_stretch};"
                if adjustment_name:
                    name += f" - {adjustment_name}"
                name += f" Límit: {tram.end_stretch}"
                
                # print("tram end")
                # print(tram.end_stretch)
                if tram.end_stretch <= quantitat:
                    # 
                    if price_original:
                        price_unit = tram.price
                        units = 1 
                        price = float(price_unit) * float(units)
                        name = f"{line_item_type_name} - {tram.name_stretch} "
                        if adjustment_name:
                            name += f" - {adjustment_name}"
                        name += f" ({ quantitat } {line_item_type.price_interval.units}); Límit: {tram.end_stretch}" # informem de la quantitat
                        linies.append(create_line_item_data(None, line_item_type, price_unit, price, units, name, ""))
                    elif price_proporcional_original:
                        price_unit = tram.proportional_price
                        units = tram.end_stretch
                        units = round_ceil(units or 0)
                        price = float(price_unit) * float(units)
                        linies.append(create_line_item_data(None, line_item_type, price_unit, price, units, name, ""))
                    break #nomès agafa el preu del seu calibre en comptes d'anar sumant
                else:
                    if price_original:
                        price_unit = tram.price
                        units = 1
                        price = float(price_unit) * float(units)
                        name = f"{line_item_type_name} - {tram.name_stretch} ({ quantitat } {line_item_type.price_interval.units}); Límit: {tram.end_stretch}" # informem de la quantitat
                        linies = [(create_line_item_data(None, line_item_type, price_unit, price, units, name, ""))]
                    elif price_proporcional_original:
                        price_unit = tram.proportional_price
                        units = quantitat
                        units = round_ceil(units or 0)
                        price = float(price_unit) * float(units)
                        linies = [(create_line_item_data(None, line_item_type, price_unit, price, units, name))]
        
        elif line_item_type.price:
            price_unit = line_item_type.price
            units = 1
            price = float(price_unit) * float(units)
            linies = [(create_line_item_data(None, line_item_type, price_unit, price, units, line_item_type_name))]
            
        elif line_item_type.proportional_price:
            price_unit = line_item_type.proportional_price
            units = 1
            price = float(price_unit) * float(units)
            linies = [(create_line_item_data(None, line_item_type, price_unit, price, units, line_item_type_name))]
        elif line_item_type.price_variable: # preu variable 
            
            trams = line_item_type.price_variable.price_variable_interval_stretches.all().order_by('stretch')

            
            # quantitat = round(consum)
            es_prorratejat = False
            
            if line_item_type.price_variable.units == 'dm_met':
                try:
                    # TODO: get the meter caliber from the connection if there is one, this is a quick fix for now
                    if MeterCaliber.objects.filter(is_default=True).exists():
                        quantitat = MeterCaliber.objects.filter(is_default=True).first().name
                    else:
                        quantitat = 13
                except Exception as e:
                    raise Exception(f"Error en calcular preu - meter caliber: {e}")
            if line_item_type.price_variable.units == 'dm_con':
                try:
                    quantitat = connection_diameter
                except Exception as e:
                    raise Exception(f"Error en calcular preu - connection diameter: {e}")
            # if line_item_type.quantity and line_item_type.quantity.token == 'dies_consum':
            #     quantitat = dies_consum
            #     es_prorratejat = line_item_type.is_prorated
            for tram in trams:
                
                
                # mirem si hi ha algun corrector de tram
                price_original = tram.price
                price_proporcional_original = tram.proportional_price
                end_stretch_original = tram.end_stretch
                
                tram.price, tram.proportional_price, end_stretch_original, adjustment_name, corrected_price_tram, _ = calc_correctors_tram([], [], tram, line_item_type.id)
                
                name = f"{line_item_type_name} - {tram.name_stretch}"
                if adjustment_name:
                    name += f" - {adjustment_name}"

                if price_original:
                    price_unit = tram.price
                    units = 1 # 1 unitat perquè és preu fix
                    if line_item_type.quantity and line_item_type.quantity.token == 'consum':
                        units = round(units)
                    units = round_ceil(units or 0)
                    price = float(price_unit) * float(units)
                    if corrected_price_tram:
                        price = corrected_price_tram
                    name += f" ({ quantitat } {line_item_type.price_variable.units})" # informem de la quantitat
                    
                    linies.append(create_line_item_data(None, line_item_type, price_unit, price, units, name, ""))
                elif price_proporcional_original:
                    price_unit = tram.proportional_price
                    units = quantitat
                    
                    if line_item_type.quantity and line_item_type.quantity.token == 'consum':
                        units = round_ceil(units, to_int=True)
                    units = round_ceil(units or 0)
                    price = float(price_unit) * float(units)
                    name = f"{line_item_type_name} - {tram.name_stretch}"
                    if corrected_price_tram:
                        price = corrected_price_tram
                    if adjustment_name:
                        name += f" - {adjustment_name}"
                    
                    linies.append(create_line_item_data(None, line_item_type, price_unit, price, units, name,""))
                break
        else:
            return None 
    except Exception as e:
        raise Exception(f"Error en calcular preu: {e}")
    
    
    return linies

def replace_match(match):
    percentage_value = float(match.group(1))  
    return f"({percentage_value / 100}) *"  

def replace_percentage(formula):

    modified_formula = re.sub(r'(\d+)%', replace_match, formula)
    return modified_formula

import contextlib
import contextvars
import datetime
import os
import math
import random
import logging

from billing.models import Invoice
from contract.models import VariableType
from pricing.models import AdjustmentCondition, AdjustmentIntervalStretch

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def calc_consumption_responsible(contract, consumption):
    if contract.total_persons == 0:
        return True
    if consumption == 0:
        return True
    return True if ( (consumption / contract.total_persons) < 100) else False

def evaluate_formula(formula, variables):
    # Sort variables by length (longest first) to avoid partial replacements
    sorted_variables = sorted(variables.items(), key=lambda x: len(x[0]), reverse=True)
    for key, value in sorted_variables:
        formula = formula.replace(f'%{key}', str(value))
    try:
        result = eval(formula)
        # logger.debug("Evaluated formula '%s' with result: %s", formula, result)
        return result
    except Exception as e:
        logger.error(f"Error evaluating adj formula {formula}: {e}")
        return False

def convert_value(value, data_type):
    if not value: return None
    if data_type == 'bool':
        return value.lower() == 'true'
    elif data_type == 'int':
        return int(value)
    return value


def _to_comparable_number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        normalized = value.strip().replace(',', '.')
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


# Clau interna de variable_types amb els tokens de VariableType vulnerables, perquè
# adjustment_eval_conditions no hagi de consultar-los a cada condició.
VULNERABLE_TOKENS_KEY = '_vulnerable_tokens'


# Dades de configuració compartides per tota una facturació (vegeu billing_run_cache_scope).
_billing_run_cache = contextvars.ContextVar('billing_run_cache', default=None)


def _run_cache(name):
    """Diccionari `name` de la facturació en curs, o None fora d'un billing_run_cache_scope."""
    run = _billing_run_cache.get()
    if run is None:
        return None
    return run.setdefault(name, {})


@contextlib.contextmanager
def billing_run_cache_scope():
    """
    Comparteix entre tots els contractes d'una facturació els VariableType i els ajustaments
    (amb condicions i intervals). S'acota a la facturació (i no a nivell de mòdul) perquè els
    workers de llarga durada no facin servir configuració obsoleta si es modifica.
    Es pot fer servir com a decorador o amb `with`.
    """
    if _billing_run_cache.get() is not None:
        yield  # ja som dins d'un scope (crides niades)
        return
    token = _billing_run_cache.set({})
    try:
        yield
    finally:
        _billing_run_cache.reset(token)


def _load_variable_types():
    all_variable_types = list(VariableType.objects.all())
    return {
        'variable_types': all_variable_types,
        'vulnerable_tokens': {vt.token for vt in all_variable_types if vt.is_vulnerable},
    }


def get_variable_types_data():
    """
    Dins d'un billing_run_cache_scope es consulten una sola vegada per a tots els contractes;
    fora d'ell, a cada crida (un cop per contracte via get_contract_variables_cache).
    """
    cache = _run_cache('variable_types')
    if cache is None:
        return _load_variable_types()
    if 'data' not in cache:
        cache['data'] = _load_variable_types()
    return cache['data']


def _preload_adjustments(adjustments):
    """
    Carrega en bloc les condicions i si tenen intervals d'una llista d'ajustaments
    (2 consultes en total, en lloc de 2 per ajustament).
    """
    conditions_cache = _run_cache('adjustment_conditions')
    stretches_cache = _run_cache('adjustment_has_stretches')
    if conditions_cache is None:
        conditions_cache, stretches_cache = {}, {}

    pending = [adj.pk for adj in adjustments if adj.pk not in conditions_cache]
    if pending:
        conditions_by_adj = {pk: [] for pk in pending}
        for condition in AdjustmentCondition.objects.filter(adjustment_id__in=pending).order_by('position'):
            conditions_by_adj[condition.adjustment_id].append(condition)
        conditions_cache.update(conditions_by_adj)

        with_stretches = set(
            AdjustmentIntervalStretch.objects.filter(adjustment_id__in=pending).values_list('adjustment_id', flat=True)
        )
        stretches_cache.update({pk: pk in with_stretches for pk in pending})

    for adj in adjustments:
        adj._billing_conditions = conditions_cache[adj.pk]
        adj._billing_has_stretches = stretches_cache[adj.pk]
    return adjustments


def get_line_item_type_adjustments(line_item_type):
    """Equivalent a line_item_type.adjustments.all().order_by('position'), un cop per facturació."""
    cache = _run_cache('line_item_type_adjustments')
    if cache is not None and line_item_type.pk in cache:
        return cache[line_item_type.pk]
    adjustments = _preload_adjustments(list(
        line_item_type.adjustments.select_related('operation', 'variable_calculation', 'variable_type').order_by('position')
    ))
    if cache is not None:
        cache[line_item_type.pk] = adjustments
    return adjustments


def get_tram_adjustments(tram, line_item_type_id):
    """
    Equivalent a tram.adjustments.filter(adjustment__line_item_type__id=...).order_by('adjustment__position'),
    un cop per facturació. Els trams es modifiquen durant el càlcul, però els intervals no.
    """
    cache = _run_cache('tram_adjustments')
    key = (tram._meta.label_lower, tram.pk, line_item_type_id)
    if cache is not None and key in cache:
        return cache[key]
    adj_intervals = list(
        tram.adjustments.filter(adjustment__line_item_type__id=line_item_type_id)
        .select_related('adjustment__operation', 'adjustment__variable_calculation', 'adjustment__variable_type')
        .order_by('adjustment__position')
    )
    _preload_adjustments([adj_interval.adjustment for adj_interval in adj_intervals if adj_interval.adjustment])
    if cache is not None:
        cache[key] = adj_intervals
    return adj_intervals


def get_adjustment_conditions(adjustment):
    """Condicions ordenades per posició; sense consulta si l'ajustament s'ha precarregat."""
    conditions = getattr(adjustment, '_billing_conditions', None)
    if conditions is None:
        conditions = list(adjustment.conditions.all().order_by('position'))
    return conditions


def adjustment_has_interval_stretches(adjustment):
    has_stretches = getattr(adjustment, '_billing_has_stretches', None)
    if has_stretches is None:
        has_stretches = adjustment.adjustment_interval_stretches.exists()
    return has_stretches


def get_contract_variables_cache(contract):
    """
    Variables del contracte i tipus de variable carregats una sola vegada per instància
    de contracte (abans es consultaven a cada línia de factura i a cada ajustament).
    La vigència per dates es continua avaluant a cada crida de generate_variables.
    """
    cache = getattr(contract, '_billing_variables_cache', None)
    if cache is None:
        variable_types_data = get_variable_types_data()
        # Es manté la primera variable (per pk, com .first()) per a cada tipus.
        variables_by_type = {}
        for v in contract.variables.order_by('pk'):
            if v.type_id is not None and v.type_id not in variables_by_type:
                variables_by_type[v.type_id] = v
        cache = {
            'variable_types': variable_types_data['variable_types'],
            'variables_by_type': variables_by_type,
            'vulnerable_tokens': variable_types_data['vulnerable_tokens'],
            'invoice_totals': {},
        }
        contract._billing_variables_cache = cache
    return cache


def get_contract_variable(contract, variable_type):
    """Equivalent a contract.variables.filter(type=variable_type).first() sense consulta."""
    if not contract or not variable_type:
        return None
    return get_contract_variables_cache(contract)['variables_by_type'].get(variable_type.id)


def generate_variables(contract, consumption, consumption_days, consumption_leakage = None, consumption_responsible = None, invoice = None):
    # consumption_responsible = calc_consumption_responsible(contract, consumption)
    persons_min = contract.total_persons if contract and contract.total_persons > 3 else 3
    
    cache = get_contract_variables_cache(contract) if contract else None

    total_final = None
    if invoice:
        if cache is not None and invoice.pk in cache['invoice_totals']:
            total_final = cache['invoice_totals'][invoice.pk]
        else:
            total_final = invoice.total_final
            try:
                invoice_child = Invoice.objects.get(parent_invoice=invoice)
            except:
                invoice_child = None
            while invoice_child is not None:
                total_final += invoice_child.total_final
                try:
                    invoice_child = Invoice.objects.get(parent_invoice=invoice_child)
                except:
                    invoice_child = None
            if cache is not None:
                cache['invoice_totals'][invoice.pk] = total_final
    
    # print(f"\n\n\nTotal\n final: {total_final}")

    variables = {
        'contract.total_persons': contract.total_persons if contract else 3,
        'contract.persons': contract.total_persons if contract else 3,
        'contract.communication_type': contract.communication_type if contract and contract.communication_type else 'PAPER',
        'persons_min': persons_min,
        'consumption': consumption,
        'consumption_days': consumption_days,
        'consumption_responsible': consumption_responsible,
        'invoice.total_final': total_final,
    }
    
    variable_types = {
        'contract.client_type': contract.client_type if contract and contract.client_type else None,
        'contract.use_type': contract.use_type if contract and contract.use_type else None,
    }

    if consumption_leakage:
        variables['consumption_leakage'] = consumption_leakage

    # if contract:
    #     for var in contract.variables.all():
    #         print(f"Variable: {var} and token: {var.token} and value: {var.value}")
    
    if contract:
        variable_types[VULNERABLE_TOKENS_KEY] = cache['vulnerable_tokens']
        contract_variables_by_type = cache['variables_by_type']

        for variable_type in cache['variable_types']:
            variable = contract_variables_by_type.get(variable_type.id)
            
            if variable:
                # Comprovem si la variable està dins del rang de dates
                avui = datetime.date.today()
                if variable.start_at and variable.end_at:
                    if not (variable.start_at <= avui <= variable.end_at):
                        variable = None # borrem la variable si no està dins del rang de dates
                elif variable.start_at and avui < variable.start_at:
                    variable = None # borrem la variable si no està dins del rang de dates
                elif variable.end_at and avui > variable.end_at:
                    variable = None # borrem la variable si no està dins del rang de dates  

            if variable:
                variables[f"variable.{variable_type.token}"] = convert_value(variable.value, variable_type.data_type)
            else:
                variables[f"variable.{variable_type.token}"] = 0
    
    return variables, variable_types

def adjustment_eval_conditions(adjustment, variables, variable_types, reading_batch_id = None): 
    # contract, supply_point, consumption, consumption_days, consumption_leakage, consumption_responsible,
    # print(f"evaluating conditions for adjustment {adjustment.token}")	
    # variables, variable_types = generate_variables(contract, consumption, consumption_days, consumption_leakage, consumption_responsible)
    # print(f"Variables: {variables}")
    # logger.debug("Variables: %s", variables)  # Debugging line

    debug = False

    is_vulnerable = False
    for condition in get_adjustment_conditions(adjustment):

        is_vulnerable = False
        quantity_key = condition.quantity['value']

        try:
            var_token = None
            if isinstance(quantity_key, str):
                quantity_parts = quantity_key.split('.', 1)
                if len(quantity_parts) == 2 and quantity_parts[1]:
                    var_token = quantity_parts[1]

            if var_token:
                vulnerable_tokens = variable_types.get(VULNERABLE_TOKENS_KEY) if isinstance(variable_types, dict) else None
                if vulnerable_tokens is not None:
                    variables_vul = var_token in vulnerable_tokens
                else:
                    variables_vul = VariableType.objects.filter(is_vulnerable=True, token=var_token).exists()
                if variables_vul and condition.quantity['value'] in variables:
                    variable_value = variables.get(quantity_key)
                    if (isinstance(variable_value, str) and variable_value.lower() == 'true') or (isinstance(variable_value, bool) and variable_value is True):
                        is_vulnerable = True
        except Exception as e:
            print(f"Error evaluating vulnerable condition flag: {e}")

            # print("variables: ", variables)

        if quantity_key == 'reading_batch_id':
            if ',' in condition.formula:
                formula_parts = condition.formula.split(',')
                if str(reading_batch_id) not in formula_parts:
                    return False, False
            else:
                if str(reading_batch_id) != condition.formula:
                    return False, False
            return True, is_vulnerable
        if condition.quantity['value'] in variables:
            quantity_value = variables.get(quantity_key)

            # print("condition: ", condition.operation)
            # logger.debug("Evaluating condition: %s", condition)  # Debugging line
            # logger.debug("Condition operation: %s", condition.operation)  # Debugging line
            # logger.debug("Quantity value get: %s", quantity_value)  # Debugging line
            

            
            if condition.operation == 'is_true':
                if not quantity_value:
                    return False, False
            elif condition.operation == 'is_false':
                if quantity_value:
                    return False, False
            elif condition.operation in ['eq', 'ne', 'gt', 'lt', 'ge', 'le']:
                if not condition.formula:
                    return False, False
                formula_result = evaluate_formula(condition.formula, variables)
                # logger.debug("Formula result: %s", formula_result)  # Debugging line
                if condition.operation == 'eq' and not (quantity_value == formula_result):
                    return False, False
                elif condition.operation == 'ne' and not (quantity_value != formula_result):
                    return False, False
                elif condition.operation in ['gt', 'lt', 'ge', 'le']:
                    left_value = _to_comparable_number(quantity_value)
                    right_value = _to_comparable_number(formula_result)

                    # Mixed or non-numeric values cannot be ordered reliably.
                    if left_value is None or right_value is None:
                        return False, False

                    if condition.operation == 'gt' and not (left_value > right_value):
                        return False, False
                    elif condition.operation == 'lt' and not (left_value < right_value):
                        return False, False
                    elif condition.operation == 'ge' and not (left_value >= right_value):
                        return False, False
                    elif condition.operation == 'le' and not (left_value <= right_value):
                        return False, False
            elif condition.operation == 'is_not_null':
                if quantity_value is None or quantity_value == 0:
                    return False, False
            elif condition.operation == 'is_null':
                if quantity_value is not None and quantity_value != 0:
                    return False, False
            # Add more operations as needed
        elif condition.quantity['value'] in variable_types:
            quantity_value = variable_types.get(quantity_key)
            if(quantity_value.token != condition.formula):
                return False, False
        else:
            return False, False
        

    if debug:
        print("--------------------------------is_vulnerable--------------------------------")
        print("is_vulnerable: ", is_vulnerable)
        print("--------------------------------is_vulnerable--------------------------------")
    return True, is_vulnerable
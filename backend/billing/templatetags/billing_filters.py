from datetime import date, datetime
from decimal import Decimal
from django import template
from django.utils import formats
from django.utils.translation import gettext as _
import re

register = template.Library()

@register.filter
def remove_useless_zeros(value):
    if not value:
        return value
    
    try:
        value_str = str(value)
        
        if ',' in value_str:
            parts = value_str.split(',')
            if len(parts) == 2:
                integer_part = parts[0]
                decimal_part = parts[1]
                
                decimal_part = decimal_part.rstrip('0')
                
                if not decimal_part:
                    return integer_part
                else:
                    return f"{integer_part},{decimal_part}"
            return value_str
        
        decimal_value = Decimal(value)
        if decimal_value == decimal_value.to_integral():
            before_replace = decimal_value.quantize(Decimal(1))
        else:
            before_replace = decimal_value.normalize()
        
        return str(before_replace).replace(".", ",")
            
    except:
        return str(value).replace(".", ",")

QUARTER_LABELS = {
    1: "Gener a Març",
    2: "Abril a Juny",
    3: "Juliol a Setembre",
    4: "Octubre a Desembre",
}

@register.filter
def quarter_period(value):
    """OBSOLET: usa `invoice_period` (rep la factura, no una data).

    Retorna el trimestre natural que conté la data rebuda, cosa que **no** és el
    període facturat: les factures s'emeten el mes següent al final del període
    (una factura emesa el 05/08/2026 correspon a maig-juny-juliol, no a
    juliol-agost-setembre). A més les etiquetes són sempre en català i no distingeix
    les factures puntuals, que no tenen cap període. Es manté només perquè les
    plantilles de client desplegades que encara el referencien no petin.
    """
    if not value:
        return ""

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return ""

    quarter = (value.month - 1) // 3 + 1
    return f"{QUARTER_LABELS[quarter]} de {value.year}"


# Mesos que abasta un període de facturació segons Biller.period_type
# (billing/models.py::Biller.TYPE_CHOICES).
PERIOD_TYPE_MONTHS = {
    'mensual': 1,
    'bimestral': 2,
    'trimestral': 3,
    'quadrimestral': 4,
    'semestral': 6,
    'anual': 12,
}
DEFAULT_PERIOD_MONTHS = 3


def _is_consumption_invoice(invoice):
    """Una factura és de consum si el seu origen és el configurat a
    ConfigProject['origin_reading_token'] (per defecte 'aigua'). La resta
    (altes, canvis de nom, reconnexions, escomeses, recàrrecs de retorn...) són
    puntuals: no estan vinculades a cap període facturat.

    Es mira `origin` i no `readings`, perquè hi ha factures de consum sense
    lectures associades (factures importades, regularitzacions) que sí que tenen
    l'origen ben posat.
    """
    origin_token = getattr(getattr(invoice, 'origin', None), 'token', None)
    if not origin_token:
        return False
    return origin_token == get_config('origin_reading_token', 'aigua')


def _invoice_period_months(invoice):
    """Nombre de mesos que abasta el període facturat de la factura.

    Parteix de la periodicitat del facturador (trimestral si no es pot determinar,
    que és la més habitual) i la retalla amb els dies consumits quan aquests
    indiquen un període més curt: altes, canvis de comptador i baixes generen
    factures parcials dins d'un cicle trimestral (p. ex. 52 dies = 2 mesos, no 3).
    Mai no s'amplia per sobre de la periodicitat del facturador, que és la
    referència comercial del cicle.
    """
    biller = getattr(getattr(invoice, 'billing', None), 'biller', None)
    if biller is None:
        # Factures fora d'un lot: la periodicitat penja de la ruta del punt de
        # subministrament (mateix camí que billing/tasks.py::fill_invoice_periods).
        try:
            biller = invoice.contract.supply_point_default.property.route_position.route.biller
        except Exception:
            biller = None
    months = PERIOD_TYPE_MONTHS.get(getattr(biller, 'period_type', None), DEFAULT_PERIOD_MONTHS)

    consumption_days = invoice.consumption_days
    if not consumption_days:
        consumption_days = next(
            (r.consumption_days for r in invoice.readings.all() if r.consumption_days), None
        )
    if consumption_days and consumption_days > 0:
        months = min(months, max(1, round(consumption_days / 30)))

    return months


def _invoice_period_end(invoice):
    """(any, mes) de l'ÚLTIM mes del període facturat.

    Prioritat:
      1. El mes de la lectura més recent de la factura: és la dada real de
         tancament del període (una factura amb lectura del 07/07/2026 tanca el
         període al juliol).
      2. El mes de facturació (`billing_period_*`, o `issue_date` si no hi és)
         menys un: la factura s'emet el mes següent al final del període.
    """
    reading_dates = [r.reading_date for r in invoice.readings.all() if r.reading_date]
    if reading_dates:
        last = max(reading_dates)
        return last.year, last.month

    year = invoice.billing_period_year
    month = invoice.billing_period_month
    if not (year and month):
        if not invoice.issue_date:
            return None
        year, month = invoice.issue_date.year, invoice.issue_date.month

    return (year - 1, 12) if month == 1 else (year, month - 1)


def _month_name(year, month):
    """Nom del mes en l'idioma actiu, amb la inicial en majúscula."""
    name = formats.date_format(date(year, month, 1), 'F')
    return name[:1].upper() + name[1:]


@register.filter
def invoice_period(invoice):
    """Període facturat d'una factura, en l'idioma actiu.

    - Factures puntuals (no de consum): "Puntual", perquè no tenen període.
    - Períodes d'un sol mes: "Juliol de 2026".
    - Períodes de diversos mesos dins del mateix any: "Maig a Juliol de 2026".
    - Períodes que travessen l'any: "Novembre de 2025 a Gener de 2026".
    """
    if invoice is None:
        return ""

    try:
        if not _is_consumption_invoice(invoice):
            return _("Puntual")

        end = _invoice_period_end(invoice)
        if not end:
            return ""

        end_year, end_month = end
        months = _invoice_period_months(invoice)

        # Primer mes del període: (months - 1) mesos enrere respecte de l'últim.
        start_index = (end_year * 12 + (end_month - 1)) - (months - 1)
        start_year, start_month = divmod(start_index, 12)
        start_month += 1

        end_name = _month_name(end_year, end_month)
        if months <= 1:
            return _("%(month)s de %(year)s") % {'month': end_name, 'year': end_year}

        start_name = _month_name(start_year, start_month)
        if start_year == end_year:
            return _("%(start)s a %(end)s de %(year)s") % {
                'start': start_name, 'end': end_name, 'year': end_year,
            }
        return _("%(start)s de %(start_year)s a %(end)s de %(end_year)s") % {
            'start': start_name, 'start_year': start_year,
            'end': end_name, 'end_year': end_year,
        }
    except Exception:
        return ""


BILLER_INITIAL_MONTH = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _invoice_period_anchor(invoice):
    """(any, mes) que situa la factura dins d'un cicle del facturador."""
    year = getattr(invoice, 'billing_period_year', None)
    month = getattr(invoice, 'billing_period_month', None)
    if year and month and 1 <= int(month) <= 12:
        return int(year), int(month)
    reading_dates = [
        r.reading_date for r in invoice.readings.all() if getattr(r, 'reading_date', None)
    ]
    if reading_dates:
        last = max(reading_dates)
        return last.year, last.month
    return None


def _cycle_bounds_from_biller(year, month, biller):
    """Cicle complet definit per period_type i initial_month del facturador.

    El mes de la factura només diu en quin cicle cau. El rang el marca el
    facturador: trimestral des de gener és Gener-Març, Abril-Juny, etc.
    """
    interval = PERIOD_TYPE_MONTHS.get(getattr(biller, 'period_type', None))
    initial = BILLER_INITIAL_MONTH.get(getattr(biller, 'initial_month', None))
    if not interval or not initial:
        return None
    position = ((month - initial) % 12) % interval
    start_month = month - position
    start_year = year
    if start_month <= 0:
        start_month += 12
        start_year -= 1
    end_index = start_month + interval - 1
    end_year = start_year + (end_index - 1) // 12
    end_month = (end_index - 1) % 12 + 1
    return start_month, start_year, end_month, end_year


def _format_period_bounds(start_month, start_year, end_month, end_year):
    end_name = _month_name(end_year, end_month)
    if start_year == end_year and start_month == end_month:
        return f"{end_name}/{end_year}"
    start_name = _month_name(start_year, start_month)
    if start_year == end_year:
        return f"{start_name}-{end_name}/{end_year}"
    return f"{start_name}/{start_year}-{end_name}/{end_year}"


@register.filter
def invoice_biller_period(invoice):
    """Període del facturador, en format Abril-Juny/2026.

    Surt de period_type i initial_month. El mes de la factura només indica
    quin cicle és. Sense facturador al lot la fila no es pinta. No
    substitueix la variable de context `billing_period`.
    """
    if invoice is None:
        return ""

    try:
        if not _is_consumption_invoice(invoice):
            return ""
        biller = getattr(getattr(invoice, 'billing', None), 'biller', None)
        if biller is None:
            return ""
        anchor = _invoice_period_anchor(invoice)
        if not anchor:
            return ""
        bounds = _cycle_bounds_from_biller(anchor[0], anchor[1], biller)
        if not bounds:
            return ""
        return _format_period_bounds(*bounds)
    except Exception:
        return ""

@register.filter
def is_advanced_product(value):
    val_upper = str(value or '').upper()
    if 'CLAVEGUERAM' in val_upper: return False
    return any(kw in val_upper for kw in ['AIGUA', 'TAXA SERVEI', 'CANON', 'CÀNON'])

@register.filter
def format_eu(value, decimal_places=2):
    if not value and value != 0:
        return value
    
    try:
        # Ensure decimal_places is an integer
        if decimal_places is None:
            decimal_places = 2
        elif isinstance(decimal_places, str):
            try:
                decimal_places = int(decimal_places)
            except (ValueError, TypeError):
                decimal_places = 2
        else:
            decimal_places = int(decimal_places)
        
        decimal_value = Decimal(str(value))
        
        if decimal_places == 0:
            formatted_value = decimal_value.quantize(Decimal(1))
        else:
            quantizer = Decimal(10) ** -decimal_places
            formatted_value = decimal_value.quantize(quantizer)
        
        value_str = str(formatted_value)
        if '.' in value_str:
            integer_part, decimal_part = value_str.split('.')
        else:
            integer_part = value_str
            decimal_part = None
        
        is_negative = integer_part.startswith('-')
        if is_negative:
            integer_part = integer_part[1:]
        
        integer_with_separator = f"{int(integer_part or 0):,}".replace(",", ".")
        
        if is_negative:
            integer_with_separator = '-' + integer_with_separator
        
        if decimal_part and decimal_places > 0:
            return f"{integer_with_separator},{decimal_part}"
        else:
            return integer_with_separator
            
    except:
        return str(value)

@register.filter
def clean_address_suffix(value):
    """
    Removes the ', city - country' suffix from address strings.
    """
    if not value:
        return value
    cleaned = re.sub(r',\s*[^,\-]+\s*-\s*[^,\-]+\s*$', '', str(value))
    return cleaned.strip()

@register.filter
def format_iban(value):
    if not value:
        return value
    iban_str = str(value).replace(' ', '')
    return ' '.join(iban_str[i:i+4] for i in range(0, len(iban_str), 4))

def _item_attr(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _custom_order_value(item):
    value = _item_attr(item, 'custom_order', None)
    if value in (None, '', 0, '0'):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number != 0 else None


@register.filter
def prioritize_custom_order(items):
    if not items:
        return items
    return sorted(
        items,
        key=lambda item: (
            _custom_order_value(item) is None,
            _custom_order_value(item) or 0,
        ),
    )

def _is_leak_by_token(item):
    """Fuita confirmada per la configuració de la línia (quantity 'diferencia_fuita*')."""
    if not item:
        return False
    line_item_type = _item_attr(item, 'line_item_type')
    quantity = getattr(line_item_type, 'quantity', None) if line_item_type else None
    return str(getattr(quantity, 'token', '') or '').startswith('diferencia_fuita')

@register.filter
def is_leak_item(item):
    """
    El consum de fuita es factura a part (preu bonificat): no és una quota fixa
    ni un bloc de consum, i cal detectar-lo per no barrejar-lo amb la resta.
    El text es té en compte perquè hi ha línies de fuita antigues (o afegides
    manualment) sense el token de quantitat informat.
    """
    if not item:
        return False
    if _is_leak_by_token(item):
        return True
    text = f"{_item_attr(item, 'name', '') or ''} {_item_attr(item, 'description', '') or ''}"
    return 'FUITA' in text.upper()

@register.filter
def leak_label(item=None):
    return get_config('leak_line_label', "CONSUM PER FUITA") or "CONSUM PER FUITA"

@register.filter
def merge_water_readings(items):
    """
    Groups water items into a single virtual reading and assigns priorities.
    Returns items unchanged if advanced grouping is disabled.
    """
    if not items:
        return []
        
    advanced_grouping = get_config('invoice_apply_advanced_grouping', 'false').lower() == 'true'
    if not advanced_grouping:
        return items

    results = []
    for item in items:
        p_name = str(getattr(item, 'product_name', '') or '').upper()
        norm = p_name.replace('À', 'A').replace('Á', 'A').replace('È', 'E').replace('É', 'E').replace('Ì', 'I').replace('Í', 'I').replace('Ò', 'O').replace('Ó', 'O').replace('Ù', 'U').replace('Ú', 'U').replace('Ü', 'U')
        
        v_id = getattr(item, 'reading_id', None) or getattr(item, 'reading', None)
        v_prio = 10
        
        if advanced_grouping:
            # Group all water-related items into a single reading-based collective
            # so the priority filter can perform cross-product calculations (like Clavegueram).
            if any(kw in norm for kw in ['AIGUA', 'TAXA SERVEI', 'CANON', 'CLAVEGUERAM']):
                v_id = f"WR_{v_id}"
                v_prio = 1
        
        if isinstance(item, dict):
            item['v_reading'] = v_id
            item['v_reading_prio'] = v_prio
        else:
            setattr(item, 'v_reading', v_id)
            setattr(item, 'v_reading_prio', v_prio)
            
        results.append(item)
    return results

@register.filter
def group_by_order_priority(line_items, arg=None):
    if not line_items:
        return []
    
    def get_it_order(x):
        if isinstance(x, dict):
            val = x.get('product_order')
        else:
            val = getattr(x, 'product_order', 4000000)
        return val if val is not None else 4000000

    def get_product_name(x):
        if isinstance(x, dict):
            return str(x.get('product_name', '') or '')
        else:
            return str(getattr(x, 'product_name', '') or '')

    def get_item_name(x):
        if isinstance(x, dict): return x.get('name', '') or x.get('description', '') or ''
        return getattr(x, 'name', '') or getattr(x, 'description', '') or ''
        
    force_top_keyword = None
    origin_id = None
    if arg:
        try: origin_id = int(str(arg))
        except (ValueError, TypeError): force_top_keyword = str(arg)

    is_water = (origin_id == 1)
    advanced_grouping = get_config('invoice_apply_advanced_grouping', 'false').lower() == 'true'
    legacy_concept_order = get_config('invoice_legacy_concept_order_enabled', 'false').lower() == 'true'

    if origin_id is not None and not is_water:
        result_list = list(line_items)
        result_list.sort(key=lambda x: get_it_order(x))
        result = []
        for i, item in enumerate(result_list):
            result.append({'grouper': i, 'list': [item]})
        return result

    
    items_with_priority = []
    items_without_priority = []
    water_total_sum = Decimal('0')
    quota_sum = Decimal('0')
    water_var_sum = Decimal('0')
    
    if advanced_grouping:
        for item in line_items:
            # Rough identification for the pre-scan
            p_name = (item.get('product_name', '') if isinstance(item, dict) else getattr(item, 'product_name', '')) or ''
            p_name = (p_name or (item.get('product', {}).get('name', '') if isinstance(item, dict) else getattr(getattr(item, 'product', None), 'name', ''))) or ''
            p_name_u = str(p_name).upper()
            
            is_water = any(kw in p_name_u for kw in ['AIGUA', 'SERVEI']) and \
                       all(kw not in p_name_u for kw in ['CANON', 'CÀNON', 'CLAVEGUERAM'])
            
            if is_water:
                it_name = (item.get('name', '') if isinstance(item, dict) else getattr(item, 'name', '')) or ''
                it_desc = (item.get('description', '') if isinstance(item, dict) else getattr(item, 'description', '')) or ''
                
                # Normalize text
                full_norm = f"{it_name} {it_desc}".upper().replace('À', 'A').replace('Á', 'A').replace('È', 'E').replace('É', 'E').replace('Ì', 'I').replace('Í', 'I').replace('Ò', 'O').replace('Ó', 'O').replace('Ù', 'U').replace('Ú', 'U').replace('Ü', 'U')
                
                val = item.get('price', 0) if isinstance(item, dict) else getattr(item, 'price', 0)
                val_dec = Decimal(str(val or 0))
                
                # Sum everything for Water
                water_total_sum += val_dec
                
                # Identify if item is a Quota/Fixed part (same logic as in renaming).
                # La fuita mai és part fixa: és consum variable i ha de comptar
                # dins la base variable (p.ex. per calcular el Clavegueram).
                is_fixed = not is_leak_item(item) and (
                    any(kw in full_norm for kw in ['QUOTA', 'FIXA']) or
                    (any(kw in full_norm for kw in ['AIGUA', 'SERVEI']) and not it_desc)
                )
                
                if is_fixed:
                    quota_sum += val_dec

        water_var_sum = water_total_sum - quota_sum
    
    for item in line_items:
        if advanced_grouping:
            name = getattr(item, 'name', '') or getattr(item, 'description', '') or ''
            product_name = ''
            if isinstance(item, dict):
                product_name = item.get('product_name', '')
                if not product_name and item.get('product'):
                    product_name = getattr(item['product'], 'name', '')
            else:
                product_name = getattr(item, 'product_name', '') 
                if not product_name and hasattr(item, 'product') and item.product:
                    product_name = getattr(item.product, 'name', '')
            
            desc = getattr(item, 'description', '') if not isinstance(item, dict) else item.get('description', '')
            desc = desc or ''
            p_name_str = str(product_name or '').upper()
            
            # Refined match: Water (Aigua/Taxa) vs Clavegueram vs Canon
            p_name_u = p_name_str.upper()
            is_leak = is_leak_item(item)
            is_canon_prod = any(kw in p_name_u for kw in ['CANON', 'CÀNON'])
            is_clav_prod = 'CLAVEGUERAM' in p_name_u
            is_quota_prod = legacy_concept_order and not is_canon_prod and not is_clav_prod and \
                            'QUOTA' in p_name_u and 'SERVEI' in p_name_u
            is_water_prod = not is_canon_prod and not is_clav_prod and not is_quota_prod and \
                            any(kw in p_name_u for kw in ['AIGUA', "TAXA SERVEI", "QUOTA SERVEI"])
            
            if is_water_prod:
                product_name = "TAXA SERVEI D'AIGUA"
                if isinstance(item, dict): item['product_name'] = product_name
                else: setattr(item, 'product_name', product_name)
                
                # Normalize description for Quotas
                if not is_leak and any(kw in name.upper() for kw in ['AIGUA', 'SERVEI', 'QUOTA']) and not desc:
                    if isinstance(item, dict):
                        item['description'] = 'QUOTA DE SERVEI'
                        item['name'] = 'QUOTA DE SERVEI'
                    else:
                        setattr(item, 'description', 'QUOTA DE SERVEI')
                        setattr(item, 'name', 'QUOTA DE SERVEI')
                    name = 'QUOTA DE SERVEI'

            elif is_canon_prod:
                product_name = "CÀNON AIGUA (ACA)"
                if isinstance(item, dict): item['product_name'] = product_name
                else: setattr(item, 'product_name', product_name)
                
                if not is_leak and any(kw in name.upper() for kw in ['CANON', 'CÀNON']) and not desc:
                    limit = item.get('end_stretch') if isinstance(item, dict) else getattr(item, 'end_stretch', None)
                    if limit and limit < 999999:
                        new_label = f"VARIABLE (Límit: {limit})"
                    else:
                        new_label = 'FIXA'
                        
                    if isinstance(item, dict):
                        item['description'] = new_label
                        item['name'] = new_label
                    else:
                        setattr(item, 'description', new_label)
                        setattr(item, 'name', new_label)
                    name = new_label
            
            elif is_clav_prod:
                product_name = "TAXA SERVEI CLAVEGUERAM"
                if isinstance(item, dict): item['product_name'] = product_name
                else: setattr(item, 'product_name', product_name)
                
                # Check for exemption (original price/Import is 0)
                price_val = item.get('price') if isinstance(item, dict) else getattr(item, 'price', None)
                if price_val == 0 or price_val == Decimal('0'):
                    if isinstance(item, dict):
                        item['price_unit'] = 0.0
                        item['price'] = 0.0
                    else:
                        setattr(item, 'price_unit', 0.0)
                        setattr(item, 'price', 0.0)
                else:
                    # Municipality Rule: Clavegueram price unit is the sum of water variable imports
                    wv_float = float(water_var_sum)
                    if isinstance(item, dict): 
                        item['price_unit'] = wv_float
                        # Recalculate price if it was not provided (None)
                        if item.get('units') and price_val is None:
                            item['price'] = float(Decimal(str(item['units'])) * water_var_sum)
                    else: 
                        setattr(item, 'price_unit', wv_float)
                        if hasattr(item, 'units') and item.units and getattr(item, 'price', None) is None:
                            setattr(item, 'price', float(Decimal(str(item.units)) * water_var_sum))
            
            # La fuita té la seva pròpia etiqueta i no ocupa la de QUOTA DE SERVEI
            if is_leak and not desc and _is_leak_by_token(item):
                new_name = leak_label()
                if isinstance(item, dict):
                    item['description'] = new_name
                    item['name'] = new_name
                else:
                    setattr(item, 'description', new_name)
                    setattr(item, 'name', new_name)
                name = new_name

            if 'CLAVEGUERAM' in p_name_str:
                coefficient = None
                lit = getattr(item, 'line_item_type', None)
                if lit and lit.formula and '*' in lit.formula:
                    # Extract the second value after the '*' from the formula (e.g., "%product.1001 * 0.335")
                    parts = lit.formula.split('*')
                    if len(parts) > 1:
                        try:
                            coefficient = float(parts[1].strip().replace(',', '.'))
                        except (ValueError, TypeError):
                            pass
                
                if coefficient is None:
                    unit_override = get_config('invoice_clavegueram_unit_override', '')
                    if unit_override:
                        try:
                            coefficient = float(unit_override.replace(',', '.'))
                        except (ValueError, TypeError):
                            pass
                
                if coefficient is not None:
                    if isinstance(item, dict): 
                        item['units'] = coefficient
                    else: 
                        setattr(item, 'units', coefficient)

            # Assign Priority based on already identified categories
            is_forced = False
            priority_val = 0
            
            if is_quota_prod:
                is_forced = True
                priority_val = 0
            elif is_water_prod:
                is_forced = True
                priority_val = 1
            elif is_canon_prod:
                is_forced = True
                priority_val = 2
            elif is_clav_prod:
                is_forced = True
                priority_val = 3
            elif force_top_keyword and force_top_keyword != 'DISABLED':
                if force_top_keyword.upper() in name.upper() or force_top_keyword.upper() in p_name_str:
                    is_forced = True
                    priority_val = -1
            
            if is_forced:
                if isinstance(item, dict): item['_force_priority'] = priority_val
                else: setattr(item, '_force_priority', priority_val)
                items_with_priority.append(item)
            elif hasattr(item, 'product') and item.product and hasattr(item.product, 'order_priority') and item.product.order_priority is not None:
                p_val = item.product.order_priority + 10
                if isinstance(item, dict): item['_force_priority'] = p_val
                else: setattr(item, '_force_priority', p_val)
                items_with_priority.append(item)
            else: items_without_priority.append(item)
        else:
            if hasattr(item, 'product') and item.product and hasattr(item.product, 'order_priority') and item.product.order_priority is not None:
                if isinstance(item, dict): item['_force_priority'] = item.product.order_priority
                else: setattr(item, '_force_priority', item.product.order_priority)
                items_with_priority.append(item)
            else: items_without_priority.append(item)
    items_with_priority.sort(key=lambda x: (
        x.get('_force_priority', 0) if isinstance(x, dict) else getattr(x, '_force_priority', 0),
        x.line_item_type.billing_range.start if (not isinstance(x, dict) and hasattr(x, 'line_item_type') and x.line_item_type and x.line_item_type.billing_range and x.line_item_type.billing_range.start) else (x.get('line_item_type').billing_range.start if (isinstance(x, dict) and x.get('line_item_type') and x.get('line_item_type').billing_range and x.get('line_item_type').billing_range.start) else date.min),
        get_it_order(x),
        get_product_name(x).upper(),
        get_item_name(x).upper()
    ))
    priority_groups = {}
    for item in items_with_priority:
        priority = item.get('_force_priority', 0) if isinstance(item, dict) else getattr(item, '_force_priority', 0)
        if priority not in priority_groups: priority_groups[priority] = []
        priority_groups[priority].append(item)
    
    result = []
    for priority in sorted(priority_groups.keys()):
        g_list = priority_groups[priority]
        if advanced_grouping:
            g_list.sort(key=lambda x: (
                1 if is_leak_item(x) else 0,
                0 if any(kw in str(get_item_name(x)).upper() for kw in ['QUOTA', 'FIXA']) else 1,
                1 if (legacy_concept_order and 'FIX' in str(get_item_name(x)).upper() and 'FUITA' not in str(get_item_name(x)).upper()) else 0,
                get_it_order(x),
                str(get_item_name(x)).upper()
            ))
        result.append({'grouper': priority, 'list': g_list})
    if items_without_priority:
        items_without_priority.sort(key=lambda x: (
            x.line_item_type.billing_range.start if (not isinstance(x, dict) and hasattr(x, 'line_item_type') and x.line_item_type and x.line_item_type.billing_range and x.line_item_type.billing_range.start) else (x.get('line_item_type').billing_range.start if (isinstance(x, dict) and x.get('line_item_type') and x.get('line_item_type').billing_range and x.get('line_item_type').billing_range.start) else date.min),
            get_it_order(x),
            get_product_name(x).upper(),
            str(get_item_name(x)).upper()
        ))
        result.append({'grouper': None, 'list': items_without_priority})
    return result

@register.filter
def get_item(dictionary, key):
    if dictionary is None: return None
    return dictionary.get(key)

@register.filter
def has_key(dictionary, key):
    if dictionary is None: return False
    return key in dictionary

@register.filter
def subtract(value, other):
    if value is None: return None
    try: return Decimal(str(value)) - Decimal(str(other or 0))
    except: return value

@register.filter
def add(value, other):
    if value is None: return None
    try: return Decimal(str(value)) + Decimal(str(other or 0))
    except: return value

@register.filter
def days_since(value, other):
    if value is None or other is None: return ""
    try:
        d1 = value.date() if isinstance(value, datetime) else value
        d2 = other.date() if isinstance(other, datetime) else other
        return (d1 - d2).days
    except: return ""

@register.filter
def sum_attribute(line_items, attribute):
    if not line_items: return 0
    total = 0
    for item in line_items:
        val = item.get(attribute, 0) if isinstance(item, dict) else getattr(item, attribute, 0)
        total += Decimal(str(val or 0))
    return total

@register.filter
def paginate_rows(items, sizes="5,16"):
    """Parteix una llista de files en blocs, un per pàgina del PDF.

    xhtml2pdf no sap partir una taula HTML entre pàgines: si les files no caben
    dins el frame de contingut, en lloc de continuar a una pàgina nova les dibuixa
    per sobre, trepitjant la capçalera. La plantilla recorre els blocs que retorna
    aquest filtre i força un `<pdf:nextpage />` entre ells.

    `sizes` és "primera,següents": la primera pàgina comparteix espai amb la
    capçalera i el cos de la carta, així que hi caben menys files que a la resta.
    """
    if not items: return []
    try:
        parts = [int(s) for s in str(sizes).split(',') if str(s).strip()]
        first = parts[0]
        rest = parts[1] if len(parts) > 1 else parts[0]
    except (ValueError, IndexError):
        first, rest = 5, 16
    if first < 1 or rest < 1: return [list(items)]

    remaining = list(items)
    pages = []
    size = first
    while remaining:
        pages.append(remaining[:size])
        remaining = remaining[size:]
        size = rest
    return pages

@register.filter
def get_quarter(value):
    if not value or not (isinstance(value, date) or isinstance(value, datetime)): return value
    q = ["1r", "2n", "3r", "4t"][(value.month-1)//3]
    return f"{q} trimestre {value.year}"

@register.filter
def get_period_months(value):
    if not value or not (isinstance(value, date) or isinstance(value, datetime)): return value
    m = ["Gener / Febrer / Març", "Abril / Maig / Juny", "Juliol / Agost / Setembre", "Octubre / Novembre / Desembre"][(value.month-1)//3]
    return f"{m} {value.year}"

@register.filter
def split_last_comma(value):
    if not value or not isinstance(value, str): return value
    idx = value.rfind(',')
    return f"{value[:idx+1]}<br>{value[idx+1:]}" if idx != -1 else value

@register.simple_tag
def get_config(token, default_value=''):
    try:
        from coredata.models import ConfigProject
        config = ConfigProject.objects.filter(token=token).first()
        return config.value if config and config.value else default_value
    except: return default_value

@register.filter
def fill_water_blocks(items, args=None):
    if not items or get_config('invoice_apply_advanced_grouping', 'false').lower() != 'true':
        return items
        
    is_canon = False
    is_domestic_aca = False
    for item in items:
        pname = item.get('product_name', '') if isinstance(item, dict) else getattr(item, 'product_name', '')
        pname = pname or (item.get('name', '') if isinstance(item, dict) else getattr(item, 'name', ''))
        if any(kw in str(pname).upper() for kw in ['CANON', 'CÀNON']):
            is_canon = True
            # Check if this Canon item is domestic
            pr = item.get('price_rate') if isinstance(item, dict) else getattr(item, 'price_rate', None)
            if pr and 'DOMEST' in str(pr.name).upper():
                is_domestic_aca = True
            # Check for specific industrial keywords in description
            desc = (item.get('description', '') or item.get('name', '')).upper() if isinstance(item, dict) else (getattr(item, 'description', '') or getattr(item, 'name', '')).upper()
            if 'INDUSTRIAL' in desc:
                is_domestic_aca = False
            break
            
    # If it is Canon but not domestic, we skip the block logic as requested
    if is_canon and not is_domestic_aca:
        return items
            
    # Dynamic limits and prices from database instead of config
    from pricing.models import PriceRate, Product
    from decimal import Decimal

    # 1. Get Multiplier from General Variable
    multiplier = 1
    invoice = None
    for it in items:
        if not invoice:
            invoice = it.get('invoice') if isinstance(it, dict) else getattr(it, 'invoice', None)
        if invoice: break

    if invoice and invoice.contract:
        general_var = invoice.contract.variables.filter(type__name='General', is_active=True).first()
        if general_var:
            try:
                val = int(general_var.value)
                if val > 0: multiplier = val
            except:
                pass

    def get_blocks_from_pr(pr, is_canon_mode, items_list=None, invoice=None, multiplier=1):
        if not pr: return []
        stretches_list = []
        found_prices = []
        
        # 1. Collect potential BillingRanges to check
        brs_to_check = []
        
        # Priority 0: BillingRange matching the invoice period (most accurate)
        if invoice:
            try:
                reading = invoice.readings.all().order_by('-reading_date').first()
                if reading and reading.reading_date:
                    from django.db.models import Q
                    target_date = reading.reading_date
                    br_match = pr.billing_ranges.filter(start__lte=target_date).filter(Q(end__gt=target_date) | Q(end__isnull=True)).order_by('-start').first()
                    if br_match:
                        brs_to_check.append(br_match)
            except:
                pass
        
        # Priority A: BillingRange from existing items (most accurate for the current invoice)
        if items_list:
            for it in items_list:
                lit = it.get('line_item_type') if isinstance(it, dict) else getattr(it, 'line_item_type', None)
                if lit:
                    br_obj = getattr(lit, 'billing_range', None)
                    if not br_obj and hasattr(lit, 'billing_range_id') and lit.billing_range_id:
                        from pricing.models import BillingRange
                        try: br_obj = BillingRange.objects.get(id=lit.billing_range_id)
                        except: pass
                    if br_obj:
                        brs_to_check.append(br_obj)
                        break
        
        # Priority B: Default active BillingRange for this PriceRate
        if pr.billing_range_active:
            brs_to_check.append(pr.billing_range_active)
            
        # Priority C: Latest active BillingRanges
        fallback_brs = pr.billing_ranges.filter(is_active=True).order_by('-start')
        for fbr in fallback_brs:
            if fbr not in brs_to_check:
                brs_to_check.append(fbr)
        
        for br in brs_to_check:
            for lit in br.line_item_types.all():
                pname_u = (lit.name or '').upper()
                stretches = None
                
                # Identify if this LIT matches the current mode
                if is_canon_mode:
                    if any(kw in pname_u for kw in ['CANON', 'CÀNON', 'VARIABLE', 'TRAM']):
                        stretches = (lit.price_variable.price_variable_interval_stretches.all() if lit.price_variable 
                                     else lit.price_interval.price_interval_stretches.all() if lit.price_interval else None)
                else:
                    if any(kw in pname_u for kw in ['CONSUM', 'BLOC', 'AIGUA']):
                        stretches = (lit.price_interval.price_interval_stretches.all() if lit.price_interval 
                                     else lit.price_variable.price_variable_interval_stretches.all() if lit.price_variable else None)
                
                if stretches:
                    stretches = stretches.order_by('stretch')
                    stretches_list = [s.end_stretch for s in stretches if s.end_stretch and s.end_stretch < 999999]
                    found_prices = [Decimal(str(s.price or s.proportional_price or 0)) for s in stretches]
                    if stretches_list or found_prices: break
            if stretches_list or found_prices: break

        if not stretches_list and not found_prices: return []

        blocks = []
        for i, limit in enumerate(stretches_list):
            # Apply multiplier to the limit
            m_limit = limit * multiplier if limit else limit
            blocks.append({
                'limit': m_limit,
                'price': found_prices[i] if i < len(found_prices) else Decimal('0')
            })
        # Add the final block (onwards)
        last_price = found_prices[len(stretches_list)] if len(found_prices) > len(stretches_list) else (found_prices[-1] if found_prices else Decimal('0'))
        blocks.append({'limit': 999999, 'price': last_price})
        return blocks

    pr_found = None
    invoice = None
    for it in items:
        if not pr_found:
            pr_found = it.get('price_rate') if isinstance(it, dict) else getattr(it, 'price_rate', None)
        if not invoice:
            invoice = it.get('invoice') if isinstance(it, dict) else getattr(it, 'invoice', None)
        if pr_found and invoice: break

    current_blocks = get_blocks_from_pr(pr_found, is_canon, items, invoice, multiplier)

    # If the price_rate found doesn't have blocks, try to find one in the contract that does
    if (not current_blocks or len(current_blocks) <= 1) and invoice and invoice.contract:
        token = '1002' if is_canon else '1001'
        # Look for a matching PriceRate in the contract's linked rates (active and for the correct zone/exploitation)
        for cpr in invoice.contract.price_rates.filter(is_active=True, price_rate__is_active=True):
            pr = cpr.price_rate
            if not pr.product: continue
            
            pname = str(pr.product.name or '').upper()
            is_match = (pr.product.token == token)
            if not is_match:
                if is_canon:
                    is_match = any(kw in pname for kw in ['CANON', 'CÀNON'])
                else:
                    is_match = any(kw in pname for kw in ['AIGUA', 'CONSUM']) and not any(kw in pname for kw in ['CANON', 'CÀNON', 'CLAVEGUERAM'])
            
            if is_match:
                test_blocks = get_blocks_from_pr(pr, is_canon, None, invoice, multiplier)
                if test_blocks and len(test_blocks) > 1:
                    pr_found = pr
                    current_blocks = test_blocks
                    break

    if not current_blocks:
        token = '1002' if is_canon else '1001'
        prod = Product.objects.filter(token=token).first()
        if prod:
            pr_fallback = PriceRate.objects.filter(product=prod, is_active=True).order_by('-created_at').first()
            current_blocks = get_blocks_from_pr(pr_fallback, is_canon, None, None, multiplier)

    if not current_blocks:
        # Final fallback - hardcoded defaults as last resort (no config used)
        d_limits = [27, 45, 54] if is_canon else [36, 84, 135]
        # Apply multiplier to fallbacks
        d_limits = [l * multiplier for l in d_limits]
        current_blocks = [{'limit': l, 'price': Decimal('0')} for l in d_limits]
        current_blocks.append({'limit': 999999, 'price': Decimal('0')})

    WATER_BLOCKS_CONFIG = CANON_BLOCKS_CONFIG = current_blocks
    
    # Safe args parsing
    args_str = str(args) if args else ''
    do_renaming = (args_str.upper() != 'DISABLED' and args_str != '')
    
    if is_canon:
        if not do_renaming or 'BLOC' in args_str.upper() or ',' not in args_str:
            args_str = "4,TRAM,VARIABLE - TRAM ,1|2|3|4"
    else:
        if not do_renaming or ',' not in args_str:
            args_str = "4,BLOC,BLOC ,1|2|3|4"

    parts = args_str.split(',')
    max_blocks = int(parts[0].strip()) if len(parts) > 0 and parts[0].strip().isdigit() else 4
    creation_prefix = parts[2].strip() if len(parts) > 2 else ('VARIABLE - TRAM ' if is_canon else 'BLOC ')
    ordinals = [o.strip() for o in parts[3].split('|')] if len(parts) > 3 and parts[3].strip() else []

    import re
    result = []
    
    # Sort items to ensure BLOC 1, 2, 3 sequence matches end_stretch ordering
    items_list = list(items)
    def it_sort_key(it):
        nm = (it.get('name', '') or it.get('description', '')).upper() if isinstance(it, dict) else (getattr(it, 'name', '') or getattr(it, 'description', '')).upper()
        if is_leak_item(it): return 999999
        if any(k in nm for k in ['QUOTA', 'FIXA']): return -1
        v = it.get('end_stretch', 0) if isinstance(it, dict) else getattr(it, 'end_stretch', 0)
        try: return float(v or 999999)
        except: return 999999
    items_list.sort(key=it_sort_key)

    block_counter = 1
    for item in items_list:
        desc = (item.get('description', '') or item.get('name', '')) if isinstance(item, dict) else (getattr(item, 'description', '') or getattr(item, 'name', ''))
        desc_str = str(desc)
        new_desc = desc_str
        is_water_block = False
        is_quota = False
        desc_upper = desc_str.upper()
        is_leak = is_leak_item(item)
        
        if not is_leak and any(kw in desc_upper for kw in ['QUOTA', 'FIXA']):
            is_quota = True
            if do_renaming: new_desc = 'FIXA' if 'FIXA' in desc_upper else 'QUOTA DE SERVEI'
            
            # If it's QUOTA DE SERVEI and we have a multiplier, update the units
            if multiplier > 1 and 'QUOTA' in desc_upper:
                if isinstance(item, dict):
                    if item.get('units') == 1:
                        item['units'] = multiplier
                        item['price_unit'] = float(item['price_unit']) / multiplier
                else:
                    if getattr(item, 'units', None) == 1:
                        setattr(item, 'units', multiplier)
                        p_unit = getattr(item, 'price_unit', 0)
                        setattr(item, 'price_unit', float(p_unit) / multiplier)
                
        if not is_quota and not is_leak:
            if any(kw in desc_upper for kw in ['CONSUM', 'BLOC', 'TRAM', 'VARIABLE']):
                is_water_block = True
                
        if is_water_block:
            idx = block_counter
            if do_renaming:
                phrase_config = CANON_BLOCKS_CONFIG if is_canon else WATER_BLOCKS_CONFIG
                block_info = phrase_config[idx-1] if 0 < idx <= len(phrase_config) else {'limit': None, 'price': Decimal('0')}
                g_limit = block_info['limit']
                prev_g = phrase_config[idx-2]['limit'] if 1 < idx <= len(phrase_config) and idx > 1 else 0
                label_prefix = f"VARIABLE - TRAM {idx}" if is_canon else f"BLOC {idx}"
                
                if idx == 1:
                    phrase = f" fins a {format_eu(int(g_limit / multiplier), 0) if g_limit else '...'} m3"
                elif idx < max_blocks: 
                    phrase = f" de {format_eu(int((prev_g / multiplier) + 1), 0)} a {format_eu(int(g_limit / multiplier), 0)} m3"
                else: 
                    phrase = f" a partir de {format_eu(int((prev_g / multiplier) + 1), 0)} m3"
                
                p_limit_val = None
                limit_match = re.search(r'Límit:\s*([\d\.,]+)', desc_str, flags=re.IGNORECASE)
                if limit_match: p_limit_val = float(limit_match.group(1).replace(',', '.'))
                elif not isinstance(item, dict): p_limit_val = getattr(item, 'end_stretch', None)
                elif isinstance(item, dict): p_limit_val = item.get('end_stretch', None)

                if idx < max_blocks and p_limit_val is not None and p_limit_val < 999999:
                    if "Límit: " not in phrase:
                        phrase += f" (Límit: {format_eu(p_limit_val, 0)})"
                
                new_desc = f"{label_prefix}{phrase}"
            block_counter += 1
            
        if is_quota:
            item_sort_prio = -1
        elif is_water_block:
            item_sort_prio = 0
        elif is_leak:
            item_sort_prio = 2
        else:
            item_sort_prio = 1
            
        if isinstance(item, dict): 
            item['description'] = item['name'] = new_desc
            item['_sort_prio'] = item_sort_prio
        else: 
            setattr(item, 'description', new_desc)
            setattr(item, 'name', new_desc)
            setattr(item, '_sort_prio', item_sort_prio)
        result.append(item)
    
    while (block_counter - 1) < max_blocks:
        idx = block_counter
        if do_renaming:
            config = CANON_BLOCKS_CONFIG if is_canon else WATER_BLOCKS_CONFIG
            block_info = config[idx-1] if 0 < idx <= len(config) else {'limit': None, 'price': Decimal('0')}
            g_limit = block_info['limit']
            prev_g = config[idx-2]['limit'] if 1 < idx <= len(config) and idx > 1 else 0
            label_prefix = f"VARIABLE - TRAM {idx}" if is_canon else f"BLOC {idx}"
            if idx == 1: phrase = f"{' (Mínim 18m3)' if is_canon else ''} fins a {int(g_limit / multiplier)} m3"
            elif idx < 4: phrase = f" de {int((prev_g / multiplier) + 1)} a {int(g_limit / multiplier)} m3"
            else: phrase = f" a partir de {int((prev_g / multiplier) + 1)} m3"
            if g_limit and g_limit < 999999:
                phrase += f" (Límit: {format_eu(g_limit, 0)})"
            label = f"{label_prefix}{phrase}"
        else:
            label = f"{creation_prefix}{ordinals[idx-1] if idx <= len(ordinals) else idx}"
        
        # Get price unit from config
        phrase_config = CANON_BLOCKS_CONFIG if is_canon else WATER_BLOCKS_CONFIG
        price_unit = phrase_config[idx-1]['price'] if 0 < idx <= len(phrase_config) else Decimal('0')
        
        result.append({'name': label, 'description': label, 'units': 0, 'price_unit': float(price_unit), 'price': 0, 'total': 0, '_sort_prio': 0})
        block_counter += 1
        
    def sort_final(x):
        return x.get('_sort_prio', 1) if isinstance(x, dict) else getattr(x, '_sort_prio', 1)
        
    return sorted(result, key=sort_final)


@register.filter
def with_bonification_percent(text, percent):
    """
    Insereix el percentatge de bonificació dins del nom d'una línia de factura.

    El nom que genera la facturació té la forma
    "CONSUM - 1R TRAM; - BONIFICACIÓ SMI Límit: 18": el nom de l'ajustament hi
    surt, però no el percentatge que s'hi ha aplicat, que viu a una variable del
    contracte. Aquest filtre l'hi encaixa just darrere del nom de l'ajustament
    (abans del "Límit:", si n'hi ha):

        {{ line_item.name|with_bonification_percent:percentatge }}
        -> "CONSUM - 1R TRAM; - BONIFICACIÓ SMI 75% Límit: 18"

    Si la línia no porta bonificació, o no tenim percentatge, torna el text tal qual.
    """
    if not text or percent in (None, '', 0, '0'):
        return text

    text = str(text)
    if 'BONIFICACI' not in text.upper():
        return text

    percent = str(percent).strip()
    suffix = f"{percent}%"
    if suffix in text:
        return text

    limit_match = re.search(r'L[ÍIíi]mit\s*:', text)
    if limit_match:
        head = text[:limit_match.start()].rstrip()
        return f"{head} {suffix} {text[limit_match.start():]}"

    return f"{text.rstrip()} {suffix}"

import datetime
import math
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from types import SimpleNamespace

from django.db.models import F, Max, Q, Sum
from matplotlib.dates import relativedelta

from billing.models import Invoice, InvoiceLineItem
from billing.utils.aca_company_service import resolve_aca_company
from contract.models import Bonification, Contract, Variable
from contract.utils.aca_tram_service import get_aca_tram_bonification_type
from coredata.models import ConfigProject
from contract.utils.contract_list_queryset import _fire_config_tokens
from pricing.models import ArticleCode
from service.models import Company, SupplyPoint
from watchdog.aca_config import ACA_DIR_VARIABLE_CONFIG_TOKEN, aca_tram_min_persons, get_config_value, split_config_tokens


class FactdetaValidationError(ValueError):
    """Dada que impedeix generar el FACTDETA i que l'usuari ha de corregir. Es mostra tal qual."""


def _load_factdeta_config():
    return SimpleNamespace(
        origin_reading_token=ConfigProject.objects.get(token='origin_reading_token').value,
        invoice_type=ConfigProject.objects.get(token="invoice_type_invoice_token").value,
        invoice_token_pending=ConfigProject.objects.get(token='invoice_status_pending_token').value,
        payoff_status_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value,
        
        main_company_token=ConfigProject.objects.get(token='main_company_token').value,
        token_meter_status_no_meter=ConfigProject.objects.get(token='token_meter_status_no_meter').value,
        active_contract_token=ConfigProject.objects.get(token='contract_active_token').value,
        
        aca_product_token = ConfigProject.objects.get(token="token_product_aca").value,
        part_fixa_token = ArticleCode.objects.get(token="part_fixa").token,
        part_variable_token = ArticleCode.objects.get(token="part_variable").token,
        tarifa_social_token=ConfigProject.objects.get(token='tarifa_social').value,
        contract_keeper_use_type_token = ConfigProject.objects.get(token="contract_keeper_use_type_token").value,
    )


def generate_factdeta_document(exploitations, invoices, is_alta = False):
    config = _load_factdeta_config()
    company = Company.objects.get(vat=config.main_company_token)
    if is_alta:
        files = generate_factdeta_alta_document(exploitations, invoices, config, company)
    else:
        files = generate_factdeta_normal_document(exploitations, invoices, config, company)
    return files

def generate_factdeta_alta_document(exploitations, invoices, config, company):
    files = []

    title_doc_id = "000" # +1 for each exploitation if done
    for exploitation in exploitations:
        print("\n\n--------------------------------")
        print("Exploitation: ", exploitation.name)
        total_exploitation = 0

        exploitation_invoices = invoices.filter(
            type_final=config.invoice_type,
            exploitation=exploitation,
            origin__token=config.origin_reading_token,
        ).filter(
            Q(used_aca="L") | Q(contract__use_aca="L", used_aca__isnull=True)
            ).exclude(
            status__token=config.invoice_token_pending
        ).distinct()
        print("Invoices: ", exploitation_invoices.count())
        ine_code = exploitation.code
        web_ine_code = "XXXXXX"

        # Group invoices by year based on issue_date
        invoices_by_year = defaultdict(list)
        for invoice in exploitation_invoices:
            year = invoice.issue_date.year
            invoices_by_year[year].append(invoice)

        # Process each year separately
        for year, year_invoices in invoices_by_year.items():
            print(f"Processing year {year} with {len(year_invoices)} invoices")
            file_company = resolve_aca_company({invoice.company_id for invoice in year_invoices}, company)
            entity_code = file_company.supply_code
            entity_nif = file_company.vat
            content_file = BytesIO()
            total_invoices = 0
            file_name = f"FDA{entity_code}_{year}_{title_doc_id}.txt"
            total_lines_report = 0

            max_characters = 398

            """ 
            CAPÇELERA DEL SUPORT
            REGISTRE DETALL DE FACTURES AMB 398 CHARS A CADA LINIA
            REGISTRE TOTAL DEL SUPORT
            """
            #
            #   SUPPORT HEADER
            #
            # support_header_space_length = 16-(len(entity_code) + len(entity_nif))

            support_header = f"10{normalize_text((entity_code + entity_nif), 16)}FACTDETA ALTA{year}{repeat_to_at_least_length(' ', 363)}"

            content_file.write((support_header + "\n").encode("utf-8"))

            #
            #   INVOICES DETAIL
            #

            #TODO: INVOICE LINES DETAIL

            invoice_tokens = [invoice.token for invoice in year_invoices]
            refactored_invoices = Invoice.objects.filter(
                return_token__in=invoice_tokens,
                type_final=config.invoice_type
            ).exclude(
                status__token=config.payoff_status_token
            ).order_by('return_token', '-created_at').distinct()

            refactored_invoice_map = {}
            for inv in refactored_invoices:
                if inv.return_token not in refactored_invoice_map:
                    refactored_invoice_map[inv.return_token] = inv

            for invoice in year_invoices:
                if total_invoices % 500 == 0:
                    print("Processed: ", total_invoices)
                    
                refactored_invoice = refactored_invoice_map.get(invoice.token, None)
                contract = invoice.contract if invoice.contract else None
                if not contract:
                    if invoice.contract_termination:
                        contract = invoice.contract_termination.contract
                
                # SINCE ALWAYS DECLARING READING INVOICES, CONTRACT SHOULD ALWAYS BE FOUND
                if not contract:
                    raise Exception("Contract not found")
                policy_num = contract.token.replace('/','')
                
                for supply_point in contract.supply_points.all():
                    
                    # IMPORTANT: DEMANAR COM ES TRACTARIEN LES LECTURES I COMPTADORS EN CAS D'HAVER-HI UN CANVI DE COMPTADOR
                    reading = invoice.readings.filter(supply_point=supply_point).order_by('-reading_date').first()
                    if not reading:
                        raise Exception("Reading not found")
                    reading_consumption = reading.real_consumption if reading.real_consumption else reading.calculated_value
                    reading_consumption = int(reading_consumption or 0)
                    close_reading = None
                    previous_reading = reading.previous_reading
                    if previous_reading:
                        if previous_reading.is_close:
                            close_reading = previous_reading
                            previous_reading = previous_reading.previous_reading
                            if previous_reading:
                                extra_consumption = previous_reading.real_consumption if previous_reading.real_consumption else previous_reading.calculated_value
                                reading_consumption += int(extra_consumption or 0)
                        elif previous_reading.previous_reading and previous_reading.previous_reading.is_close:
                            close_reading = previous_reading.previous_reading
                            previous_reading = previous_reading.previous_reading.previous_reading
                            if previous_reading:
                                extra_consumption = previous_reading.real_consumption if previous_reading.real_consumption else previous_reading.calculated_value
                                reading_consumption += int(extra_consumption or 0)
                    #
                    ### INVOICE LINE
                    #
                    invoice_line_content = "20"
                    if not web_ine_code or len(web_ine_code) != 6:
                        raise Exception("INE code is required AND to be 6 chars long")
                    invoice_line_content += web_ine_code
                    # INVOICE TOKEN WITHOUT FIRST 0 SINCE MAX IS 10 CHARS AND NO SERIE FINAL SINCE IT VARIES AND IT COULD BE GREATER THAN 10 CHARS LONG
                    invoice_token = (invoice.token or '')[1:]
                    invoice_line_content += invoice_token
                    invoice_line_content += invoice.issue_date.strftime('%Y%m%d')
                    
                    customer_token_final = invoice.customer_token_final or ''
                    customer_token_len = 12 - len(customer_token_final)
                    invoice_line_content += customer_token_final
                    invoice_line_content += repeat_to_at_least_length(' ', customer_token_len)
                    
                    customer_final = invoice.customer_final or ''
                    customer_name_len = 45 - len(customer_final)
                    invoice_line_content += customer_final
                    invoice_line_content += repeat_to_at_least_length(' ', customer_name_len)
                    
                    # SEMBLA QUE PART DE L'ADREÇA ÉS OPCIONAL
                    
                    street_code_len = 2
                    street_name_len = 50
                    street_number_len = 7
                    floor_len = 2
                    door_len = 2
                    stair_len = 2
                    invoice_line_content += repeat_to_at_least_length(' ', street_code_len)
                    invoice_line_content += repeat_to_at_least_length(' ', street_name_len)
                    invoice_line_content += repeat_to_at_least_length(' ', street_number_len)
                    invoice_line_content += repeat_to_at_least_length(' ', floor_len)
                    invoice_line_content += repeat_to_at_least_length(' ', door_len)
                    invoice_line_content += repeat_to_at_least_length(' ', stair_len)
                    
                    postal_code_final = invoice.postal_code_final or ''
                    postal_code_len = 5 - len(postal_code_final)
                    invoice_line_content += repeat_to_at_least_length(' ', postal_code_len)
                    invoice_line_content += postal_code_final
                    
                    city_final = invoice.city_final or ''
                    city_len = 25 - len(city_final)
                    invoice_line_content += city_final
                    invoice_line_content += repeat_to_at_least_length(' ', city_len)
                    
                    supply_address = normalize_text(str(supply_point.address or ''), 30)
                    supply_address_len = 30 - len(supply_address)
                    invoice_line_content += supply_address
                    invoice_line_content += repeat_to_at_least_length(' ', supply_address_len)
                    invoice_line_content += ine_code
                    
                    contract_len = 15 - len(policy_num)
                    invoice_line_content += policy_num
                    invoice_line_content += repeat_to_at_least_length(' ', contract_len)
                    
                    invoice_line_content += "01"    # SHOULD ALWAYS BE 1 METER PER SUPPLY POINT
                    invoice_line_content += reading.reading_date.strftime('%Y%m%d')
                    invoice_line_content += previous_reading.reading_date.strftime('%Y%m%d') if previous_reading else repeat_to_at_least_length('0', 8)
                    
                    consumption_str = str(reading_consumption)
                    consumption_len = 9 - len(consumption_str)
                    invoice_line_content += repeat_to_at_least_length('0', consumption_len) # CONSUMIT
                    invoice_line_content += consumption_str
                    invoice_line_content += repeat_to_at_least_length('0', consumption_len) # FACTURAT
                    invoice_line_content += consumption_str
                    
                    invoice_lines_reading = invoice.line_items.filter(Q(reading=reading) | Q(reading=close_reading, reading__isnull=False)).distinct()
                    # .values() returns dicts, not InvoiceLineItem instances
                    invoice_lines_reading_by_product = invoice_lines_reading.values('product').annotate(
                        total_price=Sum('price'),
                        product_name=F('product__name'),
                        name=Max('name'),
                    ).order_by('product_name')
                    invoice_lines_non_aca_products = list(
                        invoice_lines_reading_by_product.exclude(product__token=config.aca_product_token).distinct()
                    )
                    invoice_lines_aca_products = list(
                        invoice_lines_reading_by_product.filter(product__token=config.aca_product_token).distinct()
                    )

                    # SUBTOTAL DE LINIES DE LA FACTURA DEL PUNT DE SUBMINITRAMENT ACTUAL
                    subtotal_final = float(sum((line_item.price or 0) for line_item in invoice_lines_reading) or 0)
                    total_final = float(sum((line_item.total or 0) for line_item in invoice_lines_reading) or 0)
                    iva_final = total_final - subtotal_final
                    
                    subtotal_str = f"{subtotal_final:.2f}".replace('.', '')
                    subtotal_len = 10 -len(subtotal_str)
                    total_str = f"{total_final:.2f}".replace('.', '')
                    total_len = 11 -len(total_str)
                    iva_str = f"{iva_final:.2f}".replace('.', '')
                    iva_len = 9 -len(iva_str)
                    
                    invoice_line_content += str(len(invoice_lines_non_aca_products))
                    invoice_line_content += repeat_to_at_least_length('0', subtotal_len)
                    invoice_line_content += subtotal_str
                    invoice_line_content += repeat_to_at_least_length('0', consumption_len) 
                    invoice_line_content += consumption_str
                    
                    total_aca = 1 if int(subtotal_str) == 0 else 0
                    total_aca_len = 9 - len(str(total_aca))
                    invoice_line_content += repeat_to_at_least_length('0', total_aca_len)
                    invoice_line_content += str(total_aca)
                    
                    # PER ALGUNA RAÓ TOTA LA RESTA ÉS TOT 0, FINS QUE NO TROBEM UN CAS CONTRARI ES MANTINDRÀ D'AQUESTA MANERA
                    total_rest_len = 66
                    invoice_line_content += repeat_to_at_least_length('0', total_rest_len)
                    invoice_line_content += repeat_to_at_least_length('0', iva_len)
                    invoice_line_content += iva_str
                    invoice_line_content += repeat_to_at_least_length('0', total_len)
                    invoice_line_content += total_str
                    
                    # SO FAR NO REFACTOR
                    len_cancelled = 10
                    len_cancelled_date = 8
                    invoice_line_content += repeat_to_at_least_length(' ', len_cancelled)
                    invoice_line_content += repeat_to_at_least_length(' ', len_cancelled_date)
                    
                    invoice_line_content = remove_accents(invoice_line_content.upper())
                    content_file.write((invoice_line_content + "\n").encode("utf-8"))
                    total_invoices += 1
                    total_exploitation += total_final
                    
                    #
                    ### READING LINE
                    #
                    
                    reading_line_content = "30"
                    reading_line_content += web_ine_code
                    reading_line_content += invoice_token
                    
                    if not supply_point.meter:
                        raise Exception("Meter not found")
                    meter_code = supply_point.meter.code or ''
                    len_meter_str = 30 - len(meter_code)
                    reading_line_content += meter_code
                    reading_line_content += repeat_to_at_least_length(' ', len_meter_str)
                    
                    previous_reading_value = int(previous_reading.reading_value or 0) if previous_reading else ''
                    reading_value = int(reading.reading_value or 0)
                    len_previous_reading = 9 - len(str(previous_reading_value)) if previous_reading else 9
                    len_reading = 9 - len(str(reading_value))
                    
                    reading_line_content += repeat_to_at_least_length('0', len_previous_reading)
                    reading_line_content += str(previous_reading_value)
                    reading_line_content += previous_reading.reading_date.strftime('%Y%m%d') if previous_reading else repeat_to_at_least_length(' ', 8)
                    reading_line_content += repeat_to_at_least_length('0', len_reading)
                    reading_line_content += str(reading_value)
                    reading_line_content += reading.reading_date.strftime('%Y%m%d')
                    
                    reading_line_content += repeat_to_at_least_length('0', consumption_len) 
                    reading_line_content += consumption_str
                    reading_line_content += repeat_to_at_least_length('0', 9) 
                    reading_line_content += repeat_to_at_least_length('0', consumption_len) 
                    reading_line_content += consumption_str
                    reading_line_content += repeat_to_at_least_length(' ', 289) 
                    
                    reading_line_content = remove_accents(reading_line_content.upper())
                    content_file.write((reading_line_content + "\n").encode("utf-8"))
                    
                    #
                    ### LINE ITEM LINES
                    #
                    
                    total_lines_report += 2
                    
                    for item in invoice_lines_non_aca_products:
                        invoice_item_line_content = "40"
                        invoice_item_line_content += web_ine_code
                        invoice_item_line_content += invoice_token
                        
                        item_name = f"{item.get('product_name') or ''} - {item.get('name') or ''}"
                        len_item_name = 50 - len(item_name)
                        invoice_item_line_content += item_name
                        invoice_item_line_content += repeat_to_at_least_length(' ', len_item_name)
                        
                        item_price_str = f"{(item.get('total_price') or 0):.2f}".replace('.', '')
                        item_price_len = 9 - len(item_price_str)
                        invoice_item_line_content += repeat_to_at_least_length('0', item_price_len)
                        invoice_item_line_content += item_price_str
                        invoice_item_line_content += repeat_to_at_least_length(' ', 321)

                        total_lines_report += 1

                        invoice_item_line_content = remove_accents(invoice_item_line_content.upper())
                        content_file.write((invoice_item_line_content + "\n").encode("utf-8"))

            #
            #   SUPPORT FOOTER
            #
            len_total_invoices = 8 - len(str(total_invoices))
            len_total_lines_report = 8 - len(str(total_lines_report))
            len_entity_nif = 12 - len(entity_nif)
            support_footer = f"50{entity_code}{entity_nif}{repeat_to_at_least_length(' ', len_entity_nif)}{repeat_to_at_least_length('0', len_total_invoices)}{total_invoices}{repeat_to_at_least_length('0', len_total_lines_report)}{total_lines_report}{repeat_to_at_least_length(' ', 364)}"


            #
            #   FILE
            #

            content_file.write((support_footer + "\n").encode("utf-8"))
            
            for line in content_file.getvalue().splitlines():
                # check if every line has 398 characters
                if len(line) != 398:
                    raise Exception(f"Line {line} has {len(line)} characters instead of 398")
                # print(line)

            print("\n TOTAL EXPLOITATION: ", total_exploitation)
            files.append({
                "year": year,
                "file_name": file_name,
                "content": content_file.getvalue(),
            })
        title_doc_id = str(int(title_doc_id) + 1).zfill(3)
    return files


def repeat_to_at_least_length(s, wanted):
    if wanted >= 0:
        return s * (wanted//len(s))
    return ''

def remove_accents(text):
    nfd = unicodedata.normalize('NFD', str(text))
    s = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-/()')
    return ''.join(c if c in allowed else ' ' for c in s)

def normalize_text(content, length):
    content = str(content)
    return (content[:length]).ljust(length)


#
#   FACTDETA EN BAIXA (format 2026)
#
#   Estructura: document 03 de l'ACA "Estructura del fitxer. Declaració de la facturació
#   detallada en baixa" (actualització 03/06/2026). Validacions: document 08
#   "ACA_ValidacionsFactDeta_2026". Amb el Decret llei 5/2025 el camp de l'IVA passa a
#   ser l'import de la part fixa i el d'impagats, les xarxes alternatives.
#

FACTDETA_LINE_LENGTH = 664
DOMESTIC_TRAMS = 4
TARIFF_TYPES = ('D', 'I', 'Q', 'M', 'A', 'E', 'G', 'X')
# Exempts i mesurament directe: només es declara el volum consumit
CONSUMPTION_ONLY_TARIFF_TYPES = ('E', 'G', 'X', 'M')
ALTA_USE_ACA = 'L'
LEAK_QUANTITY_TOKEN = 'diferencia_fuita'
VULNERABLE_LEVEL = 2
# Part fixa obligatòria (alarma) per a consums des d'aquesta data
PART_FIXA_START_DATE = datetime.date(2026, 1, 1)
ZERO = Decimal('0')


def _alpha(value, length):
    return normalize_text(remove_accents(str(value or '').upper()), length)


def _num(value, int_digits, dec_digits=0):
    """Camp numèric 9(int)v9(dec): sense punt decimal, zeros a l'esquerra i el signe
    negatiu al primer dígit (-34.270 en un camp de 9 posicions és -00034270)."""
    length = int_digits + dec_digits
    scaled = int((_dec(value) * (10 ** dec_digits)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    text = '-' + str(-scaled).zfill(length - 1) if scaled < 0 else str(scaled).zfill(length)
    if len(text) > length:
        raise FactdetaValidationError(f"El valor {value} no cap en un camp numèric de {length} posicions")
    return text


def _date(value):
    return value.strftime('%Y%m%d') if value else ' ' * 8


def _dec(value):
    return Decimal(str(value or 0))


def _sum(lines, attr):
    return sum((_dec(getattr(line, attr)) for line in lines), ZERO)


def _concept(lines):
    """(volum, tarifa, import) d'un grup de línies. Si hi ha tarifes diferents (períodes amb
    canvi de tarifa) es declara la tarifa prorratejada equivalent."""
    volume = _sum(lines, 'units')
    amount = _sum(lines, 'price')
    rate = abs(amount / volume) if volume else ZERO
    return volume, rate, amount


def _empty_concept():
    return ZERO, ZERO, ZERO


def _line_quantity_token(line):
    quantity = line.line_item_type.quantity if line.line_item_type else None
    return quantity.token if quantity else None


def _line_type_name(line):
    name = (line.line_item_type.name if line.line_item_type else None) or line.name or ''
    return remove_accents(name.upper())


def _is_part_fixa(line, part_fixa_token):
    article = line.line_item_type.article if line.line_item_type else None
    return bool(article and article.token == part_fixa_token)


def _is_leak_line(line):
    return _line_quantity_token(line) == LEAK_QUANTITY_TOKEN


def _has_social_adjustment(line, tarifa_social_token):
    """Mateix criteri que la declaració ACA: la línia té un ajust condicionat a la variable
    de tarifa social (una condició `is_null` la nega)."""
    for applied in line.adjustments.all():
        adjustment = applied.adjustment
        if not adjustment:
            continue
        for condition in adjustment.conditions.all():
            quantity = condition.quantity
            if (
                isinstance(quantity, dict)
                and quantity.get('value') == f"variable.{tarifa_social_token}"
                and condition.operation != 'is_null'
            ):
                return True
    return False


def get_factdeta_tariff_type(use_aca, variable_lines, is_fire=False):
    """Tipus de tarifa del registre de detall a partir de l'ús ACA de la factura o del contracte."""
    if is_fire:
        return 'X'
    use_aca = (use_aca or '').strip().upper()
    has_price = any(abs(_dec(line.price_unit)) >= Decimal('0.001') for line in variable_lines)
    # Igual que a la declaració ACA, l'ús industrial sense preu és exempt
    if use_aca in ('', 'I') and variable_lines and not has_price:
        return 'E'
    # Contractes domèstics facturats amb tarifa industrial
    if use_aca == 'D' and variable_lines and all('INDUSTRIAL' in _line_type_name(line) for line in variable_lines):
        return 'I'
    # Contractes industrials facturats amb els trams domèstics
    if use_aca == 'I' and variable_lines and not any('INDUSTRIAL' in _line_type_name(line) for line in variable_lines) \
            and any(line.interval for line in variable_lines):
        return 'D'
    if use_aca in TARIFF_TYPES:
        return use_aca
    return 'D' if any(line.interval for line in variable_lines) else 'I'


def _empty_canon():
    return {
        'billed_volume': ZERO,
        'trams': [_empty_concept() for _ in range(DOMESTIC_TRAMS)],
        'social': _empty_concept(),
        'general': _empty_concept(),
        'specific': _empty_concept(),
        'leak': _empty_concept(),
        'variable_amount': ZERO,
        'fixed_amount': ZERO,
        'unclassified_trams': False,
    }


def _compute_domestic(canon, variable_lines):
    leak_lines = [line for line in variable_lines if _is_leak_line(line)]
    # Tarifa social amb tarifa 0 (consum per sota del límit del primer tram): en ús domèstic
    # només el bo social deixa el cànon a 0, encara que la línia no porti l'ajust de tarifa social
    # (mateix llindar de preu que la declaració ACA, i sense import perquè el registre quadri)
    social_lines = [
        line for line in variable_lines
        if not _is_leak_line(line) and abs(_dec(line.price_unit)) < Decimal('0.001') and not _dec(line.price)
    ]
    tram_lines = [line for line in variable_lines if line not in leak_lines and line not in social_lines]

    # Línies sense interval: el tram surt de l'ordre de preus (el primer tram és el més barat),
    # entre els trams que no ocupen les línies que sí en tenen
    known_trams = {line.interval for line in tram_lines if line.interval and 1 <= line.interval <= DOMESTIC_TRAMS}
    free_trams = [tram for tram in range(1, DOMESTIC_TRAMS + 1) if tram not in known_trams] or [DOMESTIC_TRAMS]
    no_interval_prices = sorted({
        _dec(line.price_unit) for line in tram_lines
        if not (line.interval and 1 <= line.interval <= DOMESTIC_TRAMS)
    })
    if no_interval_prices and (known_trams or len(no_interval_prices) > len(free_trams)):
        canon['unclassified_trams'] = True
    fallback_trams = {
        price: free_trams[min(index, len(free_trams) - 1)] for index, price in enumerate(no_interval_prices)
    }

    lines_by_tram = defaultdict(list)
    for line in tram_lines:
        tram = line.interval if line.interval and 1 <= line.interval <= DOMESTIC_TRAMS else fallback_trams[_dec(line.price_unit)]
        lines_by_tram[tram].append(line)

    canon['trams'] = [_concept(lines_by_tram[tram]) for tram in range(1, DOMESTIC_TRAMS + 1)]
    canon['social'] = (_sum(social_lines, 'units'), ZERO, ZERO)
    canon['leak'] = _concept(leak_lines)
    canon['billed_volume'] = _sum(variable_lines, 'units')


def _compute_industrial(canon, variable_lines, is_municipal):
    leak_lines = [line for line in variable_lines if _is_leak_line(line)]
    other_lines = [line for line in variable_lines if line not in leak_lines]
    if is_municipal:
        # Els usos municipals només tenen gravamen general
        general_lines, specific_lines, leak_lines = variable_lines, [], []
    else:
        specific_lines = [line for line in other_lines if 'ESPECIFIC' in _line_type_name(line)]
        general_lines = [line for line in other_lines if line not in specific_lines]

    # El gravamen general es factura sobre el consum més la fuita (és el volum facturat total),
    # l'específic només sobre el consum i la fuita té la seva pròpia tarifa
    canon['general'] = _concept(general_lines)
    canon['specific'] = _concept(specific_lines)
    canon['leak'] = _concept(leak_lines)
    canon['billed_volume'] = canon['general'][0] if general_lines else canon['specific'][0] + canon['leak'][0]


def compute_factdeta_canon(tariff_type, aca_lines, part_fixa_token):
    """Volums, tarifes i imports del cànon d'una factura segons el tipus de tarifa."""
    canon = _empty_canon()
    if tariff_type in CONSUMPTION_ONLY_TARIFF_TYPES:
        return canon

    fixed_lines = [line for line in aca_lines if _is_part_fixa(line, part_fixa_token)]
    variable_lines = [line for line in aca_lines if line not in fixed_lines]
    canon['fixed_amount'] = _sum(fixed_lines, 'price')
    canon['variable_amount'] = _sum(variable_lines, 'price')

    if tariff_type == 'D':
        _compute_domestic(canon, variable_lines)
    elif tariff_type in ('I', 'A'):
        _compute_industrial(canon, variable_lines, is_municipal=tariff_type == 'A')
    # Quota ramadera (Q): sense volum facturat; els imports de quota no es facturen
    return canon


def build_factdeta_detail_record(record):
    canon = record['canon']
    fields = [
        '20',
        _num(record['ine_code'], 6),
        _alpha(record['invoice_number'], 10),
        _date(record['issue_date']),
        _alpha(record['customer_id'], 20),
        _alpha(record['tariff_type'], 1),
        _alpha(record['surname1'], 15),
        _alpha(record['surname2'], 15),
        _alpha(record['name'], 10),
        _alpha(record['street_code'], 2),
        _alpha(record['street_name'], 50),
        _alpha(record['street_number'], 7),
        _alpha(record['floor'], 2),
        _alpha(record['door'], 2),
        _alpha(record['stair'], 2),
        _alpha(record['postal_code'], 5),
        _alpha(record['city'], 25),
        _alpha(record['policy'], 15),
        _alpha(record['meter'], 25),
        _alpha(record['billing_system'], 1),
        _date(record['period_start']),
        _date(record['period_end']),
        _num(record['consumed_volume'], 12),
        _num(canon['billed_volume'], 12),
    ]
    for volume, rate, amount in canon['trams']:
        fields += [_num(volume, 9), _num(rate, 3, 6), _num(amount, 12, 4)]
    volume, rate, amount = canon['social']
    fields += [_num(volume, 5), _num(rate, 3, 6), _num(amount, 8, 4)]
    for concept in ('general', 'specific'):
        volume, rate, amount = canon[concept]
        fields += [_num(volume, 12), _num(rate, 3, 6), _num(amount, 12, 4)]
    volume, rate, amount = canon['leak']
    fields += [_num(volume, 9), _num(rate, 3, 6), _num(amount, 12, 4)]
    fields += [
        _num(0, 12, 4),     # Import quota anual
        _num(0, 12, 4),     # Import facturat quota
        _num(canon['variable_amount'], 12, 2),
        _num(canon['fixed_amount'], 11, 2),
        _num(canon['variable_amount'] + canon['fixed_amount'], 12, 2),
        _alpha(record['cancelled_number'], 10),
        _date(record['cancelled_date']),
        _alpha(record['alternative_network'], 1),
        _alpha(record['tram_extension'], 1),
        _num(record['inhabitants'], 2),
        _alpha(record['social_tariff'], 1),
        _alpha(record['vulnerable'], 1),
        _alpha(record['establishment_code'], 10),
        _num(record['homes'], 3),
        _num(record['places'], 4),
        _num(record['utm_x'], 6, 2),
        _num(record['utm_y'], 7, 2),
    ]
    line = ''.join(fields)
    if len(line) != FACTDETA_LINE_LENGTH:
        raise Exception(f"El registre de la factura {record['invoice_number']} té {len(line)} caràcters en lloc de {FACTDETA_LINE_LENGTH}")
    return line


def factdeta_record_warnings(record):
    """Validacions del document 08 que depenen de les dades (no del format). Retorna
    missatges per revisar abans de presentar el fitxer al validador de l'ACA."""
    canon = record['canon']
    tariff_type = record['tariff_type']
    total_amount = canon['variable_amount'] + canon['fixed_amount']
    warnings = []

    if not record['policy']:
        warnings.append("sense número de pòlissa")
    if not record['customer_id']:
        warnings.append("sense identificació de l'abonat")
    if record['period_start'] and record['period_end'] and record['period_end'] < record['period_start']:
        warnings.append("la data final del període de consum és anterior a la inicial")
    if tariff_type == 'D':
        declared = sum((concept[0] for concept in canon['trams']), ZERO) + canon['social'][0] + canon['leak'][0]
        if declared != canon['billed_volume']:
            warnings.append("la suma de trams, bo social i fuites no coincideix amb el volum facturat")
        if canon['unclassified_trams']:
            warnings.append("línies de cànon sense tram assignat: revisar el tram declarat")
    if tariff_type in ('D', 'I', 'A'):
        if record['consumed_volume'] * canon['billed_volume'] < 0:
            warnings.append("el volum consumit i el facturat tenen signes diferents")
        if not canon['fixed_amount'] and record['period_end'] and record['period_end'] >= PART_FIXA_START_DATE:
            warnings.append("sense import de part fixa")
    if total_amount < 0 and not record['cancelled_number']:
        warnings.append("import negatiu sense factura anul·lada")
    if tariff_type == 'M' and not record['establishment_code']:
        warnings.append("mesurament directe sense codi d'establiment")
    if record['billing_system'] == 'G' and tariff_type == 'D' and record['homes'] <= 1:
        warnings.append("comptador general domèstic amb menys de 2 habitatges")
    if not record['utm_x'] or not record['utm_y']:
        warnings.append("sense coordenades UTM")
    return warnings


def _summarize_warnings(invoices_by_warning, max_invoices=50):
    summary = []
    for warning, invoice_numbers in invoices_by_warning.items():
        shown = ', '.join(invoice_numbers[:max_invoices])
        more = ', ...' if len(invoice_numbers) > max_invoices else ''
        summary.append(f"{warning} ({len(invoice_numbers)} factures): {shown}{more}")
    return summary


def latlon_to_utm31(latitude, longitude):
    """Coordenades geogràfiques (WGS84/ETRS89) a UTM fus 31N, el de Catalunya."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    lon0 = math.radians(3)

    n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    t = math.tan(lat) ** 2
    c = ep2 * math.cos(lat) ** 2
    A = math.cos(lat) * (lon - lon0)
    m = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * lat
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * lat)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * lat)
        - (35 * e2 ** 3 / 3072) * math.sin(6 * lat)
    )
    x = 500000 + k0 * n * (
        A + (1 - t + c) * A ** 3 / 6 + (5 - 18 * t + t ** 2 + 72 * c - 58 * ep2) * A ** 5 / 120
    )
    y = k0 * (m + n * math.tan(lat) * (
        A ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * A ** 4 / 24
        + (61 - 58 * t + t ** 2 + 600 * c - 330 * ep2) * A ** 6 / 720
    ))
    return round(x, 2), round(y, 2)


def _utm_coordinates(meter, supply_point):
    for source in (meter, supply_point.connection if supply_point else None):
        if source and source.latitude and source.longitude:
            return latlon_to_utm31(float(source.latitude), float(source.longitude))
    return 0, 0


def _split_person_name(invoice, person):
    """(primer cognom, segon cognom, nom). Les persones jurídiques fan servir la raó social
    a l'espai dels tres camps."""
    if not person or person.is_juridic or invoice.customer_is_juridic:
        full_name = _alpha(invoice.customer_final or (str(person) if person else ''), 40)
        return full_name[:15], full_name[15:30], full_name[30:]
    surnames = (person.surname or '').split(' ', 1)
    return surnames[0], surnames[1] if len(surnames) > 1 else '', person.name or ''


def _supply_address(address, invoice, exploitation):
    if not address:
        return {
            'street_code': '', 'street_name': '', 'street_number': '', 'floor': '', 'door': '', 'stair': '',
            'postal_code': invoice.postal_code_final, 'city': invoice.city_final or exploitation.name,
        }
    street = address.street
    street_type = street.type if street else None
    return {
        'street_code': (street_type.aca_abbreviation if street_type and street_type.aca_abbreviation else 'CR'),
        'street_name': street.name if street else '',
        'street_number': address.street_number.number if address.street_number else '',
        'floor': address.floor,
        'door': address.door,
        'stair': address.stair,
        'postal_code': address.postal_code or invoice.postal_code_final,
        'city': (address.city.name if address.city else address.city_name) or exploitation.name,
    }


def _billing_system(invoice, meter, config):
    """'C' comptador individual, 'G' comptador general, 'A' aforaments (sense comptador)."""
    if invoice.is_general or (meter and meter.is_general):
        return 'G'
    if not meter or (meter.status and meter.status.token == config.token_meter_status_no_meter):
        return 'A'
    return 'C'


def _homes_count(invoice, contract, meter):
    general_contracts = invoice.general_contracts.count()
    if general_contracts:
        return general_contracts
    if not meter:
        return 0
    return SupplyPoint.objects.filter(meter=meter, contracts__isnull=False).distinct().count()


def _consumption_period(invoice):
    readings = list(invoice.readings.all())
    end_dates = [reading.reading_date for reading in readings if reading.reading_date]
    start_dates = [
        reading.previous_reading.reading_date if reading.previous_reading and reading.previous_reading.reading_date
        else reading.reading_date
        for reading in readings if reading.reading_date
    ]
    if not end_dates:
        return invoice.issue_date, invoice.issue_date
    return min(start_dates), max(end_dates)


def _customer_id(value):
    """NIF sense separacions (document 03) i, si és un DNI sense els zeros de l'esquerra, completat."""
    value = re.sub(r'[^0-9A-Z]', '', str(value or '').upper())
    return value.zfill(9) if re.fullmatch(r'\d{6,7}[A-Z]', value) else value


def _invoice_number(invoice):
    # Com a l'ALTA: el token sense el primer zero (el camp és de 10 posicions)
    return (invoice.token or invoice.serie_final or '').replace('/', '')[-10:]


def _aca_lines_q(aca_product_token, field='product__token'):
    q = Q()
    for token in [part.strip() for part in (aca_product_token or '').split('|') if part.strip()]:
        q |= Q(**{f'{field}__contains': token})
    return q if q else Q(pk__in=[])


def _load_factdeta_baixa_context(config, invoices):
    """Dades que es consulten un sol cop per a totes les factures del fitxer."""
    contract_ids = {
        contract.id for invoice in invoices
        for contract in (invoice.contract, invoice.contract_termination and invoice.contract_termination.contract)
        if contract
    }

    tram_bonification_type = get_aca_tram_bonification_type()
    # Vigència de cada bonificació: en donar-la de baixa es desactiva i es tanca amb `end_at`
    tram_periods = defaultdict(list)
    if tram_bonification_type:
        for contract_id, start_at, end_at in Bonification.objects.filter(
            Q(is_active=True) | Q(end_at__isnull=False), bonification_type=tram_bonification_type,
            contract_id__in=contract_ids,
        ).values_list('contract_id', 'start_at', 'end_at'):
            tram_periods[contract_id].append((start_at, end_at))

    establishment_codes = {}
    direct_variable_tokens = split_config_tokens(get_config_value(ACA_DIR_VARIABLE_CONFIG_TOKEN))
    if direct_variable_tokens:
        for contract_id, value in Variable.objects.filter(
            type__token__in=direct_variable_tokens, is_active=True, contract_id__in=contract_ids,
        ).values_list('contract_id', 'value'):
            if value and str(value).strip().isdigit():
                establishment_codes[contract_id] = str(value).strip()

    # Factures anul·lades: l'original guarda a `return_token` el token del seu abonament
    cancelled_by_refund_token = {
        original.return_token: original
        for original in Invoice.objects.filter(
            return_token__in=[invoice.token for invoice in invoices if invoice.token],
        ).only('token', 'issue_date', 'return_token', 'serie_final')
    }

    # Com Contract.is_fire: ús del contracte o algun punt de subministrament amb connexió d'incendis
    fire_usage_tokens, fire_connection_token = _fire_config_tokens()
    fire_q = Q(use_type__token__in=fire_usage_tokens)
    if fire_connection_token:
        fire_q |= Q(supply_points__connection__use_type__token=fire_connection_token)
    fire_contract_ids = set(Contract.objects.filter(fire_q, id__in=contract_ids).values_list('id', flat=True))

    return SimpleNamespace(
        fire_contract_ids=fire_contract_ids,
        tram_periods=tram_periods,
        tram_min_persons=max(aca_tram_min_persons(), 4),
        establishment_codes=establishment_codes,
        cancelled_by_refund_token=cancelled_by_refund_token,
    )


def _factdeta_detail_data(invoice, aca_lines, exploitation, config, context):
    contract = invoice.contract or (invoice.contract_termination.contract if invoice.contract_termination else None)
    supply_point = None
    if contract:
        supply_point = contract.supply_point_default or contract.supply_points.first()
    meter = supply_point.meter if supply_point else None
    person = invoice.person or (contract.holder if contract else None)

    is_fire = bool(contract and contract.id in context.fire_contract_ids)
    variable_lines = [line for line in aca_lines if not _is_part_fixa(line, config.part_fixa_token)]
    tariff_type = get_factdeta_tariff_type(
        invoice.used_aca or (contract.use_aca if contract else None), variable_lines, is_fire,
    )
    social_line_ids = {line.id for line in variable_lines if _has_social_adjustment(line, config.tarifa_social_token)}
    canon = compute_factdeta_canon(tariff_type, aca_lines, config.part_fixa_token)

    cancelled = context.cancelled_by_refund_token.get(invoice.token)
    consumed_volume = _dec(invoice.real_consumption if invoice.real_consumption is not None else invoice.consumption)
    if (cancelled or canon['billed_volume'] < 0) and consumed_volume > 0:
        consumed_volume = -consumed_volume

    billing_system = _billing_system(invoice, meter, config)
    period_start, period_end = _consumption_period(invoice)
    persons = invoice.persons_final or (contract.total_persons if contract else 0) or 0
    has_tram_extension = bool(
        contract and persons >= context.tram_min_persons and any(
            (not start_at or not period_end or start_at <= period_end)
            and (not end_at or not period_start or end_at >= period_start)
            for start_at, end_at in context.tram_periods.get(contract.id, [])
        )
    )
    surname1, surname2, name = _split_person_name(invoice, person)
    utm_x, utm_y = _utm_coordinates(meter, supply_point)

    return {
        'ine_code': exploitation.code,
        'invoice_number': _invoice_number(invoice),
        'issue_date': invoice.issue_date,
        'customer_id': _customer_id(invoice.customer_token_final or (person.token if person else '')),
        'tariff_type': tariff_type,
        'surname1': surname1,
        'surname2': surname2,
        'name': name,
        **_supply_address(supply_point.address if supply_point else None, invoice, exploitation),
        'policy': contract.token.replace('/', '') if contract and contract.token else '',
        'meter': meter.code if meter else '',
        'billing_system': billing_system,
        'period_start': period_start,
        'period_end': period_end,
        'consumed_volume': consumed_volume,
        'canon': canon,
        'cancelled_number': _invoice_number(cancelled) if cancelled else '',
        'cancelled_date': cancelled.issue_date if cancelled else None,
        # Aigua no potable en ús domèstic: coeficient 0,5 al quart tram
        'alternative_network': 'R' if tariff_type == 'D' and supply_point and not supply_point.is_potable else '',
        'tram_extension': ('S' if has_tram_extension else 'N') if tariff_type == 'D' else '',
        'inhabitants': min(persons, 99) if tariff_type == 'D' and has_tram_extension else 0,
        'social_tariff': ('S' if social_line_ids or canon['social'][0] else 'N') if tariff_type == 'D' else '',
        'vulnerable': 'S' if person and person.vulnerability_level >= VULNERABLE_LEVEL else 'N',
        'establishment_code': context.establishment_codes.get(contract.id, '') if contract and tariff_type in ('M', 'Q') else '',
        'homes': min(_homes_count(invoice, contract, meter), 999) if billing_system == 'G' and tariff_type in ('D', 'A') else 0,
        'places': 0,
        'utm_x': utm_x,
        'utm_y': utm_y,
    }


def generate_factdeta_normal_document(exploitations, invoices, config, company):
    """Un fitxer FDCCCC_MMMMMM_AAAA.txt per municipi (explotació) i any de facturació, amb un
    registre de detall per factura amb cànon, inclosos els usos exempts i els abonaments."""
    files = []
    aca_invoices = invoices.filter(
        _aca_lines_q(config.aca_product_token, 'line_items__product__token'),
        line_items__is_active=True,
        type_final=config.invoice_type,
    ).exclude(
        status__token=config.invoice_token_pending,
    ).exclude(
        used_aca=ALTA_USE_ACA,
    ).exclude(
        Q(used_aca__isnull=True) | Q(used_aca=''),
        Q(contract__use_aca=ALTA_USE_ACA)
        | Q(contract__isnull=True, contract_termination__contract__use_aca=ALTA_USE_ACA),
    ).distinct()

    # Un fitxer per municipi: les explotacions amb el mateix codi INE van al mateix fitxer
    exploitations_by_ine = defaultdict(list)
    for exploitation in exploitations:
        exploitations_by_ine[(exploitation.code or '').strip()].append(exploitation)

    for ine_code, ine_exploitations in exploitations_by_ine.items():
        ine_invoices = list(
            aca_invoices.filter(exploitation__in=ine_exploitations).select_related(
                'exploitation', 'person', 'status',
                'contract__holder', 'contract__use_type',
                'contract__supply_point_default__meter__status',
                'contract__supply_point_default__connection',
                'contract__supply_point_default__address__street__type',
                'contract__supply_point_default__address__street_number',
                'contract__supply_point_default__address__city',
                'contract_termination__contract',
            ).prefetch_related('readings__previous_reading').order_by('issue_date', 'token')
        )
        if not ine_invoices:
            continue
        if not (ine_code.isdigit() and len(ine_code) == 6):
            names = ", ".join(exploitation.name for exploitation in ine_exploitations)
            raise FactdetaValidationError(f"El codi INE de l'explotació {names} ha de tenir 6 dígits")

        invoices_by_year = defaultdict(list)
        for invoice in ine_invoices:
            invoices_by_year[invoice.issue_date.year].append(invoice)

        for year, year_invoices in sorted(invoices_by_year.items()):
            file_company = resolve_aca_company({invoice.company_id for invoice in year_invoices}, company)
            entity_code = file_company.supply_code
            entity_nif = file_company.vat
            context = _load_factdeta_baixa_context(config, year_invoices)

            lines_by_invoice = defaultdict(list)
            for line in InvoiceLineItem.objects.filter(
                _aca_lines_q(config.aca_product_token),
                invoice_id__in=[invoice.id for invoice in year_invoices],
                is_active=True,
            ).select_related(
                'line_item_type__article', 'line_item_type__quantity',
            ).prefetch_related('adjustments__adjustment__conditions').distinct():
                lines_by_invoice[line.invoice_id].append(line)

            lines = [
                '10' + _num(entity_code, 4) + _alpha(entity_nif, 12) + 'FACTDETA' + _num(year, 4)
                + _num(ine_code, 6) + ' ' * 628
            ]
            invoices_by_warning = defaultdict(list)
            for invoice in year_invoices:
                record = _factdeta_detail_data(invoice, lines_by_invoice[invoice.id], invoice.exploitation, config, context)
                try:
                    lines.append(build_factdeta_detail_record(record))
                except FactdetaValidationError as e:
                    raise FactdetaValidationError(f"Factura {record['invoice_number']}: {e}") from e
                for warning in factdeta_record_warnings(record):
                    invoices_by_warning[warning].append(record['invoice_number'])

            total_invoices = len(lines) - 1
            lines.append(
                '30' + _num(entity_code, 4) + _alpha(entity_nif, 12) + _num(ine_code, 6)
                + _num(total_invoices, 8) + _num(total_invoices + 2, 8) + ' ' * 624
            )
            for line in lines:
                if len(line) != FACTDETA_LINE_LENGTH:
                    raise Exception(f"Línia de {len(line)} caràcters en lloc de {FACTDETA_LINE_LENGTH}")

            files.append({
                "year": year,
                "file_name": f"FD{entity_code}_{ine_code}_{year}.txt",
                "content": ("\n".join(lines) + "\n").encode("utf-8"),
                "warnings": _summarize_warnings(invoices_by_warning),
            })
    return files

import unicodedata
from collections import defaultdict
from io import BytesIO
from types import SimpleNamespace

from django.db.models import F, Max, Q, Sum
from matplotlib.dates import relativedelta

from billing.models import Invoice, InvoiceLineItem
from billing.utils.aca_company_service import resolve_aca_company
from contract.models import Contract
from coredata.models import ConfigProject
from pricing.models import ArticleCode
from service.models import Company, SupplyPoint


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

def generate_factdeta_normal_document(exploitations, invoices, config, company):
    raise Exception("Not implemented")
    files = []
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

def get_total_homes(invoice, contract):
    meter = contract.supply_point_default.meter
    supply_points_contracts = SupplyPoint.objects.filter(meter=meter, contract__isnull=False).distinct()
    return supply_points_contracts.count()

def get_address(invoice, contract):
    text = ""
    if contract:
        address = contract.supply_point_default.address
        street = address.street   #50
        number =  address.street_number.number if address.street_number and address.street_number.number else '' #2
        floor = address.floor if address.floor else '' #2
        door = address.door if address.door else '' #2
        stair = address.stair if address.stair else '' #2
        postal_code = address.postal_code if address.postal_code else '' #5
        #city =  (address.province.name).upper() if address.province else '' #2
        city =  invoice.exploitation.name.upper() if invoice.exploitation else '' #2
        street_type = street.type.aca_abbreviation if street.type and street.type.aca_abbreviation else "CR"

        text += normalize_text((street_type).upper() + (street.name).upper(), 52)
        text += normalize_text(number, 7)
        text += normalize_text(floor, 2)
        text += normalize_text(door, 2)
        text += normalize_text(stair, 2)
        text += normalize_text(postal_code, 5)
        text += normalize_text(city, 25)

        return text

    return normalize_text(text,95)

def get_price_rate(config, invoice, line_items_canon):

    """ 
    "Q" PELS USOS RAMADERS SENSE CÀNON D'AIGUA O PER QUOTA
    "D" PELS USOS DOMÈSTICS
    "I" PELS USOS INDUSTRIALS
    "A" PELS USOS DE LA MUNICIPALITAT
    "E" PER ALTRES USOS EXEMPTS
    "M" PELS MESURAMENTS DIRECTES
    """

    contract = invoice.contract if invoice.contract else invoice.contract_request
    # print("contract: ", contract.token)
    if contract and contract.use_aca:
        # print("contract.use_aca: ", contract.use_aca)
        return contract.use_aca
    if contract and contract.use_type:
        if contract.use_type.token == config.contract_domestic_use_type_token:
            return "D"
        elif (contract.use_type.token == config.contract_industrial_use_type_token or contract.use_type.token == config.contract_comercial_use_type_token):
            return "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I"
        elif contract.use_type.token == config.contract_municipal_use_type_token:
            return "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I" # SI NOMÉS TÉ GENERAL, ÉS MUNICIPAL
        elif contract.use_type.token == config.contract_keeper_use_type_token:
            return "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I" #Q
    print("should be domestic: ", any(line_item.interval > 1 for line_item in line_items_canon))
    return "D" if any(line_item.interval > 0 for line_item in line_items_canon) else "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I" #"E" #check what value should be here in case of no contract or different situations

def get_clean_serie_final(invoice, meter_count):
    clean_invoice = invoice.serie_final.replace('/','')
    """ if '/' in invoice.serie_final:
        clean_invoice = clean_invoice[4:]
    else:
        clean_invoice = f"{invoice.issue_date.strftime('%m%Y')[1:]}{clean_invoice[:-7]}" """
    clean_invoice = f"{meter_count:02}{clean_invoice[:2]}{clean_invoice[-6:]}"
    return clean_invoice

def get_meter_type(config, invoice, contract):
    
    
    raise Exception("MIRA PRIMER EL METER DE LES LECTURES JA QUE POC CANVIAR")
    """ 
    "C" - COMPTADOR INDIVIDUAL
    "G" - COMPTADOR GENERAL
    "A" - AFORAMENTS
    "O" - ALTRES
    """
    token_meter_status_no_meter = config.token_meter_status_no_meter
    meter = None
    if contract:
        meter = contract.supply_point_default.meter if contract.supply_point_default else None
    if not meter or meter.status.token == token_meter_status_no_meter:
        return "A"
    if meter.is_general or contract.variables.filter(type__token="general").exists():
        return "G"
    if contract.supply_points.count() == 1:
        return "C"
    return "O"

def get_total_line_items(line_items):
    return round(abs(sum(line_item.price for line_item in line_items)), 2)


def _aggregate_canon_line_items(line_items_list, is_domestic):
    """
    Aggregate canon line items by (line_item_type, price_unit) and, for domestic,
    also by interval. Sums units and price so that repeated meter+line_item_type+price_unit
    are shown as a single line with combined total.
    For domestic contracts, if canon lines share the same (interval) but
    have different price_unit (e.g. positive/negative adjustments), merge them by interval:
    keep units (they should match), sum price, and **preserve the original price_unit**
    instead of recomputing it from the aggregated total, to avoid small rounding changes.
    Returns a list of SimpleNamespace(units, price_unit, price, line_item_type, interval).
    """
    if not line_items_list:
        return []

    groups = defaultdict(
        lambda: {"units": None, "price": 0.0, "price_unit": None, "line_item_type": None, "interval": None}
    )

    for li in line_items_list:
        if is_domestic:
            # Group domestic canon by interval only (ignore type/price_unit differences)
            key = (li.units or 0, li.interval or 0)
        else:
            key = (li.line_item_type_id or 0, float(li.price_unit or 0))
        g = groups[key]

        if is_domestic:
            # For domestic, units for same interval should be the same; keep first seen.
            if g["units"] is None:
                g["units"] = float(li.units or 0)
        else:
            if g["units"] is None:
                g["units"] = 0.0
            g["units"] += float(li.units or 0)

        g["price"] += float(li.price or 0)
        g["name"] = li.name
        if g["line_item_type"] is None:
            g["line_item_type"] = li.line_item_type
            g["price_unit"] = li.price_unit
            g["interval"] = li.interval

    result = []
    for g in groups.values():
        units = g["units"] if g["units"] is not None else 0.0
        if is_domestic:
            # Preserve the original unit price for domestic contracts to avoid
            # changing it due to rounding differences between total/units.
            price_unit = g["price_unit"] or 0.0
        else:
            price_unit = g["price_unit"]
        result.append(
            SimpleNamespace(
                units=units,
                price_unit=price_unit,
                price=g["price"],
                line_item_type=g["line_item_type"],
                interval=g["interval"],
                name=g["name"],
            )
        )
    return result


def get_canon_line_items(config, invoice, line_items, contract, total_leak, refactored_invoice, price_rate_letter):
    content = ''
    #POS 426 TO 436?
    tarifa_social_token = config.tarifa_social_token

    #watch out!!! using for now since no price rate is calculating leak by intervals
    line_items = line_items.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()
    if contract and ((contract.use_type and contract.use_type.token == config.contract_domestic_use_type_token) or contract.use_aca == "D"):
        line_items = line_items.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()
    # print("line_items: ", line_items)

    original_list = list(line_items)
    is_domestic = price_rate_letter == "D"
    aggregated = _aggregate_canon_line_items(original_list, is_domestic)
    line_item_len = len(aggregated)
    # print("aggregated: ", aggregated)

    extra_line_item_info = 4 - line_item_len
    volume_billed = 0
    price_rate_billed = 0

    if contract:
        not_in_any_type = False
        if not contract.use_aca:
            if contract.use_type:
                if contract.use_type.token != config.contract_domestic_use_type_token and contract.use_type.token != config.contract_industrial_use_type_token and contract.use_type.token != config.contract_municipal_use_type_token and contract.use_type.token != config.contract_comercial_use_type_token and contract.use_type.token != config.contract_keeper_use_type_token:
                    not_in_any_type = True
            else:
                not_in_any_type = True
        else:
            if contract.use_aca == "M":
                return content + repeat_to_at_least_length('0', 236)

        if is_domestic:
            # print("domestic")
            len_volume = 9
            len_price_rate = 9

            value_to_add_social = False


            for line_item in original_list:
                for adj in line_item.adjustments.all():
                    for cond in adj.adjustment.conditions.all():
                        if (
                            cond.quantity
                            and 'value' in cond.quantity
                            and cond.quantity['value'] == f"variable.{tarifa_social_token}"
                            and cond.operation != "is_null" # pot tenir la variable per "negar-la", per validar que és null
                            ):
                            value_to_add_social = True

            #START POS - 264/298/332/366 END 400
            for line_item in sorted(aggregated, key=lambda x: (x.interval or x.price_unit or 0)):
                used_units = abs(int(line_item.units))
                if value_to_add_social and line_item.price_unit == 0:
                    used_units = 0
                units_str = repeat_to_at_least_length('0', len_volume-len(str(used_units)))
                if refactored_invoice:
                    units_str = '-' + units_str[1:] if units_str.startswith('0') else units_str
                content += units_str
                content += str(used_units)

                price_unit_split = str(round(line_item.price_unit or 0, 4)).split('.') if abs(int(line_item.units)) > 0 else ['0', '0']
                content += repeat_to_at_least_length('0', 3-len(price_unit_split[0]))
                content += price_unit_split[0]
                try:
                    content += price_unit_split[1]
                    content += repeat_to_at_least_length('0', 6-len(price_unit_split[1]))
                except:
                    content += repeat_to_at_least_length('0', 6)

                total_split = str(round(abs(line_item.price or 0), 2)).split('.')
                total_split_str = repeat_to_at_least_length('0', 12-len(total_split[0]))
                if refactored_invoice:
                    total_split_str = '-' + total_split_str[1:] if total_split_str.startswith('0') else total_split_str
                content += total_split_str
                content += total_split[0]
                try:
                    content += total_split[1]
                    content += repeat_to_at_least_length('0', 4-len(str((total_split[1]))))
                except:
                    content += repeat_to_at_least_length('0', 4)
            if extra_line_item_info > 0:
                for i in range(extra_line_item_info):
                    content += repeat_to_at_least_length('0', len_volume)
                    content += repeat_to_at_least_length('0', 9)
                    content += repeat_to_at_least_length('0', 16)



            #START AT 400 END AT 426
            #should negative be added????¿?¿ (No found examples of negative values here)
            # content += "|"
            total_price_lineitems = get_total_line_items(original_list)

            if (value_to_add_social and total_price_lineitems == 0):

                total_consumption = sum(abs(int(li.units or 0)) for li in original_list)
                # if line_item_len > 1:
                #     total_consumption = 0
                len_consumption = 5 - len(str(int(total_consumption)))

                total_consumption_str = repeat_to_at_least_length('0', len_consumption) + str(int(total_consumption))
                total_final_units_str = repeat_to_at_least_length('0', 9)
                if refactored_invoice:
                    total_consumption_str = '-' + total_consumption_str[1:] if total_consumption_str.startswith('0') else total_consumption_str
                    total_final_units_str = '-' + total_final_units_str[1:] if total_final_units_str.startswith('0') else total_final_units_str
                content += total_consumption_str
                content += repeat_to_at_least_length('0', 12)
                content += total_final_units_str
                content += repeat_to_at_least_length('0', 74)
            else:
                content += repeat_to_at_least_length('0', 5)
                content += repeat_to_at_least_length('0', 9)
                content += repeat_to_at_least_length('0', 12)
                content += repeat_to_at_least_length('0', 74)
            # content += "|"
            return content

        elif (contract.use_type and (contract.use_type.token == config.contract_industrial_use_type_token or contract.use_type.token == config.contract_municipal_use_type_token or contract.use_type.token == config.contract_comercial_use_type_token or contract.use_type.token == config.contract_keeper_use_type_token)) or not_in_any_type or contract.use_aca in ["I", "A"]:
            # print("industrial")
            content += repeat_to_at_least_length('0', 162)
            len_volume = 12

            for line_item in sorted(aggregated, key=lambda x: (x.price_unit), reverse=True):
                line_units_str = repeat_to_at_least_length('0', len_volume-len(str(abs(int(line_item.units)))))
                if refactored_invoice:
                    line_units_str = '-' + line_units_str[1:] if line_units_str.startswith('0') else line_units_str

                content += line_units_str
                content += str(abs(int(line_item.units)))

                price_unit_split = str(round(line_item.price_unit or 0, 4)).split('.') if round(abs(line_item.price or 0), 2) > 0 or abs(int(line_item.units)) > 0 else str(round(0, 4)).split('.')
                content += repeat_to_at_least_length('0', 3-len(price_unit_split[0]))
                content += price_unit_split[0]
                try:
                    content += price_unit_split[1]
                    content += repeat_to_at_least_length('0', 6-len(price_unit_split[1]))
                except:
                    content += repeat_to_at_least_length('0', 6)

                total_split = str(round(abs(line_item.price or 0), 2)).split('.')
                line_total_split_str = repeat_to_at_least_length('0', 12-len(total_split[0]))
                if refactored_invoice:
                    line_total_split_str = '-' + line_total_split_str[1:] if line_total_split_str.startswith('0') else line_total_split_str

                content += line_total_split_str
                content += total_split[0]
                try:
                    content += total_split[1]
                    content += repeat_to_at_least_length('0', 4-len(total_split[1]))
                except:
                    content += repeat_to_at_least_length('0', 4)

            for i in range(2 - line_item_len):
                content += repeat_to_at_least_length('0', 37)


            """ if line_item_len == 1:
                content += repeat_to_at_least_length('0', 37)
            if line_item_len == 0:
                content += repeat_to_at_least_length('0', 73) #??? """

            return content
    print("none")
    return content + repeat_to_at_least_length('0', 236)

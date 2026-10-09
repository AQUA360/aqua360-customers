import datetime
import math
import unicodedata
from io import BytesIO
from types import SimpleNamespace

from billing.models import Invoice
from billing.templatetags.billing_filters import format_eu
from coredata.models import ConfigProject
from coredata.utils.address_utils import get_address_complete_without_city
from pricing.models import ArticleCode


def repeat_to_at_least_length(s, wanted):
    if wanted >= 0:
        return s * (wanted // len(s))
    return ''


def remove_accents(text):
    nfd = unicodedata.normalize('NFD', str(text))
    s = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-/():')
    return ''.join(c if c in allowed else ' ' for c in s)


def normalize_text(content, length):
    content = str(content)
    return (content[:length]).ljust(length)


def _load_sgt_txt_config():
    return SimpleNamespace(
        token_meter_status_no_meter=ConfigProject.objects.get(token='token_meter_status_no_meter').value,
        debt_vulnerable_token=ConfigProject.objects.get(token='debt_vulnerable_token').value,
        tarifa_social_token=ConfigProject.objects.get(token='tarifa_social').value,
        direct_debit_token=ConfigProject.objects.get(token='direct_debit_token').value,
        product_water_token=ConfigProject.objects.get(token='product_water_token').value,
        product_meter_token=ConfigProject.objects.get(token='product_meter_token').value,
        product_sewer_token=ConfigProject.objects.get(token='product_sewer_token').value,
        product_aca_token=ConfigProject.objects.get(token='token_product_aca').value,
        part_fixa_token=ArticleCode.objects.get(token='part_fixa').token,
    )


def _get_code_values(config):
    return [
        {"code": "42", "product_token": config.product_water_token, "is_variable": True, "is_fix": False, "is_tax": False, "is_aca": False},
        {"code": "62", "product_token": config.product_water_token, "is_variable": True, "is_fix": True, "is_tax": True, "is_aca": False},
        {"code": "32", "product_token": config.product_aca_token, "is_variable": True, "is_fix": True, "is_tax": False, "is_aca": True},
        {"code": "15", "product_token": config.product_sewer_token, "is_variable": True, "is_fix": True, "is_tax": False, "is_aca": False},
        {"code": "2B", "product_token": config.product_meter_token, "is_variable": True, "is_fix": True, "is_tax": False, "is_aca": False},
        {"code": "63", "product_token": config.product_meter_token, "is_variable": True, "is_fix": True, "is_tax": True, "is_aca": False},
        {"code": "40", "product_token": config.product_water_token, "is_variable": False, "is_fix": True, "is_tax": False, "is_aca": False},
    ]


def _get_billing_period(invoices, billing_date):
    first_invoice = invoices.first()
    unique_billing_months = invoices.values_list('issue_date__month', flat=True).distinct()
    if first_invoice and ((all(invoice.billing_period_days == 30 for invoice in invoices) and len(unique_billing_months) == 1)):
        return f"{first_invoice.issue_date.month:02d}"
    invoice_with_period = invoices.filter(billing_period_days__isnull=False).first()
    p_month = invoice_with_period.billing_period_month if invoice_with_period else (first_invoice.issue_date.month if first_invoice else billing_date.month)
    p_days = invoice_with_period.billing_period_days if invoice_with_period else (first_invoice.issue_date.day if first_invoice else 30)
    if p_days and p_month:
        trimester = math.ceil(30 * p_month / p_days)
    else:
        trimester = 1
    return f"{trimester}T"


def _get_matrix_lines(invoice, code_values, config):
    matrix_lines_content = ""
    len_description = 8
    
    # if any line item product is not in the code values, warn about it
    for line_item in invoice.line_items.all():
        if line_item.product.token not in [code_value['product_token'] for code_value in code_values]:
            print(f"Warning: line item product {line_item.product.token} not in code values")

    for code_value in code_values:
        # print(f"code value: {code_value}")
        # print(f"product token: {code_value['product_token']}")
        lines = invoice.line_items.filter(product__token=code_value['product_token'])
        # print(f"lines: {lines}")
        if lines and lines.count() > 0:
            matrix_lines_content += code_value['code']
            if not code_value['is_fix']:
                if code_value['is_aca']:
                    lines = lines.exclude(line_item_type__article__token=config.part_fixa_token).distinct()
                else:
                    lines = lines.filter(line_item_type__price__isnull=True).distinct()
            if not code_value['is_variable']:
                if code_value['is_aca']:
                    lines = lines.filter(line_item_type__article__token=config.part_fixa_token).distinct()
                else:
                    lines = lines.filter(line_item_type__price__isnull=False).distinct()
            if code_value['is_tax']:
                lines_total = str(format_eu(sum(float(line.total) - float(line.price) for line in lines), 2)).replace('.', '').replace(',', '')
            else:
                lines_total = str(format_eu(sum(float(line.price) for line in lines), 2)).replace('.', '').replace(',', '')
            matrix_lines_content += repeat_to_at_least_length('0', len_description - len(lines_total))
            matrix_lines_content += lines_total

    return matrix_lines_content


def _get_desc_lines(invoice, contract, holder, config):
    desc_lines_content = ""
    reading = None
    if contract:
        reading = invoice.readings.filter(meter=contract.supply_point_default.meter).order_by('-reading_date').first()
    if not reading:
        reading = invoice.readings.first()

    aca_line_items = invoice.line_items.filter(product__token=config.product_aca_token)

    subtotal_line = str(format_eu(invoice.subtotal_final, 2))[:10]
    taxes_line = str(format_eu(float(invoice.total_final) - float(invoice.subtotal_final), 2))[:10]

    total_water_import = str(format_eu(sum(line.price for line in invoice.line_items.filter(product__token=config.product_water_token, line_item_type__price__isnull=False)), 2))[:8]
    total_water_variable_import = str(format_eu(sum(line.price for line in invoice.line_items.filter(product__token=config.product_water_token, line_item_type__price__isnull=True)), 2))[:7]
    total_aca_fixa_import = str(format_eu(
        sum(
            line.price
            for line in invoice.line_items.filter(product__token=config.product_aca_token)
            if any(sub in (line.line_item_type.name or '') for sub in ['ESPECÍFIC', 'ESPECIFIC'])
        ), 2)
    )[:9]

    total_aca_variable_import = str(format_eu(
        sum(
            line.price
            for line in invoice.line_items.filter(product__token=config.product_aca_token)
            if not any(sub in (line.line_item_type.name or '') for sub in ['ESPECÍFIC', 'ESPECIFIC'])
        ), 2)
    )[:13]
    total_clv_fixa_import = str(format_eu(sum(line.price for line in invoice.line_items.filter(product__token=config.product_sewer_token, line_item_type__price__isnull=False)), 2))[:11]
    total_clv_variable_import = str(format_eu(sum(line.price for line in invoice.line_items.filter(product__token=config.product_sewer_token, line_item_type__price__isnull=True)), 2))[:10]
    total_meter_import = str(format_eu(sum(line.price for line in invoice.line_items.filter(product__token=config.product_meter_token)), 2))[:9]
    tax_water_fixa_import = str(format_eu(sum(float(line.total) - float(line.price) for line in invoice.line_items.filter(product__token=config.product_water_token, line_item_type__price__isnull=False)), 2))[:9]
    tax_water_variable_import = str(format_eu(sum(float(line.total) - float(line.price) for line in invoice.line_items.filter(product__token=config.product_water_token, line_item_type__price__isnull=True)), 2))[:7]
    tax_clav_fixa_import = str(format_eu(sum(float(line.total) - float(line.price) for line in invoice.line_items.filter(product__token=config.product_sewer_token, line_item_type__price__isnull=False)), 2))[:10]
    tax_clav_variable_import = str(format_eu(sum(float(line.total) - float(line.price) for line in invoice.line_items.filter(product__token=config.product_sewer_token, line_item_type__price__isnull=True)), 2))[:10]
    tax_meter_import = str(format_eu(sum(float(line.total) - float(line.price) for line in invoice.line_items.filter(product__token=config.product_meter_token)), 2))[:10]
    total_bonif = "0,00"
    tax_aca_import = "0,00"
    
    meter = None
    if invoice.readings and invoice.readings.count() > 0:
        meter = invoice.readings.first().meter
    if not meter:
        meter = contract.supply_point_default.meter if contract and contract.supply_point_default else None
    meter_line = f"Comptador:{meter.code}" if meter else "Comptador:"
    
    len_meter_line = 27 - len(meter_line)
    desc_lines_content += meter_line
    desc_lines_content += repeat_to_at_least_length(' ', len_meter_line)

    address_line = normalize_text(f"Adreça:{invoice.address_final}", 53) if invoice and invoice.address_final else ""
    len_address_line = 53 - len(address_line)
    desc_lines_content += address_line
    desc_lines_content += repeat_to_at_least_length(' ', len_address_line)

    previous_reading_line = normalize_text(f"Lectura Anterior:{repeat_to_at_least_length(' ', 10-len(format_eu(int(reading.previous_reading.reading_value), 0)))}{format_eu(int(reading.previous_reading.reading_value), 0)} ", 28) if invoice and reading and reading.previous_reading else ""
    len_previous_reading_line = 28 - len(previous_reading_line)
    desc_lines_content += previous_reading_line
    desc_lines_content += repeat_to_at_least_length(' ', len_previous_reading_line)

    current_reading_line = normalize_text(f"Lectura Actual:{repeat_to_at_least_length(' ', 10-len(format_eu(int(reading.reading_value), 0)))}{format_eu(int(reading.reading_value), 0)}{repeat_to_at_least_length(' ', 3)}", 28) if invoice and reading and reading.reading_value else ""
    len_current_reading_line = 28 - len(current_reading_line)
    desc_lines_content += current_reading_line
    desc_lines_content += repeat_to_at_least_length(' ', len_current_reading_line)

    current_consumption_line = normalize_text(f"Consum:{format_eu(int(invoice.consumption), 0)}", 24)
    len_current_consumption_line = 24 - len(current_consumption_line)
    desc_lines_content += current_consumption_line
    desc_lines_content += repeat_to_at_least_length(' ', len_current_consumption_line)

    import_line = "IMPORTS:"
    len_import_line = 81 - len(import_line)
    desc_lines_content += import_line
    desc_lines_content += repeat_to_at_least_length(' ', len_import_line)

    line_item_names_line = "Aigua    C.Especific    C.General    Clav.Fix    Clav.Var    Conserv    Bonif"
    desc_lines_content += line_item_names_line

    desc_lines_content += repeat_to_at_least_length(' ', 9 - len(total_water_variable_import))
    desc_lines_content += total_water_variable_import
    desc_lines_content += repeat_to_at_least_length(' ', 11 - len(total_aca_fixa_import))
    desc_lines_content += total_aca_fixa_import
    desc_lines_content += repeat_to_at_least_length(' ', 15 - len(total_aca_variable_import))
    desc_lines_content += total_aca_variable_import
    desc_lines_content += repeat_to_at_least_length(' ', 13 - len(total_clv_fixa_import))
    desc_lines_content += total_clv_fixa_import
    desc_lines_content += repeat_to_at_least_length(' ', 12 - len(total_clv_variable_import))
    desc_lines_content += total_clv_variable_import
    desc_lines_content += repeat_to_at_least_length(' ', 11 - len(total_meter_import))
    desc_lines_content += total_meter_import
    desc_lines_content += repeat_to_at_least_length(' ', 9 - len(total_bonif))
    desc_lines_content += total_bonif

    desc_lines_content += repeat_to_at_least_length(' ', 9 - len(tax_water_variable_import))
    desc_lines_content += tax_water_variable_import
    desc_lines_content += repeat_to_at_least_length(' ', 11 - len(tax_aca_import))
    desc_lines_content += tax_aca_import
    desc_lines_content += repeat_to_at_least_length(' ', 16 - len(tax_aca_import))
    desc_lines_content += tax_aca_import
    desc_lines_content += repeat_to_at_least_length(' ', 12 - len(tax_clav_fixa_import))
    desc_lines_content += tax_clav_fixa_import
    desc_lines_content += repeat_to_at_least_length(' ', 12 - len(tax_clav_variable_import))
    desc_lines_content += tax_clav_variable_import
    desc_lines_content += repeat_to_at_least_length(' ', 11 - len(tax_meter_import))
    desc_lines_content += tax_meter_import
    desc_lines_content += repeat_to_at_least_length(' ', 9 - len(total_bonif))
    desc_lines_content += total_bonif

    desc_lines_content += repeat_to_at_least_length(' ', 2)
    desc_lines_content += "QUOTA FIXA AIGUA:"
    desc_lines_content += repeat_to_at_least_length(' ', 10 - len(total_water_import))
    desc_lines_content += total_water_import
    desc_lines_content += repeat_to_at_least_length(' ', 2)
    desc_lines_content += "IVA Q.FIXA:"
    desc_lines_content += repeat_to_at_least_length(' ', 10 - len(tax_water_fixa_import))
    desc_lines_content += tax_water_fixa_import

    desc_lines_content += repeat_to_at_least_length(' ', 30)
    desc_lines_content += "BASE IMPOSABLE:"
    desc_lines_content += repeat_to_at_least_length(' ', 10 - len(subtotal_line))
    desc_lines_content += subtotal_line
    desc_lines_content += repeat_to_at_least_length(' ', 4)
    desc_lines_content += "IMPORT IVA:"
    desc_lines_content += repeat_to_at_least_length(' ', 10 - len(taxes_line))
    desc_lines_content += taxes_line

    return desc_lines_content


def generate_sgt_txt_content(request, invoices):
    config = _load_sgt_txt_config()
    invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
    code_values = _get_code_values(config)

    print("\n\n--------------------------------")
    if request:
        invoices = Invoice.objects.filter(
            type_final=invoice_type,
            serie_final__in=[
                # "2552014705",
                # "2552004351",
                # "2552015935",
                # "2552004392",
                "2552004268"
            ]).distinct()

    content_file = BytesIO()
    current_year = invoices.first().issue_date.year if invoices.first() else datetime.datetime.now().year

    first_invoice = invoices.first()
    billing_date = first_invoice.issue_date if first_invoice else datetime.datetime.now()
    billing_period = _get_billing_period(invoices, billing_date)
    file_name = f"{current_year}{billing_period} sgttxs.txt"
    
    count = 0

    for invoice in invoices:
        # print(f"Processing invoice {invoice.serie_final}")
        if count % 200 == 0:
            print(f"Processed {count} invoices out of {invoices.count()}")
        count += 1
        
        # if count == 500:
        #     break

        holder = None
        contract = None
        address = ""
        if invoice.contract:
            holder = invoice.contract.holder
            contract = invoice.contract
        elif invoice.contract_request:
            holder = invoice.contract_request.holder
            contract = invoice.contract_request
        elif invoice.contract_termination:
            holder = invoice.contract_termination.contract.holder
            contract = invoice.contract_termination.contract
        elif invoice.connection_request:
            holder = invoice.connection_request.person

        if contract and contract.supply_point_default:
            address = get_address_complete_without_city(contract.supply_point_default.address)
        elif invoice.connection_request:
            address_complete = ""
            if str(invoice.connection_request.address_street) and str(invoice.connection_request.address_street) != 'None':
                address_complete += str(invoice.connection_request.address_street)
            if str(invoice.connection_request.address_street_number) and str(invoice.connection_request.address_street_number) != 'None':
                address_complete += ", " + str(invoice.connection_request.address_street_number)
            address = address_complete

        len_token = 10 - len(invoice.token[2:])

        normalized_invoice = normalize_text(invoice.serie_final.replace('/', ''), 15)
        len_invoice = 15 - len(normalized_invoice)

        normalized_person_name = normalize_text(str(holder).upper(), 40)
        len_person_name = 40 - len(normalized_person_name)
        none_valid = ['00000000T', '00000001R', '99999999R', 'X0000000T', '']
        normalized_person_token = normalize_text(holder.token if holder.token not in none_valid else '99999999R', 9)
        len_person_token = 9 - len(normalized_person_token)

        len_receiver_billing = 40

        normalized_address_billing = normalize_text(invoice.address_final.upper(), 42)
        len_address_billing = 42 - len(normalized_address_billing)
        len_postal_code = 5 - len(invoice.postal_code_final)
        normalized_address_city = normalize_text(invoice.city_final.upper(), 25)
        len_city = 25 - len(normalized_address_city)

        normalized_iban = normalize_text(invoice.payment_bank_final.replace(' ', '').replace('-', ''), 34) if invoice.payment_type_token_final == config.direct_debit_token and invoice.payment_bank_final else ''
        len_iban = 34 - len(normalized_iban)

        normalized_total_final = str(invoice.total_final).replace('.', '')
        len_total_final = 10 - len(normalized_total_final)

        normalized_address = normalize_text(address.upper(), 42)
        len_address = 42 - len(normalized_address)

        normalized_customer_token = normalize_text(contract.token if contract else holder.token, 12)
        len_customer_token = 12 - len(normalized_customer_token)

        matrix_lines = _get_matrix_lines(invoice, code_values, config)
        len_line_items_matrix = 80 - len(matrix_lines)

        desc_lines = _get_desc_lines(invoice, contract, holder, config)
        len_desc_lines = 960 - len(desc_lines)

        normalized_contract_token = normalize_text(contract.token if contract else holder.token, 20).replace(' ', '')
        len_contract_token = 20 - len(normalized_contract_token)

        line_content = "134" 
        line_content += "91"

        line_content += repeat_to_at_least_length('0', len_token)
        line_content += invoice.token[2:]
        line_content += normalized_invoice
        line_content += repeat_to_at_least_length(' ', len_invoice)

        line_content += normalized_person_name
        line_content += repeat_to_at_least_length(' ', len_person_name)
        line_content += normalized_person_token
        line_content += repeat_to_at_least_length(' ', len_person_token)

        line_content += repeat_to_at_least_length(' ', len_receiver_billing)

        line_content += normalized_address_billing
        line_content += repeat_to_at_least_length(' ', len_address_billing)

        line_content += repeat_to_at_least_length(' ', len_postal_code)
        line_content += invoice.postal_code_final
        line_content += normalized_address_city
        line_content += repeat_to_at_least_length(' ', len_city)

        line_content += normalized_iban
        line_content += repeat_to_at_least_length(' ', len_iban)

        line_content += repeat_to_at_least_length('0', len_total_final)
        line_content += normalized_total_final

        line_content += normalized_address
        line_content += repeat_to_at_least_length(' ', len_address)

        line_content += normalized_customer_token
        line_content += repeat_to_at_least_length(' ', len_customer_token)

        line_content += matrix_lines
        line_content += repeat_to_at_least_length('0', len_line_items_matrix)

        line_content += desc_lines
        line_content += repeat_to_at_least_length(' ', len_desc_lines)

        line_content += repeat_to_at_least_length('0', 4)
        line_content += repeat_to_at_least_length(' ', 10)

        line_content += str(invoice.issue_date.year)

        line_content += normalized_contract_token
        line_content += repeat_to_at_least_length(' ', len_contract_token)

        line_content += repeat_to_at_least_length('0', 8)

        line_content = remove_accents(line_content)
        content_file.write((line_content + "\n").encode("utf-8"))

    return content_file, file_name

from collections import defaultdict
from io import BytesIO
import json
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from billing.models import Invoice, InvoiceLineItem, PaymentMovement
from billing.utils.sgt_txt_service import normalize_text, remove_accents
from contract.models import PaymentType
from coredata.models import Bank, ConfigProject
from coredata.utils.other_utils import round_ceil
from pricing.models import AccountingConcept, AccountingCostCenter, AccountingPricing, LineItemType, PriceInterval, PriceRate, PriceVariableInterval, Product, ProductOrigin
from service.models import Company, Exploitation


IVA_VALUES_TEMPLATE = {
    '0.00': {'base': 0.00, 'tax': 0.00},
    '10.00': {'base': 0.00, 'tax': 0.00},
    '21.00': {'base': 0.00, 'tax': 0.00},
    '50.00': {'base': 0.00, 'tax': 0.00},
}


def _empty_iva_values():
    return {percent: dict(amounts) for percent, amounts in IVA_VALUES_TEMPLATE.items()}


def _tax_for_base(base, percent_key):
    tax = Decimal(str(base)) * Decimal(str(percent_key)) / Decimal('100')
    return round_ceil(tax)


def _sum_iva_values(iva_values, field):
    return round_ceil(sum(amounts[field] for amounts in iva_values.values()))


def _as_float(value, negative = False):
    flip = 1 if not negative else -1
    if value is None:
        return 0.00
    if isinstance(value, Decimal):
        return round_ceil(float(value) * flip)
    return round_ceil(float(value) * flip)


def _iva_percent_key(percent):
    if percent is None:
        return '0.00'
    return f"{_as_float(round_ceil(percent)):.2f}"


def get_accounting_lines(accounting_pricings, invoices, movements):
    #
    # CATEGORIES
    # 'invoice': HANDLES INVOICES AS A WHOLE
    # 'lineitems': HANDLES INVOICE LINES DEPEDING ON RELATIONS IN ACCOUNTING PRICING
    # 'payment': HANDLES PAYMENT MOVEMENTS AS A WHOLE
    #
    lines = []

    if hasattr(accounting_pricings, 'select_related'):
        accounting_pricings = accounting_pricings.select_related(
            'accounting_concept',
            'accounting_concept__type',
            'exploitation',
        ).prefetch_related(
            'products',
            'price_rates',
            'line_item_types',
            'price_intervals',
            'price_variables',
        )

    lineitem_amounts = _group_lineitem_amounts(accounting_pricings, invoices)
    
    iva_accountings = AccountingPricing.objects.filter(
        is_active=True,
        accounting_concept__category='invoice',
        accounting_concept__type__add_taxes=True,
    )

    for accounting_pricing in accounting_pricings:
        concept = accounting_pricing.accounting_concept
        iva_accounting = iva_accountings.filter(exploitation=accounting_pricing.exploitation, accounting_concept__type__add_subtotals=False).first()
        main_accounting = iva_accountings.filter(exploitation=accounting_pricing.exploitation, accounting_concept__type__add_subtotals=True).first()
        if not concept or not concept.is_active:
            continue

        category = concept.category
        if category == 'invoice':
            lines.append(_get_invoice_category_line(accounting_pricing, invoices, iva_accounting, main_accounting))
        elif category == 'lineitem':
            new_line = _get_lineitem_category_line(
                accounting_pricing,
                lineitem_amounts.get(accounting_pricing.id),
                iva_accounting,
                main_accounting,
            )
            if new_line:
                lines.append(new_line)
        
        # 'payment' will be handled later

    return lines


def _get_invoice_category_line(accounting_pricing, invoices, iva_accounting = None, main_accounting = None):
    concept = accounting_pricing.accounting_concept
    accounting_type = concept.type
    add_subtotals = bool(accounting_type and accounting_type.add_subtotals)
    add_taxes = bool(accounting_type and accounting_type.add_taxes)

    matched_invoices = invoices
    if accounting_pricing.exploitation_id:
        matched_invoices = invoices.filter(exploitation_id=accounting_pricing.exploitation_id)

    subtotal = 0.00
    total = 0.00
    iva_values = _empty_iva_values()

    if add_subtotals and add_taxes:
        aggregated = matched_invoices.aggregate(
            subtotal=Coalesce(Sum('subtotal_final'), Decimal('0')),
            total=Coalesce(Sum('total_final'), Decimal('0')),
        )
        subtotal = _as_float(aggregated['subtotal'])
        total = _as_float(aggregated['total'])
        iva_values = _get_invoice_iva_values(matched_invoices)
    elif add_subtotals:
        aggregated = matched_invoices.aggregate(
            subtotal=Coalesce(Sum('subtotal_final'), Decimal('0'))
        )
        subtotal = _as_float(aggregated['subtotal'])
        total = subtotal
    elif add_taxes:
        iva_values = _get_invoice_iva_values(matched_invoices)
        total = _sum_iva_values(iva_values, 'tax')
    
    print(iva_values)
    print(subtotal)

    return {
        'accounting_concept': concept.token,
        'accounting_pricing': accounting_pricing.token,
        'accounting_pricing_name': accounting_pricing.name,
        'name': concept.name,
        'exploitation': accounting_pricing.exploitation,
        'category': concept.category,
        'iva': iva_values,
        'subtotal': _as_float(subtotal),
        'total': _as_float(total, accounting_pricing.accounting_concept.category == 'invoice' and add_taxes and add_subtotals),
        'iva_accounting': iva_accounting if accounting_pricing.accounting_concept.category == 'invoice' and add_taxes and not add_subtotals else None,
        'main_accounting': main_accounting,
        'cost_center_code': None,
    }


def _get_invoice_iva_values(invoices):
    """Split invoice taxes by line-item tax percent.

    Invoice itself has no tax rate, so percentages come from its line items.
    Each rate keeps the taxable base (sum of line prices) and the tax
    calculated from that base. Matching still uses the invoice as a whole
    (no product/rate/type filters).
    """
    iva_values = _empty_iva_values()
    line_items = InvoiceLineItem.objects.filter(
        invoice__in=invoices,
        is_active=True,
    ).only('tax_percent', 'total', 'price')

    for line_item in line_items.iterator():
        key = _iva_percent_key(line_item.tax_percent)
        if key not in iva_values:
            print(key, "not in iva_values")
            continue

        iva_values[key]['base'] = round_ceil(iva_values[key]['base'] + _as_float(line_item.price))

    for key, amounts in iva_values.items():
        amounts['tax'] = _tax_for_base(amounts['base'], key)

    return iva_values


_LEVEL_INTERVAL = 3
_LEVEL_LINE_ITEM = 2
_LEVEL_PRICE_RATE = 1
_LEVEL_PRODUCT = 0


def _decimal_amount(value):
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _lineitem_spec(accounting_pricing):
    """Most specific relation present on the pricing decides its level.

    Product is always required. A child relation does not need its parent:
    a line-item type can be set without the price rate it belongs to.
    """
    price_interval_ids = {interval.id for interval in accounting_pricing.price_intervals.all()}
    price_variable_ids = {variable.id for variable in accounting_pricing.price_variables.all()}
    line_item_type_ids = {line_item_type.id for line_item_type in accounting_pricing.line_item_types.all()}
    price_rate_ids = {price_rate.id for price_rate in accounting_pricing.price_rates.all()}

    if price_interval_ids or price_variable_ids:
        level = _LEVEL_INTERVAL
    elif line_item_type_ids:
        level = _LEVEL_LINE_ITEM
    elif price_rate_ids:
        level = _LEVEL_PRICE_RATE
    else:
        level = _LEVEL_PRODUCT

    return {
        'id': accounting_pricing.id,
        'level': level,
        'exploitation_id': accounting_pricing.exploitation_id,
        'product_ids': {product.id for product in accounting_pricing.products.all()},
        'price_rate_ids': price_rate_ids,
        'line_item_type_ids': line_item_type_ids,
        'price_interval_ids': price_interval_ids,
        'price_variable_ids': price_variable_ids,
    }


def _line_item_matches_spec(spec, line_item):
    if line_item.product_id not in spec['product_ids']:
        return False
    if spec['exploitation_id'] and line_item.invoice.exploitation_id != spec['exploitation_id']:
        return False

    level = spec['level']
    if level == _LEVEL_INTERVAL:
        line_item_type = line_item.line_item_type
        if line_item_type is None:
            return False
        interval_match = (
            line_item_type.price_interval_id in spec['price_interval_ids']
            if line_item_type.price_interval_id else False
        )
        variable_match = (
            line_item_type.price_variable_id in spec['price_variable_ids']
            if line_item_type.price_variable_id else False
        )
        return interval_match or variable_match
    if level == _LEVEL_LINE_ITEM:
        return line_item.line_item_type_id in spec['line_item_type_ids']
    if level == _LEVEL_PRICE_RATE:
        return line_item.price_rate_id in spec['price_rate_ids']
    return True


def _empty_lineitem_bucket():
    return {
        'price': Decimal('0'),
        'total': Decimal('0'),
        'iva_bases': defaultdict(lambda: Decimal('0')),
    }


def _group_lineitem_amounts(accounting_pricings, invoices):
    """Assign each invoice line to one line-item accounting pricing.

    Walk from children up to the product. Intervals and variables claim
    their lines first, then line-item types, then price rates. Whatever
    is left stays on the product pricing.
    """
    by_product = defaultdict(list)
    pricing_ids = []
    for accounting_pricing in accounting_pricings:
        concept = accounting_pricing.accounting_concept
        if not concept or not concept.is_active or concept.category != 'lineitem':
            continue
        spec = _lineitem_spec(accounting_pricing)
        if not spec['product_ids']:
            continue
        pricing_ids.append(spec['id'])
        for product_id in spec['product_ids']:
            by_product[product_id].append(spec)

    for specs in by_product.values():
        specs.sort(key=lambda spec: (-spec['level'], spec['id']))

    buckets = {pricing_id: _empty_lineitem_bucket() for pricing_id in pricing_ids}
    if not by_product:
        return buckets

    line_items = InvoiceLineItem.objects.filter(
        invoice__in=invoices,
        is_active=True,
        product_id__in=list(by_product.keys()),
    ).select_related('line_item_type', 'invoice')

    for line_item in line_items.iterator(chunk_size=2000):
        for spec in by_product.get(line_item.product_id, ()):
            if not _line_item_matches_spec(spec, line_item):
                continue
            bucket = buckets[spec['id']]
            price = _decimal_amount(line_item.price)
            bucket['price'] += price
            bucket['total'] += _decimal_amount(line_item.total)
            percent_key = _iva_percent_key(line_item.tax_percent)
            bucket['iva_bases'][percent_key] += price
            break

    return buckets


def _lineitem_iva_values(iva_bases):
    iva_values = _empty_iva_values()
    for percent_key, base in iva_bases.items():
        if percent_key not in iva_values:
            continue
        iva_values[percent_key]['base'] = _as_float(base)
        iva_values[percent_key]['tax'] = _tax_for_base(iva_values[percent_key]['base'], percent_key)
    return iva_values


def _get_lineitem_category_line(accounting_pricing, bucket, iva_accounting = None, main_accounting = None):
    concept = accounting_pricing.accounting_concept
    accounting_type = concept.type
    add_subtotals = bool(accounting_type and accounting_type.add_subtotals)
    add_taxes = bool(accounting_type and accounting_type.add_taxes)

    bucket = bucket or _empty_lineitem_bucket()
    subtotal = 0.00
    total = 0.00
    iva_values = _lineitem_iva_values(bucket['iva_bases']) if add_taxes else _empty_iva_values()

    if add_subtotals and add_taxes:
        subtotal = _as_float(bucket['price'])
        total = _as_float(bucket['total'])
    elif add_subtotals:
        subtotal = _as_float(bucket['price'])
        total = subtotal
    elif add_taxes:
        total = _sum_iva_values(iva_values, 'tax')
    
    if _as_float(subtotal) == 0 and _as_float(total) == 0:
        return None

    return {
        'accounting_concept': concept.token,
        'accounting_pricing': accounting_pricing.token,
        'accounting_pricing_name': accounting_pricing.name,
        'name': concept.name,
        'exploitation': accounting_pricing.exploitation,
        'category': concept.category,
        'iva': iva_values,
        'subtotal': _as_float(subtotal),
        'total': _as_float(total),
        'iva_accounting': iva_accounting if add_taxes and not add_subtotals else None,
        'main_accounting': main_accounting,
        'cost_center_code': accounting_pricing.accounting_cost_center.token if accounting_pricing.accounting_cost_center else None,
    }


def generate_general_accounting(date, last_document = None):
    content_file = BytesIO()
    max_characters = 2126
    
    date_str = date.strftime("%Y%m%d")
    doc_number = str(int(last_document.token) + 1) if last_document else '158429'
    
    accounting_pricings = AccountingPricing.objects.filter(is_active=True)
    
    invoices = Invoice.objects.filter(issue_date=date, is_active=True).distinct()
    movements = PaymentMovement.objects.filter(timestamp__date=date).distinct()
    print("total invoices: ", invoices.count())
    print("total movements: ", movements.count())
    invoice_status_payoff_token = ConfigProject.objects.get(token='invoice_status_payoff_token').value
    
    total_invoices = sum(invoice.total_final for invoice in invoices)
    print("total invoices: ", total_invoices)
    
    
    
    
    lines = get_accounting_lines(accounting_pricings, invoices, movements)
    
    print("total lines: ", len(lines))
    for line in lines:
        print(line)
    
    # raise Exception("stop here")
    
    for line in lines:

        """
        REGISTRE AMB 2126 CHARS A CADA LINIA
        """
        print("line")
        print(line)
        iva_values = line.get('iva')
        
        empty_num_value = 0.00
        iva_account_code = f"{line.get('iva_accounting').accounting_concept.token}{'0' * (12 - len(line.get('iva_accounting').accounting_concept.token) - len(line.get('iva_accounting').token))}{line.get('iva_accounting').token}" if line.get('iva_accounting') else ''
        main_account_code = f"{line.get('main_accounting').accounting_concept.token}{'0' * (12 - len(line.get('main_accounting').accounting_concept.token) - len(line.get('main_accounting').token))}{line.get('main_accounting').token}" if line.get('main_accounting') else ''
        
        len_center_code = 3
        center_code = f"{repeat_to_at_least_length('0', len_center_code - (len(line.get('cost_center_code'))))}{line.get('cost_center_code')}" if line.get('cost_center_code') else None
        
        line_content = ""
        line_content += repeat_to_at_least_length(' ', 6)
        line_content += date_str * 2
        
        doc_num_total = 10
        len_doc_number = len(str(doc_number))
        line_content += repeat_to_at_least_length(' ', doc_num_total-len_doc_number)
        line_content += str(doc_number)
        
        if len(line_content) != 32:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 34")
        
        line_content += '60' # DEFAULT FOR THE MOMENT
        
        title_total = 30
        title = normalize_text(line.get('accounting_pricing_name'), title_total)
        line_content += title
        line_content += repeat_to_at_least_length(' ', title_total-len(title))
        
        # if total is negative it goes into the other line
        debt = abs(line.get('total')) if line.get('total') < 0 else 0.00
        have = abs(line.get('total')) if line.get('total') > 0 else 0.00
        
        debt_str = f"{debt:.6f}"
        have_str = f"{have:.6f}"
        debt_len = 16 - len(debt_str)
        have_len = 16 - len(have_str)
        line_content += repeat_to_at_least_length(' ', debt_len)
        line_content += debt_str
        line_content += repeat_to_at_least_length(' ', have_len)
        line_content += have_str
        
        if len(line_content) != 96:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 98")
        
        accounting_account = f"{line.get('accounting_concept')}{'0' * (12 - len(line.get('accounting_concept')) - len(line.get('accounting_pricing')))}{line.get('accounting_pricing')}"
        accounting_account_len = 12 - len(accounting_account)
        line_content += repeat_to_at_least_length(' ', accounting_account_len)
        line_content += accounting_account
        
        line_content += '01'
        
        line_content += repeat_to_at_least_length(' ', 6-len_doc_number)
        line_content += str(doc_number)
        
        if len(line_content) != 116:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 116")
        
        
        #CURRENTLY EMPTY
        line_content += repeat_to_at_least_length(' ', 155)
        
        # has_iva = line.get('iva_accounting')
        iva_base_total = _sum_iva_values(iva_values, 'base')
        iva_tax_total = _sum_iva_values(iva_values, 'tax')
        has_iva = iva_base_total > 0 and line.get('category') == 'invoice' and line.get('subtotal') == 0
        if has_iva:
            line_content += 'IR'
            # line_accounting_token_len = 2 - len(line.get('iva_accounting').token)
            normalized_acc_name = normalize_text(line.get('main_accounting').name, 30)
            line_accounting_name_len = 30 - len(normalized_acc_name)
            # line_content += repeat_to_at_least_length('0', line_accounting_token_len) + line.iva_accounting.token
            line_content += '02' # SERIE IVA
            line_content += normalized_acc_name + repeat_to_at_least_length(' ', line_accounting_name_len)
            line_content += 'SENSE' + repeat_to_at_least_length(' ', 15 - len('SENSE'))
        else:
            line_content += repeat_to_at_least_length(' ', 49)
            
        if len(line_content) != 320:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 320")
        
        invoices_total = _as_float(iva_tax_total + iva_base_total) if has_iva else 0.00
        invoices_total_str = f"{invoices_total:.6f}"
        invoices_len = 16 - len(invoices_total_str)
        line_content += repeat_to_at_least_length(' ', invoices_len)
        line_content += invoices_total_str
        
        len_iva_value = 16
        len_percentage = 5
        for iva_value in iva_values:
            # print(iva_value, iva_values[iva_value])
            iva_entry = iva_values[iva_value]
            iva_amount = float(iva_entry['base']) if has_iva else 0.00
            iva = int(float(iva_value)) if iva_amount > 0 and has_iva else 0
            iva_total = float(iva_entry['tax']) if iva != 0 and has_iva else 0.00
            
            iva_value_str = f"{iva_amount:.6f}"
            iva_total_str = f"{iva_total:.6f}"
            iva_extra_total_str = f"{empty_num_value:.6f}"
            iva_str = f"{iva:.2f}"
            iva_extra_str = f"{empty_num_value:.2f}"
            
            show_iva = (iva_amount > 0 or (int(float(iva_value)) == 0 and iva_base_total > 0)) and has_iva
            line_content += '1' if show_iva else ' '
            line_content += repeat_to_at_least_length(' ', len_iva_value-len(iva_value_str))
            line_content += iva_value_str
            line_content += repeat_to_at_least_length(' ', len_percentage-len(iva_str))
            line_content += iva_str
            line_content += repeat_to_at_least_length(' ', len_percentage-len(iva_extra_str))
            line_content += iva_extra_str
            line_content += repeat_to_at_least_length(' ', len_iva_value-len(iva_total_str))
            line_content += iva_total_str
            line_content += repeat_to_at_least_length(' ', len_iva_value-len(iva_extra_total_str))
            line_content += iva_extra_total_str
        
        
        if len(line_content) != 572:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 572")
        
        line_content += repeat_to_at_least_length(' ', 53)
        for i in range(6):
            empty_num_value_str = f"{empty_num_value:.6f}"
            len_empty_num_value_str = 16 - len(empty_num_value_str)
            line_content += repeat_to_at_least_length(' ', 8)
            line_content += repeat_to_at_least_length(' ', len_empty_num_value_str)
            line_content += empty_num_value_str
        
        if len(line_content) != 769:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 769")
        
        if has_iva:
            len_main_account_code = 12 - len(main_account_code)
            line_content += main_account_code + repeat_to_at_least_length(' ', len_main_account_code)
            line_content += '002' #002 is EUR
        else:
            line_content += repeat_to_at_least_length(' ', 15)
        
        change_total = 1 #so far default value
        change_total_str = f"{change_total:.6f}"
        len_change_total_str = 12 - len(change_total_str)
        line_content += repeat_to_at_least_length(' ', len_change_total_str)
        line_content += change_total_str
        
        if center_code:
            len_iva_account_code = 6 - len(center_code)
            line_content += iva_account_code + repeat_to_at_least_length(' ', len_iva_account_code)
        else:
            line_content += repeat_to_at_least_length(' ', 6)
        
        if len(line_content) != 802:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 802")
        
        for j in range(8):
            empty_num_value_str = f"{empty_num_value:.6f}"
            len_empty_num_value_str = 16 - len(empty_num_value_str)
            line_content += repeat_to_at_least_length(' ', len_empty_num_value_str)
            line_content += empty_num_value_str
        
        if len(line_content) != 930:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 930")
        
        line_content += repeat_to_at_least_length(' ', 33)
        
        change_total_str = f"{change_total:.6f}"
        len_change_total_str = 12 - len(change_total_str)
        line_content += repeat_to_at_least_length(' ', len_change_total_str)
        line_content += change_total_str
        
        if len(line_content) != 975:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 975")
        
        line_content += repeat_to_at_least_length(' ', 147)
        
        if len(line_content) != 1122:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 1122")
        
        for k in range(12):
            empty_num_value_str = f"{empty_num_value:.6f}"
            len_empty_num_value_str = 16 - len(empty_num_value_str)
            line_content += repeat_to_at_least_length(' ', len_empty_num_value_str)
            line_content += empty_num_value_str
        
        line_content += repeat_to_at_least_length(' ', 105)
        line_content += ' 0'*3
        
        if len(line_content) != 1425:
            print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 1425")
        
        ###################

        line_content = remove_accents(line_content.upper())
        remaining = max_characters - len(line_content)
        line_content += repeat_to_at_least_length(' ', remaining)

        content_file.write((line_content + "\n").encode("utf-8"))

    for line in content_file.getvalue().splitlines():
        if len(line) != max_characters:
            raise Exception(f"Line {line} has {len(line)} characters instead of {max_characters}")

    return content_file


def repeat_to_at_least_length(s, wanted):
    if wanted >= 0:
        return s * (wanted // len(s))
    return ''


def _merge_related_ids(incoming_ids, related_manager):
    merged_ids = list(incoming_ids or [])
    merged_ids.extend(related_manager.values_list('id', flat=True))
    return list(dict.fromkeys(merged_ids))




def bulk_save_accounting_pricing(data, user):
    try:
        items = data.get('items', []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise Exception("Invalid payload: expected {'items': [...]} or a list of items")

        main_company_token = ConfigProject.objects.get(token='main_company_token').value
        main_company = Company.objects.get(vat=main_company_token)

        with transaction.atomic():
            for item in items:
                if not isinstance(item, dict):
                    raise Exception(f"Invalid item: expected dict, got {type(item)}")

                id = item.get('id')
                token = item.get('token')
                name = item.get('name')
                is_default = item.get('is_default', False)
                is_active = item.get('is_active', True)
                exploitation_id = item.get('exploitation')
                company_id = item.get('company', None)
                category = item.get('category')
                accounting_concept_id = item.get('accounting_concept')
                cost_center_id = item.get('cost_center', None)
                group_values = item.get('group_values', True)
                
                product_ids = item.get('products', [])
                price_rate_ids = item.get('price_rates', [])
                line_item_type_ids = item.get('line_item_types', [])
                price_interval_ids = item.get('price_intervals', [])
                price_variable_interval_ids = item.get('price_variables', [])
                
                payment_type_ids = item.get('payment_types', [])
                bank_ids = item.get('banks', [])
                outgoing_payments = item.get('outgoing_payments', True)
                incoming_payments = item.get('incoming_payments', True)
                national_iban = item.get('national_iban', True)
                foreign_iban = item.get('foreign_iban', True)
                
                undeclare_previous = item.get('undeclare_previous', False)
                invoice_category = item.get('invoice_category', None)
                origin_ids = item.get('origins', [])

                found_banks = Bank.objects.filter(id__in=bank_ids).distinct()
                if not company_id:
                    company = main_company
                else:
                    company = Company.objects.get(id=company_id)

                if not exploitation_id:
                    exploitation = Exploitation.objects.all().first()
                else:
                    exploitation = Exploitation.objects.get(id=exploitation_id)

                if not accounting_concept_id:
                    raise Exception("Accounting concept is required")
                else:
                    accounting_concept = AccountingConcept.objects.get(id=accounting_concept_id)
                
                cost_center = None
                if cost_center_id:
                    cost_center = AccountingCostCenter.objects.get(id=cost_center_id)

                if not id:
                    existing_pricing_accounting = None
                    try:
                        existing_pricing_accounting = AccountingPricing.objects.get(
                            token=token,
                            accounting_concept=accounting_concept,
                            exploitation=exploitation,
                            company=company,
                            banks__in=found_banks,
                            is_active=True,
                            invoice_category=invoice_category,
                            outgoing_payments=outgoing_payments,
                            incoming_payments=incoming_payments,
                            national_iban=national_iban,
                            foreign_iban=foreign_iban,
                            )
                        
                    except Exception as e:
                        pass
                    if existing_pricing_accounting:
                        accounting_pricing_saved = existing_pricing_accounting
                        product_ids = _merge_related_ids(product_ids, accounting_pricing_saved.products)
                        price_rate_ids = _merge_related_ids(price_rate_ids, accounting_pricing_saved.price_rates)
                        line_item_type_ids = _merge_related_ids(line_item_type_ids, accounting_pricing_saved.line_item_types)
                        price_interval_ids = _merge_related_ids(price_interval_ids, accounting_pricing_saved.price_intervals)
                        price_variable_interval_ids = _merge_related_ids(price_variable_interval_ids, accounting_pricing_saved.price_variables)
                        payment_type_ids = _merge_related_ids(payment_type_ids, accounting_pricing_saved.payment_types)
                        bank_ids = _merge_related_ids(bank_ids, accounting_pricing_saved.banks)
                        origin_ids = _merge_related_ids(origin_ids, accounting_pricing_saved.origins)
                    else:
                        accounting_pricing_saved = AccountingPricing.objects.create(
                            token=token,
                            name=name,
                            accounting_concept=accounting_concept,
                            accounting_cost_center=cost_center,
                            company=company,
                            exploitation=exploitation,
                            is_default=is_default,
                            is_active=is_active,
                            created_by=user,
                            last_updated_by=user,
                            undeclare_previous=undeclare_previous,
                            invoice_category=invoice_category,
                            outgoing_payments=outgoing_payments,
                            incoming_payments=incoming_payments,
                            national_iban=national_iban,
                            foreign_iban=foreign_iban,
                        )
                else:
                    accounting_pricing_saved = AccountingPricing.objects.get(id=id)
                    accounting_pricing_saved.token = token
                    accounting_pricing_saved.name = name
                    accounting_pricing_saved.accounting_concept = accounting_concept
                    accounting_pricing_saved.company = company
                    accounting_pricing_saved.exploitation = exploitation
                    accounting_pricing_saved.is_default = is_default
                    accounting_pricing_saved.is_active = is_active
                    accounting_pricing_saved.last_updated_by = user
                    accounting_pricing_saved.accounting_cost_center = cost_center
                    accounting_pricing_saved.undeclare_previous = undeclare_previous
                    accounting_pricing_saved.outgoing_payments = outgoing_payments
                    accounting_pricing_saved.incoming_payments = incoming_payments
                    accounting_pricing_saved.national_iban = national_iban
                    accounting_pricing_saved.foreign_iban = foreign_iban
                    accounting_pricing_saved.group_values = group_values
                    
                if category == 'payment':
                    accounting_pricing_saved.payment_types.set(PaymentType.objects.filter(id__in=payment_type_ids).distinct())
                    accounting_pricing_saved.banks.set(Bank.objects.filter(id__in=bank_ids).distinct())
                elif category == 'lineitem':
                    accounting_pricing_saved.products.set(Product.objects.filter(id__in=product_ids).distinct())
                    accounting_pricing_saved.price_rates.set(PriceRate.objects.filter(id__in=price_rate_ids).distinct())
                    accounting_pricing_saved.line_item_types.set(LineItemType.objects.filter(id__in=line_item_type_ids).distinct())
                    accounting_pricing_saved.price_intervals.set(PriceInterval.objects.filter(id__in=price_interval_ids).distinct())
                    accounting_pricing_saved.price_variables.set(PriceVariableInterval.objects.filter(id__in=price_variable_interval_ids).distinct())
                elif category == 'invoice':
                    accounting_pricing_saved.origins.set(ProductOrigin.objects.filter(id__in=origin_ids).distinct())
                accounting_pricing_saved.save()
    except Exception as e:
        raise Exception(f"Couldn't bulk save accounting pricing: {e}") from e
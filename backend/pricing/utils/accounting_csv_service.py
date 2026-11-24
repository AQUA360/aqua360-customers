"""CSV export for general accounting declarations."""

from io import BytesIO, StringIO
import csv

from billing.utils.sgt_txt_service import remove_accents
from pricing.utils.accounting_service import (
    _as_float,
    _assign_register_number,
    _line_debt_have,
    _optional_text,
    _pad_account_code,
    _sum_iva_values,
    repeat_to_at_least_length,
)

# CSV only exports 0 / 10 / 21 rates (no percent columns, no 50%).
_CSV_IVA_RATES = ('0.00', '10.00', '21.00')

_CSV_HEADERS = [
    'ACC_ENTRY',
    'MOVEMENT_DATE',
    'REGISTER_DATE',
    'REGISTER_ID',
    'TITLE',
    'DEBT',
    'HAVE',
    'COST_CENTER',
    'IVA_TYPE',
    'IVA_SERIES',
    'IVA_OPERATION',
    'IVA_TITLE',
    'IVA_ACC_ENTRY',
    'TOTAL',
    'IVA_0_BASE',
    'IVA_0_TAX',
    'IVA_10_BASE',
    'IVA_10_TAX',
    'IVA_21_BASE',
    'IVA_21_TAX',
]


def _csv_text(value):
    """Force spreadsheet apps to treat the cell as TEXT (keeps leading zeros)."""
    text = '' if value is None else str(value)
    return f'="{text.replace(chr(34), chr(34) + chr(34))}"'


def _csv_number(value):
    """Write a numeric cell (debt / have / IVA amounts)."""
    return _as_float(value)


def _csv_title(value):
    """Clean title like XML: strip accents/symbols, collapse spaces, uppercase."""
    text = remove_accents(value or '').upper()
    return _csv_text(' '.join(text.split()))


def _line_has_iva(line):
    """Same HAS_IVA gate as the XML export."""
    iva_values = line.get('iva') or {}
    iva_base_total = _sum_iva_values(iva_values, 'base')
    return (
        iva_base_total != 0
        and line.get('category') == 'invoice'
        and line.get('subtotal') == 0
    )


def _main_account_code(line):
    if not line.get('main_accounting'):
        return ''
    main_concept = (
        _optional_text(line.get('main_concept_token_override'))
        or line.get('main_accounting').accounting_concept.token
    )
    return _pad_account_code(main_concept, line.get('main_accounting').token)


def _iva_row_values(line, accounting_config, has_iva):
    """IVA cells matching the XML HAS_IVA block; blank when conditions fail."""
    blank = ''
    # TYPE/SERIES/OPERATION/TITLE/ACC_ENTRY/TOTAL + base/tax per rate
    if not has_iva:
        return [blank] * (6 + len(_CSV_IVA_RATES) * 2)

    iva_values = line.get('iva') or {}
    iva_base_total = _sum_iva_values(iva_values, 'base')
    iva_tax_total = _sum_iva_values(iva_values, 'tax')
    iva_document_code = (accounting_config.get('iva_document_code') or 'IR')[:2].strip()
    iva_series_code = (accounting_config.get('iva_series_code') or '02')[:2].strip()
    iva_operation_code = (accounting_config.get('iva_operation_code') or 'SENSE')[:15].strip()
    main_name = ''
    if line.get('main_accounting'):
        main_name = _optional_text(line.get('main_accounting').name) or ''

    values = [
        _csv_text(iva_document_code),
        _csv_text(iva_series_code),
        _csv_text(iva_operation_code),
        _csv_title(main_name),
        _csv_text(_main_account_code(line)),
        _csv_number(iva_tax_total + iva_base_total),
    ]

    for percent in _CSV_IVA_RATES:
        iva_entry = iva_values.get(percent) or {'base': 0.00, 'tax': 0.00}
        iva_amount = float(iva_entry.get('base') or 0)
        # Same per-rate visibility as XML.
        show_iva = (
            iva_amount != 0
            or (int(float(percent)) == 0 and iva_base_total != 0)
        )
        if show_iva:
            iva_percent = int(float(percent)) if iva_amount != 0 else 0
            iva_tax = float(iva_entry.get('tax') or 0) if iva_percent != 0 else 0.00
            values.extend([
                _csv_number(iva_amount),
                _csv_number(iva_tax),
            ])
        else:
            values.extend([blank, blank])

    return values


def generate_accounting_csv(lines, date, accounting_config=None):
    """CSV with the variable columns of each accounting declaration line."""
    accounting_config = accounting_config or {}
    date_str = date.strftime("%Y%m%d")
    next_register_number = int(f"{date.year % 10}{date.strftime('%m%d')}1")
    register_numbers_by_key = {}

    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(_CSV_HEADERS)

    for line in lines:
        # Same padded account as XML: concept + zeros + pricing token (12 chars).
        accounting_pricing = _pad_account_code(
            line.get('accounting_concept'),
            line.get('accounting_pricing'),
        )
        movement_date_str = (
            line.get('movement_date').strftime("%Y%m%d")
            if line.get('movement_date')
            else date_str
        )
        register_number, next_register_number = _assign_register_number(
            line, register_numbers_by_key, next_register_number,
        )
        if len(str(register_number)) > 6:
            raise Exception(f"Register number {register_number} exceeds 6 characters")

        debt, have = _line_debt_have(line)
        center_code = ''
        if line.get('cost_center_code'):
            center_code = (
                f"{repeat_to_at_least_length('0', 3 - len(str(line.get('cost_center_code'))))}"
                f"{line.get('cost_center_code')}"
            )

        has_iva = _line_has_iva(line)
        writer.writerow([
            _csv_text(accounting_pricing),
            _csv_text(movement_date_str),
            _csv_text(date_str),
            _csv_text(register_number),
            _csv_title(line.get('accounting_pricing_name') or ''),
            _csv_number(debt),
            _csv_number(have),
            _csv_text(center_code),
            *_iva_row_values(line, accounting_config, has_iva),
        ])

    return BytesIO(buffer.getvalue().encode('utf-8-sig'))

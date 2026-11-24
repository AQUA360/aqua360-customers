"""Fixed-width (XML/SGT) export for general accounting declarations."""

from io import BytesIO

from billing.utils.sgt_txt_service import normalize_text, remove_accents
from pricing.utils.accounting_service import (
    _as_float,
    _assign_register_number,
    _line_debt_have,
    _optional_text,
    _pad_account_code,
    _sum_iva_values,
    repeat_to_at_least_length,
)


def generate_accounting_xml(lines, date, accounting_config):
    """
    Build the fixed-width accounting file (2126 chars per line).

    Returns a BytesIO content file.
    """
    content_file = BytesIO()
    max_characters = 2126
    date_str = date.strftime("%Y%m%d")
    doc_number = date.strftime("%y%m%d")
    # Per-declaration register: YMMDD1, YMMDD2, ... (e.g. 610311, 610312).
    next_register_number = int(f"{date.year % 10}{date.strftime('%m%d')}1")
    register_numbers_by_key = {}

    iva_document_code = (accounting_config.get('iva_document_code') or 'IR')[:2].ljust(2)
    iva_series_code = (accounting_config.get('iva_series_code') or '02')[:2].ljust(2)
    iva_operation_code = (accounting_config.get('iva_operation_code') or 'SENSE')[:15].ljust(15)

    for line in lines:

        """
        REGISTRE AMB 2126 CHARS A CADA LINIA
        """
        # print("line")
        # print(line)
        iva_values = line.get('iva')

        empty_num_value = 0.00
        iva_account_code = (
            _pad_account_code(
                line.get('iva_accounting').accounting_concept.token,
                line.get('iva_accounting').token,
            )
            if line.get('iva_accounting')
            else ''
        )
        if line.get('main_accounting'):
            main_concept = (
                _optional_text(line.get('main_concept_token_override'))
                or line.get('main_accounting').accounting_concept.token
            )
            main_account_code = _pad_account_code(
                main_concept,
                line.get('main_accounting').token,
            )
        else:
            main_account_code = ''
        accounting_account = _pad_account_code(
            line.get('accounting_concept'),
            line.get('accounting_pricing'),
        )
        movement_date_str = (
            (line.get('movement_date')).strftime("%Y%m%d")
            if 'movement_date' in line and line.get('movement_date')
            else date_str
        )
        len_center_code = 3
        center_code = (
            f"{repeat_to_at_least_length('0', len_center_code - (len(line.get('cost_center_code'))))}"
            f"{line.get('cost_center_code')}"
            if line.get('cost_center_code')
            else None
        )

        line_content = ""
        line_content += repeat_to_at_least_length(' ', 6)
        line_content += movement_date_str
        line_content += date_str
        # line_content += date_str * 2

        doc_num_total = 10
        len_doc_number = len(str(doc_number))
        line_content += repeat_to_at_least_length(' ', doc_num_total - len_doc_number)
        line_content += str(doc_number)

        if len(line_content) != 32:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 34")

        line_content += '70'  # DEFAULT FOR THE MOMENT

        title_total = 30
        title = normalize_text(line.get('accounting_pricing_name'), title_total)
        line_content += title
        line_content += repeat_to_at_least_length(' ', title_total - len(title))

        # declare_as / amount sign already resolved in get_accounting_lines.
        debt, have = _line_debt_have(line)

        debt_str = f"{debt:.6f}"
        have_str = f"{have:.6f}"
        debt_len = 16 - len(debt_str)
        have_len = 16 - len(have_str)
        line_content += repeat_to_at_least_length(' ', debt_len)
        line_content += debt_str
        line_content += repeat_to_at_least_length(' ', have_len)
        line_content += have_str

        if len(line_content) != 96:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 98")

        accounting_account_len = 12 - len(accounting_account)
        line_content += repeat_to_at_least_length(' ', accounting_account_len)
        line_content += accounting_account

        line_content += '01'

        register_number, next_register_number = _assign_register_number(
            line, register_numbers_by_key, next_register_number,
        )
        register_number_str = str(register_number)
        if len(register_number_str) > 6:
            raise Exception(
                f"Register number {register_number} exceeds 6 characters"
            )
        line_content += repeat_to_at_least_length(' ', 6 - len(register_number_str))
        line_content += register_number_str

        if len(line_content) != 116:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 116")

        # CURRENTLY EMPTY
        line_content += repeat_to_at_least_length(' ', 155)

        # has_iva = line.get('iva_accounting')
        iva_base_total = _sum_iva_values(iva_values, 'base')
        iva_tax_total = _sum_iva_values(iva_values, 'tax')
        # Return invoices keep signed (negative) IVA bases; still emit IR02.
        has_iva = (
            iva_base_total != 0
            and line.get('category') == 'invoice'
            and line.get('subtotal') == 0
        )
        if has_iva:
            line_content += iva_document_code
            # line_accounting_token_len = 2 - len(line.get('iva_accounting').token)
            normalized_acc_name = normalize_text(line.get('main_accounting').name, 30)
            line_accounting_name_len = 30 - len(normalized_acc_name)
            # line_content += repeat_to_at_least_length('0', line_accounting_token_len) + line.iva_accounting.token
            line_content += iva_series_code
            line_content += normalized_acc_name + repeat_to_at_least_length(' ', line_accounting_name_len)
            line_content += iva_operation_code
        else:
            line_content += repeat_to_at_least_length(' ', 49)

        if len(line_content) != 320:
            # print(line_content)
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
            iva = int(float(iva_value)) if iva_amount != 0 and has_iva else 0
            iva_total = float(iva_entry['tax']) if iva != 0 and has_iva else 0.00

            iva_value_str = f"{iva_amount:.6f}"
            iva_total_str = f"{iva_total:.6f}"
            iva_extra_total_str = f"{empty_num_value:.6f}"
            iva_str = f"{iva:.2f}"
            iva_extra_str = f"{empty_num_value:.2f}"

            show_iva = (
                iva_amount != 0
                or (int(float(iva_value)) == 0 and iva_base_total != 0)
            ) and has_iva
            if show_iva:
                line_content += '2' if int(float(iva_value)) == 0 else '1'
            else:
                line_content += ' '
            line_content += repeat_to_at_least_length(' ', len_iva_value - len(iva_value_str))
            line_content += iva_value_str
            line_content += repeat_to_at_least_length(' ', len_percentage - len(iva_str))
            line_content += iva_str
            line_content += repeat_to_at_least_length(' ', len_percentage - len(iva_extra_str))
            line_content += iva_extra_str
            line_content += repeat_to_at_least_length(' ', len_iva_value - len(iva_total_str))
            line_content += iva_total_str
            line_content += repeat_to_at_least_length(' ', len_iva_value - len(iva_extra_total_str))
            line_content += iva_extra_total_str

        if len(line_content) != 572:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 572")

        line_content += repeat_to_at_least_length(' ', 53)
        for i in range(6):
            empty_num_value_str = f"{empty_num_value:.6f}"
            len_empty_num_value_str = 16 - len(empty_num_value_str)
            line_content += repeat_to_at_least_length(' ', 8)
            line_content += repeat_to_at_least_length(' ', len_empty_num_value_str)
            line_content += empty_num_value_str

        if len(line_content) != 769:
            #  print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 769")

        if has_iva:
            len_main_account_code = 12 - len(main_account_code)
            line_content += main_account_code + repeat_to_at_least_length(' ', len_main_account_code)
            line_content += '002'  # 002 is EUR
        else:
            line_content += repeat_to_at_least_length(' ', 15)

        change_total = 1  # so far default value
        change_total_str = f"{change_total:.6f}"
        len_change_total_str = 12 - len(change_total_str)
        line_content += repeat_to_at_least_length(' ', len_change_total_str)
        line_content += change_total_str
        if center_code:
            len_iva_account_code = 6 - len(center_code)
            line_content += repeat_to_at_least_length('0', len_iva_account_code) + center_code
        else:
            line_content += repeat_to_at_least_length(' ', 6)

        if len(line_content) != 802:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 802")

        for j in range(8):
            empty_num_value_str = f"{empty_num_value:.6f}"
            len_empty_num_value_str = 16 - len(empty_num_value_str)
            line_content += repeat_to_at_least_length(' ', len_empty_num_value_str)
            line_content += empty_num_value_str

        if len(line_content) != 930:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 930")

        line_content += repeat_to_at_least_length(' ', 33)

        change_total_str = f"{change_total:.6f}"
        len_change_total_str = 12 - len(change_total_str)
        line_content += repeat_to_at_least_length(' ', len_change_total_str)
        line_content += change_total_str

        if len(line_content) != 975:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 975")

        line_content += repeat_to_at_least_length(' ', 147)

        if len(line_content) != 1122:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 1122")

        for k in range(12):
            empty_num_value_str = f"{empty_num_value:.6f}"
            len_empty_num_value_str = 16 - len(empty_num_value_str)
            line_content += repeat_to_at_least_length(' ', len_empty_num_value_str)
            line_content += empty_num_value_str

        line_content += repeat_to_at_least_length(' ', 105)
        line_content += ' 0' * 3

        if len(line_content) != 1425:
            # print(line_content)
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

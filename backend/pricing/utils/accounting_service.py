from collections import defaultdict
from datetime import datetime
from io import BytesIO
import json
from decimal import Decimal

from django.db import transaction
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from billing.models import Invoice, InvoiceLineItem, PaymentMovement
from billing.utils.sgt_txt_service import normalize_text, remove_accents
from contract.models import Contract, ContractUseType, PaymentType
from coredata.models import Bank, ConfigProject
from coredata.utils.other_utils import round_ceil
from pricing.models import (
    AccountingConcept,
    AccountingConfig,
    AccountingCostCenter,
    AccountingPricing,
    LineItemType,
    PriceInterval,
    PriceRate,
    PriceVariableInterval,
    Product,
    ProductOrigin,
)
from service.models import Company, Exploitation


IVA_VALUES_TEMPLATE = {
    '0.00': {'base': 0.00, 'tax': 0.00},
    '10.00': {'base': 0.00, 'tax': 0.00},
    '21.00': {'base': 0.00, 'tax': 0.00},
    '50.00': {'base': 0.00, 'tax': 0.00},
}


def _empty_iva_values():
    return {percent: dict(amounts) for percent, amounts in IVA_VALUES_TEMPLATE.items()}


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


def _empty_iva_accumulator():
    """Per-percent base/tax totals built from per-line rounded amounts."""
    return defaultdict(lambda: {'base': Decimal('0'), 'tax': Decimal('0')})


def _rounded_money(value):
    """Same 2-decimal rounding used when invoices store price/tax_price."""
    return Decimal(str(round_ceil(value)))


def _add_iva_amount(accumulator, percent_key, base=0, tax=0, sign=1):
    entry = accumulator[percent_key]
    signed = Decimal(sign)
    entry['base'] += signed * _rounded_money(base)
    entry['tax'] += signed * _rounded_money(tax)


def _merge_iva_amounts(dest, source, sign=1):
    signed = Decimal(sign)
    for percent_key, amounts in (source or {}).items():
        if isinstance(amounts, dict):
            base = amounts.get('base', 0)
            tax = amounts.get('tax', 0)
        else:
            # Legacy accumulator stored only the taxable base.
            base = amounts
            tax = 0
        entry = dest[percent_key]
        entry['base'] += signed * _decimal_amount(base)
        entry['tax'] += signed * _decimal_amount(tax)


def get_accounting_lines(accounting_pricings, invoices, movements, endowment_invoices=None, irrecoverable_invoices=None):
    #
    # CATEGORIES
    # 'invoice': HANDLES INVOICES AS A WHOLE
    #   normal: issue_date, split by origins and contract use types
    #   endowment: endowment_date, optionally subtracted from the normal line
    #   irrecoverable: irrecoverable_date, optionally subtracted from endowment
    #     (or from normal when no endowment pricing matches)
    #   separate_by_origin: invoices still share that pricing, but the
    #     generated line is split by invoice origin and the origin name
    #     is appended to the title
    # 'lineitems': HANDLES INVOICE LINES DEPEDING ON RELATIONS IN ACCOUNTING PRICING
    # 'payment': HANDLES PAYMENT MOVEMENTS AS A WHOLE
    #   match by payment_type, national/foreign IBAN, incoming/outgoing,
    #   invoice_category and, for a BANK_PAYMENT-only pricing, payment_origin.
    #   Empty payment_origin handles box office and post office. A single
    #   origin is more specific. A BANK_PAYMENT movement with no origin
    #   counts as box office. is_default is last resource.
    #   When is_default, lines are split by payment type and the payment
    #   type name is appended to the title (same idea as invoice origin).
    #   grouped_lines sums by movement_date (and payment_type when
    #   separate_by_type or is_default). When separate_by_payment_origin,
    #   BANK_PAYMENT lines are also summed by movement origin and that
    #   origin name is appended to the title. Otherwise one line per movement.
    #   That payment account is declared as debt. The same total is also
    #   declared as have on the original invoice/clients account, using the
    #   payment line's name and the same split (one have line per payment
    #   line). Commitment-deposit payments (no invoice) still get that have
    #   on the matched clients account via the commitment contract.
    #   Piggy-bank payments follow AccountingConfig (movement debt/have +
    #   sign, optional counter on a selected pricing). When
    #   include_piggy_status_payments is on, status payment_status_piggy_token
    #   movements are treated as piggy-bank even with invoice/commitment/BALANCE.
    #   When payment lines are not grouped, debt stays one per movement
    #   while have is still summed by movement_date (and payment type when
    #   is_default) under the payment line's name.
    #   When an endowment/irrecoverable invoice is collected and there is no
    #   payment pricing for that invoice_category, the movement falls back to
    #   a normal payment pricing. The paid amount is also undeclared from the
    #   matching endowment/irrecoverable invoice pricing (with additional
    #   lines). If that pricing has undeclare_previous, the previous tier
    #   (normal for endowment; endowment then normal for irrecoverable) is
    #   restored for the paid amount, and the payment have lands on the
    #   normal clients account.
    #
    # OUTPUT ORDER: invoice -> undeclare -> payment-restore -> lineitem ->
    #   payment have -> payment.
    # Within invoices, lines with both taxes and subtotals come first.
    # is_default pricings stay first inside that group.
    #
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
            'origins',
            'contract_types',
            'payment_types',
            'aditional_lines',
            'aditional_lines__accounting_concept',
            'aditional_lines__accounting_concept__type',
        ).order_by(
            'accounting_concept__category',
            '-is_default',
            'id',
        )

    invoice_amounts, undeclare_amounts = _group_invoice_amounts(
        accounting_pricings,
        invoices,
        endowment_invoices,
        irrecoverable_invoices,
    )
    lineitem_amounts = _group_lineitem_amounts(accounting_pricings, invoices)
    (
        payment_amounts,
        payment_debt_amounts,
        payment_restore_amounts,
        payment_undeclare_amounts,
        payment_counter_amounts,
    ) = _group_payment_amounts(accounting_pricings, movements)
    _merge_invoice_amount_groups(undeclare_amounts, payment_undeclare_amounts)

    iva_accountings = AccountingPricing.objects.filter(
        is_active=True,
        accounting_concept__category='invoice',
        accounting_concept__type__add_taxes=True,
    )

    invoice_lines = []
    undeclare_lines = []
    payment_restore_lines = []
    lineitem_lines = []
    payment_debt_lines = []
    payment_lines = []
    for accounting_pricing in accounting_pricings:
        concept = accounting_pricing.accounting_concept
        iva_accounting = iva_accountings.filter(exploitation=accounting_pricing.exploitation, accounting_concept__type__add_subtotals=False).first()
        main_accounting = iva_accountings.filter(exploitation=accounting_pricing.exploitation, accounting_concept__type__add_subtotals=True, is_default=True).first()
        if not concept or not concept.is_active:
            continue

        category = concept.category
        if category == 'invoice':
            invoice_lines.extend(_expand_with_additional_lines(
                accounting_pricing,
                _get_invoice_category_lines(
                    accounting_pricing,
                    invoice_amounts.get(accounting_pricing.id),
                    iva_accounting,
                    main_accounting,
                ),
            ))
            undeclare_lines.extend(_expand_with_additional_lines(
                accounting_pricing,
                _get_invoice_category_lines(
                    accounting_pricing,
                    undeclare_amounts.get(accounting_pricing.id),
                    iva_accounting,
                    main_accounting,
                    require_values=True,
                    undeclared=True,
                ),
            ))
            payment_restore_lines.extend(_expand_with_additional_lines(
                accounting_pricing,
                _get_invoice_category_lines(
                    accounting_pricing,
                    payment_restore_amounts.get(accounting_pricing.id),
                    iva_accounting,
                    main_accounting,
                    require_values=True,
                ),
            ))
            for entry in payment_debt_amounts.get(accounting_pricing.id, ()):
                debt_line = _get_payment_debt_line(
                    accounting_pricing,
                    entry.get('total'),
                    main_accounting,
                    line_name=entry.get('line_name'),
                    movement_date=entry.get('movement_date'),
                    declare_as=entry.get('declare_as') or 'have',
                )
                if debt_line:
                    payment_debt_lines.extend(_expand_with_additional_lines(
                        accounting_pricing,
                        [debt_line],
                    ))
        elif category == 'lineitem':
            new_line = _get_lineitem_category_line(
                accounting_pricing,
                lineitem_amounts.get(accounting_pricing.id),
                iva_accounting,
                main_accounting,
            )
            if new_line:
                lineitem_lines.extend(_expand_with_additional_lines(
                    accounting_pricing,
                    [new_line],
                ))
        elif category == 'payment':
            payment_lines.extend(_expand_with_additional_lines(
                accounting_pricing,
                _get_payment_category_lines(
                    accounting_pricing,
                    payment_amounts.get(accounting_pricing.id),
                    iva_accounting,
                    main_accounting,
                ),
            ))

    # Piggy-bank counters may point at any accounting pricing (often clients).
    emitted_counter_ids = {p.id for p in accounting_pricings}
    for pricing_id, entries in (payment_counter_amounts or {}).items():
        if pricing_id in emitted_counter_ids:
            continue
        counter_pricing = AccountingPricing.objects.filter(
            id=pricing_id,
            is_active=True,
        ).select_related(
            'accounting_concept',
            'accounting_concept__type',
            'exploitation',
        ).first()
        if not counter_pricing or not counter_pricing.accounting_concept:
            continue
        iva_accounting = iva_accountings.filter(
            exploitation=counter_pricing.exploitation,
            accounting_concept__type__add_subtotals=False,
        ).first()
        main_accounting = iva_accountings.filter(
            exploitation=counter_pricing.exploitation,
            accounting_concept__type__add_subtotals=True,
            is_default=True,
        ).first()
        for entry in entries:
            counter_line = _get_payment_debt_line(
                counter_pricing,
                entry.get('total'),
                main_accounting,
                line_name=entry.get('line_name'),
                movement_date=entry.get('movement_date'),
                declare_as=entry.get('declare_as') or 'have',
            )
            if counter_line:
                payment_debt_lines.extend(_expand_with_additional_lines(
                    counter_pricing,
                    [counter_line],
                ))

    for accounting_pricing in accounting_pricings:
        for entry in (payment_counter_amounts or {}).get(accounting_pricing.id, ()):
            main_accounting = iva_accountings.filter(
                exploitation=accounting_pricing.exploitation,
                accounting_concept__type__add_subtotals=True,
                is_default=True,
            ).first()
            counter_line = _get_payment_debt_line(
                accounting_pricing,
                entry.get('total'),
                main_accounting,
                line_name=entry.get('line_name'),
                movement_date=entry.get('movement_date'),
                declare_as=entry.get('declare_as') or 'have',
            )
            if counter_line:
                payment_debt_lines.extend(_expand_with_additional_lines(
                    accounting_pricing,
                    [counter_line],
                ))

    invoice_lines.sort(key=lambda line: 0 if line.get('is_invoice') else 1)
    undeclare_lines.sort(key=lambda line: 0 if line.get('is_invoice') else 1)
    payment_restore_lines.sort(key=lambda line: 0 if line.get('is_invoice') else 1)

    return (
        invoice_lines
        + undeclare_lines
        + payment_restore_lines
        + lineitem_lines
        + payment_debt_lines
        + payment_lines
    )


_INVOICE_CATEGORY_NORMAL = 'normal'
_INVOICE_CATEGORY_ENDOWMENT = 'endowment'
_INVOICE_CATEGORY_IRRECOVERABLE = 'irrecoverable'

_INVOICE_CATEGORY_ALIASES = {
    'normal': _INVOICE_CATEGORY_NORMAL,
    'endowment': _INVOICE_CATEGORY_ENDOWMENT,
    'endownment': _INVOICE_CATEGORY_ENDOWMENT,
    'irrecoverable': _INVOICE_CATEGORY_IRRECOVERABLE,
    'irrecuperable': _INVOICE_CATEGORY_IRRECOVERABLE,
}


def _normalize_invoice_category(value):
    if not value:
        return _INVOICE_CATEGORY_NORMAL
    key = str(value).strip().lower()
    return _INVOICE_CATEGORY_ALIASES.get(key, key)


def _empty_invoice_bucket():
    return {
        'subtotal': Decimal('0'),
        'total': Decimal('0'),
        'iva_bases': _empty_iva_accumulator(),
    }


def _invoice_spec(accounting_pricing):
    """Origins and contract types together are more specific than either one.

    A pricing with neither filter is the base line: invoices that match no
    specific line of the same category land here.
    """
    origin_ids = {origin.id for origin in accounting_pricing.origins.all()}
    contract_type_ids = {contract_type.id for contract_type in accounting_pricing.contract_types.all()}
    concept = accounting_pricing.accounting_concept
    accounting_type = concept.type if concept else None
    add_subtotals = bool(accounting_type and accounting_type.add_subtotals)
    add_taxes = bool(accounting_type and accounting_type.add_taxes)
    return {
        'id': accounting_pricing.id,
        'level': int(bool(origin_ids)) + int(bool(contract_type_ids)),
        'exploitation_id': accounting_pricing.exploitation_id,
        'origin_ids': origin_ids,
        'contract_type_ids': contract_type_ids,
        'category': _normalize_invoice_category(accounting_pricing.invoice_category),
        'undeclare_previous': bool(accounting_pricing.undeclare_previous),
        'has_taxes_and_subtotals': add_taxes and add_subtotals,
        'separate_by_origin': bool(
            accounting_pricing.separate_by_origin and accounting_pricing.grouped_lines
        ),
    }


def _invoice_matches_spec(spec, row):
    if spec['exploitation_id'] and row['exploitation_id'] != spec['exploitation_id']:
        return False
    if spec['origin_ids'] and row['origin_id'] not in spec['origin_ids']:
        return False
    if spec['contract_type_ids'] and row['use_type_id'] not in spec['contract_type_ids']:
        return False
    return True


def _spec_filter_key(spec):
    return (
        spec['exploitation_id'],
        frozenset(spec['origin_ids']),
        frozenset(spec['contract_type_ids']),
    )


def _matching_specs(specs, row):
    """Pricings that should receive this invoice.

    The most specific origin/contract-type filter wins. Every pricing that
    shares that exact filter (for example a subtotal account and a tax
    account) receives the invoice. A less specific line, including the
    base line, does not.
    """
    matched = [spec for spec in specs or () if _invoice_matches_spec(spec, row)]
    if not matched:
        return []
    best_level = max(spec['level'] for spec in matched)
    best = [spec for spec in matched if spec['level'] == best_level]
    best.sort(key=lambda spec: (spec['exploitation_id'] is None, spec['id']))
    winner_key = _spec_filter_key(best[0])
    return [spec for spec in best if _spec_filter_key(spec) == winner_key]


def _load_invoice_rows(invoices):
    if not hasattr(invoices, 'annotate'):
        return []
    return list(
        invoices.annotate(
            use_type_id=Coalesce(
                'contract__use_type_id',
                'contract_request__use_type_id',
                'contract_termination__contract__use_type_id',
            ),
        ).values(
            'id',
            'exploitation_id',
            'origin_id',
            'use_type_id',
            'subtotal_final',
            'total_final',
        ).distinct()
    )


def _invoice_tax_amounts(invoice_ids):
    """Accumulate per-line rounded base and tax_price, like get_totals().

    Recalculating tax from the summed base (base * percent) drifts from the
    invoice total at volume because each line's tax_price was already rounded.
    """
    amounts = defaultdict(_empty_iva_accumulator)
    if not invoice_ids:
        return amounts
    line_items = InvoiceLineItem.objects.filter(
        invoice_id__in=invoice_ids,
        is_active=True,
    ).only('invoice_id', 'tax_percent', 'price', 'tax_price')
    for line_item in line_items.iterator(chunk_size=2000):
        key = _iva_percent_key(line_item.tax_percent)
        _add_iva_amount(
            amounts[line_item.invoice_id],
            key,
            base=line_item.price,
            tax=line_item.tax_price,
        )
    return amounts


def _add_invoice_to_bucket(bucket, row, tax_amounts, sign):
    signed = Decimal(sign)
    bucket['subtotal'] += signed * _decimal_amount(row['subtotal_final'])
    bucket['total'] += signed * _decimal_amount(row['total_final'])
    _merge_iva_amounts(bucket['iva_bases'], tax_amounts.get(row['id']), sign=sign)


def _invoice_group_key(spec, row):
    if spec.get('separate_by_origin'):
        return row.get('origin_id')
    return None


def _ensure_invoice_group(groups, group_key, origin_name=None):
    bucket = groups.get(group_key)
    if bucket is None:
        bucket = _empty_invoice_bucket()
        bucket['origin_name'] = origin_name
        groups[group_key] = bucket
    return bucket


def _declare_invoice(buckets, specs, row, tax_amounts, sign, origin_names):
    matched = _matching_specs(specs, row)
    for spec in matched:
        group_key = _invoice_group_key(spec, row)
        origin_name = origin_names.get(group_key) if spec.get('separate_by_origin') else None
        bucket = _ensure_invoice_group(buckets[spec['id']], group_key, origin_name)
        _add_invoice_to_bucket(bucket, row, tax_amounts, sign)
    return matched


def _undeclare_invoice(buckets, specs, row, tax_amounts, origin_names):
    """Reverse the invoice only on original accounts that carry tax and subtotal.

    A matching account with only taxes or only the subtotal is left as it was.
    When that account separates by origin, the reversal is split the same way.
    """
    matched = _matching_specs(specs, row)
    for spec in matched:
        if not spec['has_taxes_and_subtotals']:
            continue
        group_key = _invoice_group_key(spec, row)
        origin_name = origin_names.get(group_key) if spec.get('separate_by_origin') else None
        bucket = _ensure_invoice_group(buckets[spec['id']], group_key, origin_name)
        _add_invoice_to_bucket(bucket, row, tax_amounts, -1)
    return matched


def _group_invoice_amounts(accounting_pricings, normal_invoices, endowment_invoices, irrecoverable_invoices):
    """Assign each invoice to the pricings of its category, then undeclare.

    Specific origin and contract-type lines claim their invoices first.
    Anything left goes to the base pricing of that category. Pricings that
    share the same filter all receive the invoice. Endowment with
    undeclare_previous is declared on its own line and the reversal is kept
    apart, so the original normal line stays intact. The reversal is written
    only on original accounts that have both taxes and subtotals. Irrecoverable
    with undeclare_previous does the same against endowment, or against normal
    when no endowment pricing matches.
    """
    specs_by_category = defaultdict(list)
    pricing_ids = []
    for accounting_pricing in accounting_pricings:
        concept = accounting_pricing.accounting_concept
        if not concept or not concept.is_active or concept.category != 'invoice':
            continue
        spec = _invoice_spec(accounting_pricing)
        pricing_ids.append(spec['id'])
        specs_by_category[spec['category']].append(spec)

    buckets = {pricing_id: {} for pricing_id in pricing_ids}
    undeclare_buckets = {pricing_id: {} for pricing_id in pricing_ids}
    origin_names = {}
    if any(
        spec.get('separate_by_origin')
        for specs in specs_by_category.values()
        for spec in specs
    ):
        origin_names = {
            origin.id: origin.name
            for origin in ProductOrigin.objects.all().only('id', 'name')
        }
    normal_rows = _load_invoice_rows(normal_invoices)
    endowment_rows = _load_invoice_rows(endowment_invoices)
    irrecoverable_rows = _load_invoice_rows(irrecoverable_invoices)

    invoice_ids = {row['id'] for row in normal_rows}
    invoice_ids.update(row['id'] for row in endowment_rows)
    invoice_ids.update(row['id'] for row in irrecoverable_rows)
    tax_amounts = _invoice_tax_amounts(invoice_ids)

    normal_specs = specs_by_category[_INVOICE_CATEGORY_NORMAL]
    endowment_specs = specs_by_category[_INVOICE_CATEGORY_ENDOWMENT]
    irrecoverable_specs = specs_by_category[_INVOICE_CATEGORY_IRRECOVERABLE]

    for row in normal_rows:
        _declare_invoice(buckets, normal_specs, row, tax_amounts, 1, origin_names)

    for row in endowment_rows:
        matched = _declare_invoice(buckets, endowment_specs, row, tax_amounts, 1, origin_names)
        if any(spec['undeclare_previous'] for spec in matched):
            _undeclare_invoice(undeclare_buckets, normal_specs, row, tax_amounts, origin_names)

    for row in irrecoverable_rows:
        matched = _declare_invoice(buckets, irrecoverable_specs, row, tax_amounts, 1, origin_names)
        if not any(spec['undeclare_previous'] for spec in matched):
            continue
        if not _undeclare_invoice(undeclare_buckets, endowment_specs, row, tax_amounts, origin_names):
            _undeclare_invoice(undeclare_buckets, normal_specs, row, tax_amounts, origin_names)

    return buckets, undeclare_buckets


def _optional_text(value):
    if value is None:
        return ''
    return str(value).strip()


def _line_concept_token(accounting_pricing, total, undeclared=False):
    """Negative lines and undeclarations use token_return instead of the concept token."""
    concept = accounting_pricing.accounting_concept
    concept_token = concept.token if concept else ''
    token_return = _optional_text(accounting_pricing.token_return)
    if token_return and (undeclared or _as_float(total) < 0):
        return token_return
    return concept_token


def _additional_line_concept_token(additional_line, total):
    """Use token_return when the extra line amount is negative (after is_negative flip).

    Unlike the parent pricing, undeclare status is ignored here: is_negative may
    flip an undeclare into a positive amount that must keep the concept token.
    """
    concept = additional_line.accounting_concept
    concept_token = concept.token if concept else ''
    token_return = _optional_text(additional_line.token_return)
    if token_return and _as_float(total) < 0:
        return token_return
    return concept_token


def _additional_line_title(additional_line, detail_name=None):
    name = _optional_text(additional_line.declared_as) or _optional_text(additional_line.name)
    detail_name = _optional_text(detail_name)
    if not detail_name:
        return name
    return f"{name} {detail_name}".strip()


def _flip_iva_values(iva_values, negative=False):
    source = iva_values or _empty_iva_values()
    return {
        percent: {
            'base': _as_float(amounts.get('base'), negative=negative),
            'tax': _as_float(amounts.get('tax'), negative=negative),
        }
        for percent, amounts in source.items()
    }


def _active_additional_lines(accounting_pricing):
    lines = getattr(accounting_pricing, 'aditional_lines', None)
    if lines is None:
        return []
    return [
        line
        for line in lines.all()
        if line.is_active and line.accounting_concept_id and line.accounting_concept and line.accounting_concept.is_active
    ]


def _build_additional_line_from_parent(parent_line, additional_line):
    """Clone parent amounts onto an extra line (concept/token/name from the extra).

    When is_negative is True, amounts are flipped so a positive parent declaration
    produces a negative extra line (and uses token_return), and the reverse on
    return/undeclare lines.
    """
    concept = additional_line.accounting_concept
    if not concept:
        return None

    flip = bool(additional_line.is_negative)
    total = _as_float(parent_line.get('total'), negative=flip)
    subtotal = _as_float(parent_line.get('subtotal'), negative=flip)
    if total == 0 and subtotal == 0:
        return None

    extra = dict(parent_line)
    extra.update({
        'accounting_concept': _additional_line_concept_token(additional_line, total),
        'accounting_pricing': additional_line.token,
        'accounting_pricing_name': _additional_line_title(additional_line),
        'name': concept.name,
        'category': concept.category,
        'iva': _flip_iva_values(parent_line.get('iva'), negative=flip),
        'subtotal': subtotal,
        'total': total,
    })
    return extra


def _expand_with_additional_lines(accounting_pricing, lines):
    """After each parent line, emit its active AccountingAdditionalLine clones."""
    parent_lines = list(lines or [])
    extras = _active_additional_lines(accounting_pricing)
    if not extras or not parent_lines:
        return parent_lines

    expanded = []
    for parent_line in parent_lines:
        expanded.append(parent_line)
        for additional_line in extras:
            extra = _build_additional_line_from_parent(parent_line, additional_line)
            if extra:
                expanded.append(extra)
    return expanded


def _line_title(accounting_pricing, detail_name=None):
    """declared_as is the line title. When empty, the line keeps name.

    detail_name is appended for splits such as invoice origin or payment type.
    """
    name = _optional_text(accounting_pricing.declared_as) or _optional_text(accounting_pricing.name)
    detail_name = _optional_text(detail_name)
    if not detail_name:
        return name
    return f"{name} {detail_name}".strip()


def _invoice_line_name(accounting_pricing, origin_name):
    return _line_title(accounting_pricing, origin_name)


def _payment_detail_name(payment_type_name=None, origin_name=None):
    parts = [_optional_text(payment_type_name), _optional_text(origin_name)]
    parts = [part for part in parts if part]
    if not parts:
        return None
    return ' '.join(parts)


def _payment_line_name(base_name, payment_type_name=None):
    base_name = _optional_text(base_name)
    payment_type_name = _optional_text(payment_type_name)
    if not payment_type_name:
        return base_name
    return f"{base_name} {payment_type_name}".strip()


def _sorted_invoice_groups(groups):
    if not groups:
        return [(None, _empty_invoice_bucket())]
    ordered = sorted(
        groups.items(),
        key=lambda item: (
            (item[1].get('origin_name') or '').lower(),
            item[0] is None,
            item[0] or 0,
        ),
    )
    return [
        (bucket.get('origin_name') or None, bucket)
        for _group_key, bucket in ordered
    ]


def _get_invoice_category_lines(
    accounting_pricing,
    groups,
    iva_accounting=None,
    main_accounting=None,
    require_values=False,
    undeclared=False,
):
    lines = []
    for origin_name, bucket in _sorted_invoice_groups(groups):
        line = _get_invoice_category_line(
            accounting_pricing,
            bucket,
            iva_accounting,
            main_accounting,
            origin_name=origin_name,
            undeclared=undeclared,
        )
        if not line:
            continue
        if require_values and not _invoice_line_has_values(line):
            continue
        lines.append(line)
    return lines


def _get_invoice_category_line(accounting_pricing, bucket, iva_accounting = None, main_accounting = None, origin_name = None, undeclared = False):
    concept = accounting_pricing.accounting_concept
    accounting_type = concept.type
    add_subtotals = bool(accounting_type and accounting_type.add_subtotals)
    add_taxes = bool(accounting_type and accounting_type.add_taxes)

    bucket = bucket or _empty_invoice_bucket()
    subtotal = 0.00
    total = 0.00
    iva_values = _lineitem_iva_values(bucket['iva_bases']) if add_taxes else _empty_iva_values()

    if add_subtotals and add_taxes:
        subtotal = _as_float(bucket['subtotal'])
        total = _as_float(bucket['total'])
    elif add_subtotals:
        subtotal = _as_float(bucket['subtotal'])
        total = subtotal
    elif add_taxes:
        total = _sum_iva_values(iva_values, 'tax')

    line = {
        'accounting_concept': _line_concept_token(accounting_pricing, total, undeclared=undeclared),
        'accounting_pricing': accounting_pricing.token,
        'accounting_pricing_name': _invoice_line_name(accounting_pricing, origin_name),
        'name': concept.name,
        'exploitation': accounting_pricing.exploitation,
        'category': concept.category,
        'invoice_category': _normalize_invoice_category(accounting_pricing.invoice_category),
        'iva': iva_values,
        'subtotal': _as_float(subtotal),
        'total': _as_float(total),
        "is_invoice": concept.category == 'invoice' and add_taxes and add_subtotals,
        'iva_accounting': iva_accounting if concept.category == 'invoice' and add_taxes and not add_subtotals else None,
        'main_accounting': main_accounting,
        'cost_center_code': None,
    }
    if not _invoice_line_has_values(line):
        return None
    return line


def _invoice_line_has_values(line):
    if _as_float(line.get('subtotal')) != 0 or _as_float(line.get('total')) != 0:
        return True
    for amounts in (line.get('iva') or {}).values():
        if _as_float(amounts.get('base')) != 0 or _as_float(amounts.get('tax')) != 0:
            return True
    return False


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
        'iva_bases': _empty_iva_accumulator(),
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
            price = _rounded_money(line_item.price)
            bucket['price'] += price
            bucket['total'] += _rounded_money(line_item.total)
            percent_key = _iva_percent_key(line_item.tax_percent)
            _add_iva_amount(
                bucket['iva_bases'],
                percent_key,
                base=line_item.price,
                tax=line_item.tax_price,
            )
            break

    return buckets


def _lineitem_iva_values(iva_amounts):
    """Map accumulated per-line IVA into the accounting line payload.

    Tax must come from summed round_ceil(tax_price) values (same as
    get_totals / register billing summary), never from recomputing
    percent on the aggregated base.
    """
    iva_values = _empty_iva_values()
    for percent_key, amounts in (iva_amounts or {}).items():
        if percent_key not in iva_values:
            iva_values[percent_key] = {'base': 0.00, 'tax': 0.00}
        if isinstance(amounts, dict):
            iva_values[percent_key]['base'] = _as_float(amounts.get('base'))
            iva_values[percent_key]['tax'] = _as_float(amounts.get('tax'))
        else:
            iva_values[percent_key]['base'] = _as_float(amounts)
            iva_values[percent_key]['tax'] = 0.00
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
        'accounting_concept': _line_concept_token(accounting_pricing, total),
        'accounting_pricing': accounting_pricing.token,
        'accounting_pricing_name': _line_title(accounting_pricing),
        'name': concept.name,
        'exploitation': accounting_pricing.exploitation,
        'category': concept.category,
        'iva': iva_values,
        'subtotal': _as_float(subtotal),
        'total': _as_float(total),
        "is_invoice": False,
        'iva_accounting': iva_accounting if add_taxes and not add_subtotals else None,
        'main_accounting': main_accounting,
        'cost_center_code': accounting_pricing.accounting_cost_center.token if accounting_pricing.accounting_cost_center else None,
    }


_BANK_PAYMENT_TOKEN = 'BANK_PAYMENT'
_PAYMENT_ORIGIN_VALUES = ('box_office', 'post_office')


def _payment_origin_label(origin):
    if origin == 'box_office':
        return _('Box Office')
    if origin == 'post_office':
        return _('Post Office')
    return None


def _movement_payment_origin(payment_type_token, payment_origin):
    """BANK_PAYMENT without an origin is box office."""
    if payment_origin in _PAYMENT_ORIGIN_VALUES:
        return payment_origin
    if payment_type_token == _BANK_PAYMENT_TOKEN:
        return 'box_office'
    return None


def _bank_payment_origin_flags(category, group_values, payment_type_ids, payment_origin, separate_by_payment_origin):
    """Origin filter only when BANK_PAYMENT is the sole payment type.

    Splitting grouped lines by origin applies when BANK_PAYMENT is one of
    the selected types and the pricing groups its lines.
    """
    if category != 'payment':
        return None, False
    tokens = set(
        PaymentType.objects.filter(id__in=list(payment_type_ids or [])).values_list('token', flat=True)
    )
    origin = payment_origin if payment_origin in _PAYMENT_ORIGIN_VALUES else None
    if tokens != {_BANK_PAYMENT_TOKEN}:
        origin = None
    separate = (
        bool(separate_by_payment_origin)
        and bool(group_values)
        and _BANK_PAYMENT_TOKEN in tokens
    )
    return origin, separate


def _payment_spec(accounting_pricing):
    payment_types = list(accounting_pricing.payment_types.all())
    payment_type_ids = {payment_type.id for payment_type in payment_types}
    payment_type_tokens = {
        payment_type.token for payment_type in payment_types if payment_type.token
    }
    national_iban = bool(accounting_pricing.national_iban)
    foreign_iban = bool(accounting_pricing.foreign_iban)
    outgoing_payments = bool(accounting_pricing.outgoing_payments)
    incoming_payments = bool(accounting_pricing.incoming_payments)
    payment_origin = accounting_pricing.payment_origin if accounting_pricing.payment_origin in _PAYMENT_ORIGIN_VALUES else None
    if payment_type_tokens != {_BANK_PAYMENT_TOKEN}:
        payment_origin = None
    level = 0
    if payment_type_ids:
        level += 1
    if national_iban != foreign_iban:
        level += 1
    if outgoing_payments != incoming_payments:
        level += 1
    if payment_origin:
        level += 1
    return {
        'id': accounting_pricing.id,
        'level': level,
        'is_default': bool(accounting_pricing.is_default),
        'exploitation_id': accounting_pricing.exploitation_id,
        'payment_type_ids': payment_type_ids,
        'payment_origin': payment_origin,
        'national_iban': national_iban,
        'foreign_iban': foreign_iban,
        'outgoing_payments': outgoing_payments,
        'incoming_payments': incoming_payments,
        'grouped_lines': bool(accounting_pricing.grouped_lines),
        'separate_by_type': bool(accounting_pricing.separate_by_type),
        'separate_by_payment_origin': (
            bool(accounting_pricing.separate_by_payment_origin)
            and bool(accounting_pricing.grouped_lines)
            and _BANK_PAYMENT_TOKEN in payment_type_tokens
        ),
        'category': _normalize_invoice_category(accounting_pricing.invoice_category),
        'name': _line_title(accounting_pricing),
    }


def _is_spanish_iban(iban):
    return bool(iban) and str(iban).strip().upper().startswith('ES')


def _invoice_match_ids(invoice):
    if invoice is None:
        return None, None
    use_type_id = None
    if invoice.contract_id and invoice.contract is not None:
        use_type_id = invoice.contract.use_type_id
    elif invoice.contract_request_id and invoice.contract_request is not None:
        use_type_id = invoice.contract_request.use_type_id
    elif (
        invoice.contract_termination_id
        and invoice.contract_termination is not None
        and invoice.contract_termination.contract_id
        and invoice.contract_termination.contract is not None
    ):
        use_type_id = invoice.contract_termination.contract.use_type_id
    return invoice.origin_id, use_type_id


def _contract_exploitation_id(contract):
    if contract is None:
        return None
    supply_point = getattr(contract, 'supply_point_default', None)
    if supply_point is None:
        return None
    connection = getattr(supply_point, 'connection', None)
    if connection is None:
        return None
    return connection.exploitation_id


def _payment_contract(payment):
    if payment.contract_id and payment.contract is not None:
        return payment.contract
    invoice = payment.invoice if payment.invoice_id else None
    if invoice is not None: 
        if invoice.contract_id and invoice.contract is not None:
            return invoice.contract
        elif invoice.contract_request_id and invoice.contract_request is not None:
            return Contract.objects.get(contract_request__id=invoice.contract_request_id)
        elif invoice.contract_termination_id and invoice.contract_termination is not None and invoice.contract_termination.contract_id and invoice.contract_termination.contract is not None:
            return invoice.contract_termination.contract
    commitment = payment.commitment_deposit if payment.commitment_deposit_id else None
    if commitment is not None and commitment.contract_id and commitment.contract is not None:
        return commitment.contract
    return None


def _movement_invoice_category(invoice):
    if not invoice:
        return _INVOICE_CATEGORY_NORMAL
    if invoice.endowment_date and invoice.irrecoverable_date:
        return _INVOICE_CATEGORY_IRRECOVERABLE
    if invoice.endowment_date:
        return _INVOICE_CATEGORY_ENDOWMENT
    return _INVOICE_CATEGORY_NORMAL


def _accounting_config_snapshot():
    """Load AccountingConfig once per accounting generation."""
    try:
        config = AccountingConfig.get_solo()
    except Exception:
        return {
            'piggybank_as_negative': False,
            'include_piggy_status_payments': False,
            'incoming_declare_as': 'debt',
            'incoming_sign': 'positive',
            'incoming_counter_declare_as': 'have',
            'incoming_counter_pricing_id': None,
            'return_declare_as': 'have',
            'return_sign': 'positive',
            'return_counter_declare_as': 'debt',
            'return_counter_pricing_id': None,
        }
    return {
        'piggybank_as_negative': bool(config.piggybank_as_negative),
        'include_piggy_status_payments': bool(config.include_piggy_status_payments),
        'incoming_declare_as': config.incoming_declare_as or 'debt',
        'incoming_sign': config.incoming_sign or 'positive',
        'incoming_counter_declare_as': config.incoming_counter_declare_as or 'have',
        'incoming_counter_pricing_id': config.incoming_counter_pricing_id,
        'return_declare_as': config.return_declare_as or 'have',
        'return_sign': config.return_sign or 'positive',
        'return_counter_declare_as': config.return_counter_declare_as or 'debt',
        'return_counter_pricing_id': config.return_counter_pricing_id,
    }


def _piggy_status_token():
    try:
        return ConfigProject.objects.get(token='payment_status_piggy_token').value
    except ConfigProject.DoesNotExist:
        return None


def _is_base_piggybank_payment(row):
    """Classic piggy-bank: no invoice, no commitment, contract or person."""
    return (
        not row.get('has_invoice')
        and not row.get('has_commitment')
        and (row.get('has_contract') or row.get('has_person'))
    )


def _is_piggybank_payment(row, config=None):
    if _is_base_piggybank_payment(row):
        return True
    if config and config.get('include_piggy_status_payments') and row.get('is_piggy_status'):
        return True
    return False


def _is_outgoing_payment(row):
    """Outgoing piggy-bank return (positive movement)."""
    return bool(row.get('is_piggybank')) and bool(row.get('is_positive'))


def _piggybank_direction_rules(row, config):
    """Incoming = deposit (is_positive False); return = refund (is_positive True)."""
    if row.get('is_positive'):
        return {
            'declare_as': config.get('return_declare_as') or 'have',
            'sign': config.get('return_sign') or 'positive',
            'counter_declare_as': config.get('return_counter_declare_as') or 'debt',
            'counter_pricing_id': config.get('return_counter_pricing_id'),
        }
    return {
        'declare_as': config.get('incoming_declare_as') or 'debt',
        'sign': config.get('incoming_sign') or 'positive',
        'counter_declare_as': config.get('incoming_counter_declare_as') or 'have',
        'counter_pricing_id': config.get('incoming_counter_pricing_id'),
    }


def _payment_signed_amount(row, config=None):
    amount = abs(_decimal_amount(row['amount']))
    if row.get('is_piggybank') and config:
        rules = _piggybank_direction_rules(row, config)
        if config.get('piggybank_as_negative'):
            return -amount
        if rules['sign'] == 'negative':
            return -amount
        return amount

    is_positive = bool(row['is_positive'])
    if row.get('is_outgoing'):
        is_positive = not is_positive
    if not is_positive:
        return -amount
    return amount


def _payment_matches_spec(spec, row):
    if spec['exploitation_id'] and row['exploitation_id'] != spec['exploitation_id']:
        return False
    if spec['category'] != row['invoice_category']:
        return False
    if spec['payment_type_ids'] and row['payment_type_id'] not in spec['payment_type_ids']:
        return False
    if spec['payment_origin'] and row.get('payment_origin') != spec['payment_origin']:
        return False
    if row['payment_bank']:
        if _is_spanish_iban(row['payment_bank']):
            if not spec['national_iban']:
                return False
        elif not spec['foreign_iban']:
            return False
    if row['is_outgoing']:
        if not spec['outgoing_payments']:
            return False
    elif not spec['incoming_payments']:
        return False
    return True


def _matching_payment_spec_for_category(specs_by_category, row, category):
    """Most specific non-default pricing wins; is_default is last resource."""
    # Match as if the movement belonged to this invoice_category so fallback
    # from endowment/irrecoverable to normal can reuse the same filters.
    match_row = row
    if row.get('invoice_category') != category:
        match_row = dict(row)
        match_row['invoice_category'] = category

    category_specs = specs_by_category.get(category, {})
    specific = [
        spec for spec in category_specs.get('specific', ())
        if _payment_matches_spec(spec, match_row)
    ]
    if specific:
        best_level = max(spec['level'] for spec in specific)
        best = [spec for spec in specific if spec['level'] == best_level]
        best.sort(key=lambda spec: (spec['exploitation_id'] is None, spec['id']))
        return best[0]

    defaults = category_specs.get('default', ())
    if defaults:
        defaults = sorted(defaults, key=lambda spec: (spec['exploitation_id'] is None, spec['id']))
        return defaults[0]
    return None


def _matching_payment_spec(specs_by_category, row):
    """Most specific non-default pricing wins; is_default is last resource.

    Endowment/irrecoverable movements without a payment pricing for that
    invoice_category fall back to a normal payment pricing.
    """
    category = row['invoice_category']
    spec = _matching_payment_spec_for_category(specs_by_category, row, category)
    if spec:
        return spec, False
    if category in (_INVOICE_CATEGORY_ENDOWMENT, _INVOICE_CATEGORY_IRRECOVERABLE):
        fallback = _matching_payment_spec_for_category(
            specs_by_category,
            row,
            _INVOICE_CATEGORY_NORMAL,
        )
        if fallback:
            return fallback, True
    return None, False


def _should_ignore_payment_movement(movement, commitment_status_token, include_piggy_status=False, piggy_status_token=None):
    if (
        commitment_status_token
        and movement.previous_status_id
        and movement.previous_status
        and movement.previous_status.token == commitment_status_token
    ):
        return True
    payment = movement.payment
    if not payment:
        return True
    is_piggy_status = bool(
        include_piggy_status
        and piggy_status_token
        and movement.current_status_id
        and movement.current_status
        and movement.current_status.token == piggy_status_token
    )
    if is_piggy_status:
        return False
    has_invoice_or_commitment = bool(payment.invoice_id or payment.commitment_deposit_id)
    payment_type_token = movement.payment_type.token if movement.payment_type_id and movement.payment_type else None
    if has_invoice_or_commitment and payment_type_token == 'BALANCE':
        return True
    return False


def _load_payment_rows(movements):
    if not hasattr(movements, 'select_related'):
        return []

    commitment_status_token = None
    try:
        commitment_status_token = ConfigProject.objects.get(token='invoice_status_commitment_token').value
    except ConfigProject.DoesNotExist:
        commitment_status_token = None

    config = _accounting_config_snapshot()
    piggy_status_token = _piggy_status_token() if config.get('include_piggy_status_payments') else None

    queryset = movements.filter(is_active=True).select_related(
        'payment',
        'payment__invoice',
        'payment__invoice__contract',
        'payment__invoice__contract_request',
        'payment__invoice__contract_termination__contract',
        'payment__commitment_deposit',
        'payment__commitment_deposit__contract',
        'payment__commitment_deposit__contract__supply_point_default__connection',
        'payment__contract',
        'payment__contract__supply_point_default__connection',
        'payment__person',
        'payment_type',
        'previous_status',
        'current_status',
    )

    rows = []
    for movement in queryset.iterator(chunk_size=2000):
        # if _should_ignore_payment_movement(
        #     movement, commitment_status_token,
        #     include_piggy_status=config.get('include_piggy_status_payments'),
        #     piggy_status_token=piggy_status_token,
        # ):
        #     continue
        payment = movement.payment
        if payment is None:
            continue
        invoice = payment.invoice
        contract = _payment_contract(payment)
        if invoice is not None:
            exploitation_id = invoice.exploitation_id
            origin_id, use_type_id = _invoice_match_ids(invoice)
            invoice_category = _movement_invoice_category(invoice)
        else:
            exploitation_id = _contract_exploitation_id(contract)
            origin_id = None
            use_type_id = contract.use_type_id if contract is not None else None
            invoice_category = _INVOICE_CATEGORY_NORMAL

        payment_type = movement.payment_type if movement.payment_type_id else None
        payment_type_token = payment_type.token if payment_type else None
        is_piggy_status = bool(
            piggy_status_token
            and movement.current_status_id
            and movement.current_status
            and movement.current_status.token == piggy_status_token
        )
        row = {
            'movement_id': movement.id,
            'movement_date': movement.movement_date,
            'payment_type_id': movement.payment_type_id,
            'payment_type_token': payment_type_token,
            'payment_type_name': _optional_text(payment_type.name) if payment_type else '',
            'payment_origin': _movement_payment_origin(payment_type_token, movement.payment_origin),
            'payment_bank': movement.payment_bank,
            'is_positive': bool(movement.is_positive),
            'amount': payment.amount,
            'has_invoice': bool(payment.invoice_id),
            'has_commitment': bool(payment.commitment_deposit_id),
            'has_contract': bool(contract),
            'has_person': bool(payment.person_id),
            'exploitation_id': exploitation_id,
            'origin_id': origin_id,
            'use_type_id': use_type_id,
            'invoice_category': invoice_category,
            'is_piggy_status': is_piggy_status,
        }
        row['is_piggybank'] = _is_piggybank_payment(row, config)
        row['is_outgoing'] = _is_outgoing_payment(row)
        if row['is_piggybank']:
            rules = _piggybank_direction_rules(row, config)
            row['piggy_declare_as'] = rules['declare_as']
            row['piggy_counter_declare_as'] = rules['counter_declare_as']
            row['piggy_counter_pricing_id'] = rules['counter_pricing_id']
        else:
            row['piggy_declare_as'] = None
            row['piggy_counter_declare_as'] = None
            row['piggy_counter_pricing_id'] = None
        row['signed_amount'] = _payment_signed_amount(row, config)
        rows.append(row)
    return rows


def _invoice_debt_specs(specs_by_category, row, category=None):
    """Original invoice accounts that take this payment as have.

    Invoice payments prefer the most specific origin/contract-type account
    that carries both taxes and the subtotal. Lower-level mains stay
    eligible, so a base clients account is still used when the specific
    match is only taxes or only the subtotal. Commitment-deposit payments
    (no invoice) use the same matching from the commitment contract and
    land on that clients account too. Piggy-bank payments use AccountingConfig
    counter pricing instead of invoice matching.

    category overrides the row invoice_category (used when an
    endowment/irrecoverable collection falls back to a normal payment).
    """
    if row.get('is_piggybank'):
        return []
    if not row.get('has_invoice') and not row.get('has_commitment'):
        return []
    lookup_category = category if category is not None else row['invoice_category']
    specs = specs_by_category.get(lookup_category, ())
    matched = [spec for spec in specs if _invoice_matches_spec(spec, row)]
    mains = [spec for spec in matched if spec['has_taxes_and_subtotals']]
    if mains:
        best_level = max(spec['level'] for spec in mains)
        best = [spec for spec in mains if spec['level'] == best_level]
        best.sort(key=lambda spec: (spec['exploitation_id'] is None, spec['id']))
        return [best[0]]
    if len(matched) == 1:
        return matched
    return []


def _merge_invoice_amount_groups(target, source):
    """Merge payment-triggered invoice group buckets into existing amounts."""
    if not source:
        return target
    for pricing_id, groups in source.items():
        target_groups = target.setdefault(pricing_id, {})
        for group_key, bucket in (groups or {}).items():
            dest = _ensure_invoice_group(
                target_groups,
                group_key,
                origin_name=bucket.get('origin_name'),
            )
            dest['subtotal'] += _decimal_amount(bucket.get('subtotal'))
            dest['total'] += _decimal_amount(bucket.get('total'))
            _merge_iva_amounts(dest['iva_bases'], bucket.get('iva_bases'))
    return target


def _add_payment_amount_to_invoice_groups(groups_by_pricing, specs, row, amount, sign, origin_names, mains_only=False):
    """Add a flat payment amount to invoice declare/undeclare groups."""
    matched = _matching_specs(specs, row)
    written = []
    signed = Decimal(sign) * _decimal_amount(amount)
    if signed == 0:
        return written
    for spec in matched:
        if mains_only and not spec['has_taxes_and_subtotals']:
            continue
        group_key = _invoice_group_key(spec, row)
        origin_name = origin_names.get(group_key) if spec.get('separate_by_origin') else None
        bucket = _ensure_invoice_group(
            groups_by_pricing.setdefault(spec['id'], {}),
            group_key,
            origin_name,
        )
        bucket['subtotal'] += signed
        bucket['total'] += signed
        written.append(spec)
    return written


def _previous_invoice_restore_specs(invoice_specs_by_category, row, current_category):
    """Accounts that were undeclared_previous when current_category was declared."""
    if current_category == _INVOICE_CATEGORY_ENDOWMENT:
        return _matching_specs(
            invoice_specs_by_category.get(_INVOICE_CATEGORY_NORMAL, ()),
            row,
        )
    if current_category == _INVOICE_CATEGORY_IRRECOVERABLE:
        endowment_matched = _matching_specs(
            invoice_specs_by_category.get(_INVOICE_CATEGORY_ENDOWMENT, ()),
            row,
        )
        if endowment_matched:
            return endowment_matched
        return _matching_specs(
            invoice_specs_by_category.get(_INVOICE_CATEGORY_NORMAL, ()),
            row,
        )
    return []


def _apply_payment_category_fallback_undeclare(
    row,
    amount,
    invoice_specs_by_category,
    undeclare_groups,
    restore_groups,
    origin_names,
):
    """Undeclare endowment/irrecoverable invoice lines for a fallback collection.

    When a positive payment on an endowment/irrecoverable invoice has no
    payment pricing for that category, reverse the paid amount on the
    matching invoice pricing. If that pricing used undeclare_previous,
    restore the previous tier for the same amount (mains only).
    """
    current_category = row.get('invoice_category')
    if current_category not in (_INVOICE_CATEGORY_ENDOWMENT, _INVOICE_CATEGORY_IRRECOVERABLE):
        return
    if not row.get('has_invoice') or _decimal_amount(amount) <= 0:
        return

    matched = _add_payment_amount_to_invoice_groups(
        undeclare_groups,
        invoice_specs_by_category.get(current_category, ()),
        row,
        amount,
        -1,
        origin_names,
        mains_only=False,
    )
    if not matched or not any(spec.get('undeclare_previous') for spec in matched):
        return

    restore_specs = _previous_invoice_restore_specs(
        invoice_specs_by_category,
        row,
        current_category,
    )
    mains = [spec for spec in restore_specs if spec.get('has_taxes_and_subtotals')]
    if not mains:
        return
    _add_payment_amount_to_invoice_groups(
        restore_groups,
        mains,
        row,
        amount,
        1,
        origin_names,
        mains_only=True,
    )


def _payment_type_detail(spec, row):
    """Default payment lines split by type and append the type name."""
    if not spec.get('is_default'):
        return None, None
    payment_type_name = _optional_text(row.get('payment_type_name'))
    if not payment_type_name:
        return row.get('payment_type_id'), None
    return row.get('payment_type_id'), payment_type_name


def _payment_origin_detail(spec, row):
    """Grouped BANK_PAYMENT lines split by movement origin.

    Missing origin is already box office, so it stays out of other payment types.
    """
    if not spec.get('separate_by_payment_origin'):
        return None, None
    if row.get('payment_type_token') != _BANK_PAYMENT_TOKEN:
        return None, None
    origin = row.get('payment_origin') or 'box_office'
    return origin, _payment_origin_label(origin)


def _payment_origin_names(invoice_specs_by_category):
    if not any(
        spec.get('separate_by_origin')
        for specs in invoice_specs_by_category.values()
        for spec in specs
    ):
        return {}
    return {
        origin.id: origin.name
        for origin in ProductOrigin.objects.all().only('id', 'name')
    }


def _accumulate_payment_rows(rows, specs_by_category, specs_by_id, invoice_specs_by_category):
    """Split each movement into a payment line and a matching counter line.

    Normal payments: debt on the payment account, have on the invoice account.
    Piggy-bank payments: declare_as / counter from AccountingConfig.
    """
    buckets = {pricing_id: [] for pricing_id in specs_by_id}
    grouped_totals = defaultdict(lambda: defaultdict(lambda: Decimal('0')))
    debt_totals = defaultdict(lambda: Decimal('0'))
    counter_totals = defaultdict(lambda: Decimal('0'))
    restore_groups = {}
    undeclare_groups = {}
    origin_names = _payment_origin_names(invoice_specs_by_category)

    for row in rows:
        spec, used_fallback = _matching_payment_spec(specs_by_category, row)
        if not spec:
            continue
        amount = row['signed_amount']
        debt_category = (
            _INVOICE_CATEGORY_NORMAL
            if used_fallback
            else row['invoice_category']
        )
        invoice_specs = _invoice_debt_specs(
            invoice_specs_by_category,
            row,
            category=debt_category,
        )
        invoice_id = invoice_specs[0]['id'] if invoice_specs else None
        default_type_key, payment_type_name = _payment_type_detail(spec, row)
        movement_declare_as = row.get('piggy_declare_as') or 'debt'
        counter_declare_as = row.get('piggy_counter_declare_as')
        counter_pricing_id = row.get('piggy_counter_pricing_id')
        if row.get('is_piggybank'):
            invoice_id = None

        if used_fallback:
            _apply_payment_category_fallback_undeclare(
                row,
                amount,
                invoice_specs_by_category,
                undeclare_groups,
                restore_groups,
                origin_names,
            )

        if not spec['grouped_lines']:
            buckets[spec['id']].append({
                'movement_date': row['movement_date'],
                'total': amount,
                'payment_type_name': payment_type_name,
                'declare_as': movement_declare_as,
            })
            if invoice_id is not None:
                debt_totals[(
                    spec['id'],
                    invoice_id,
                    row['movement_date'],
                    default_type_key,
                    payment_type_name,
                    None,
                    None,
                    'have',
                )] += amount
            elif (
                row.get('is_piggybank')
                and counter_pricing_id
                and counter_declare_as
                and counter_declare_as != 'none'
            ):
                counter_totals[(
                    counter_pricing_id,
                    row['movement_date'],
                    default_type_key,
                    payment_type_name,
                    None,
                    None,
                    counter_declare_as,
                    spec['id'],
                )] += amount
            continue

        separate_by_type = (
            bool(spec['is_default'])
            or (spec['separate_by_type'] and len(spec['payment_type_ids']) > 1)
        )
        type_key = row['payment_type_id'] if separate_by_type else None
        origin_key, origin_name = _payment_origin_detail(spec, row)
        group_key = (
            row['movement_date'],
            type_key,
            payment_type_name,
            origin_key,
            origin_name,
            movement_declare_as,
        )
        grouped_totals[spec['id']][group_key] += amount
        if invoice_id is not None:
            debt_totals[(
                spec['id'],
                invoice_id,
                row['movement_date'],
                type_key,
                payment_type_name,
                origin_key,
                origin_name,
                'have',
            )] += amount
        elif (
            row.get('is_piggybank')
            and counter_pricing_id
            and counter_declare_as
            and counter_declare_as != 'none'
        ):
            counter_totals[(
                counter_pricing_id,
                row['movement_date'],
                type_key,
                payment_type_name,
                origin_key,
                origin_name,
                counter_declare_as,
                spec['id'],
            )] += amount

    for pricing_id, groups in grouped_totals.items():
        for (
            movement_date,
            _payment_type_id,
            payment_type_name,
            _origin_key,
            origin_name,
            declare_as,
        ), total in groups.items():
            buckets[pricing_id].append({
                'movement_date': movement_date,
                'total': total,
                'payment_type_name': _payment_detail_name(payment_type_name, origin_name),
                'declare_as': declare_as,
            })

    debt_entries = defaultdict(list)
    for (
        payment_id,
        invoice_id,
        movement_date,
        _type_key,
        payment_type_name,
        _origin_key,
        origin_name,
        declare_as,
    ), total in debt_totals.items():
        spec = specs_by_id[payment_id]
        debt_entries[invoice_id].append({
            'total': total,
            'movement_date': movement_date,
            'line_name': _payment_line_name(
                spec.get('name') or '',
                _payment_detail_name(payment_type_name, origin_name),
            ),
            'payment_pricing_id': payment_id,
            'declare_as': declare_as,
        })
    for entries in debt_entries.values():
        entries.sort(key=lambda entry: (
            (entry['line_name'] or '').lower(),
            entry['movement_date'] is None,
            str(entry['movement_date'] or ''),
            entry['payment_pricing_id'],
        ))

    counter_entries = defaultdict(list)
    for (
        counter_pricing_id,
        movement_date,
        _type_key,
        payment_type_name,
        _origin_key,
        origin_name,
        declare_as,
        payment_id,
    ), total in counter_totals.items():
        spec = specs_by_id.get(payment_id) or {}
        counter_entries[counter_pricing_id].append({
            'total': total,
            'movement_date': movement_date,
            'line_name': _payment_line_name(
                spec.get('name') or '',
                _payment_detail_name(payment_type_name, origin_name),
            ),
            'payment_pricing_id': payment_id,
            'declare_as': declare_as,
        })
    for entries in counter_entries.values():
        entries.sort(key=lambda entry: (
            (entry['line_name'] or '').lower(),
            entry['movement_date'] is None,
            str(entry['movement_date'] or ''),
            entry['payment_pricing_id'],
        ))

    return buckets, debt_entries, restore_groups, undeclare_groups, counter_entries


def _group_payment_amounts(accounting_pricings, movements):
    """Assign each payment movement to one payment accounting pricing.

    Non-default pricings are matched by payment type, IBAN nationality,
    incoming/outgoing, invoice_category and, when BANK_PAYMENT is the only
    type, payment origin. is_default is only used when
    nothing else matches. Endowment/irrecoverable movements without a
    matching payment category fall back to normal payment pricing and
    undeclare the paid amount on the related invoice pricing.

    The payment account receives the amount as debt (or AccountingConfig
    declare_as for piggy-bank). The counterpart lands on the invoice
    account or on AccountingConfig counter pricing.
    """
    specs_by_category = defaultdict(lambda: {'specific': [], 'default': []})
    specs_by_id = {}
    invoice_specs_by_category = defaultdict(list)
    for accounting_pricing in accounting_pricings:
        concept = accounting_pricing.accounting_concept
        if not concept or not concept.is_active:
            continue
        if concept.category == 'invoice':
            spec = _invoice_spec(accounting_pricing)
            invoice_specs_by_category[spec['category']].append(spec)
            continue
        if concept.category != 'payment':
            continue
        spec = _payment_spec(accounting_pricing)
        specs_by_id[spec['id']] = spec
        bucket_key = 'default' if spec['is_default'] else 'specific'
        specs_by_category[spec['category']][bucket_key].append(spec)

    return _accumulate_payment_rows(
        _load_payment_rows(movements),
        specs_by_category,
        specs_by_id,
        invoice_specs_by_category,
    )


def _get_payment_category_lines(accounting_pricing, bucket_entries, iva_accounting=None, main_accounting=None):
    concept = accounting_pricing.accounting_concept
    accounting_type = concept.type
    add_subtotals = bool(accounting_type and accounting_type.add_subtotals)
    add_taxes = bool(accounting_type and accounting_type.add_taxes)
    cost_center_code = (
        accounting_pricing.accounting_cost_center.token
        if accounting_pricing.accounting_cost_center_id and accounting_pricing.accounting_cost_center
        else None
    )
    invoice_category = _normalize_invoice_category(accounting_pricing.invoice_category)
    lines = []

    for entry in bucket_entries or ():
        total_amount = _as_float(entry.get('total'))
        if total_amount == 0:
            continue

        iva_values = _empty_iva_values()
        subtotal = 0.00
        total = total_amount
        if add_subtotals:
            subtotal = total_amount
            total = total_amount
        elif add_taxes:
            total = total_amount

        lines.append({
            'accounting_concept': _line_concept_token(accounting_pricing, total),
            'accounting_pricing': accounting_pricing.token,
            'accounting_pricing_name': _line_title(
                accounting_pricing,
                entry.get('payment_type_name'),
            ),
            'name': concept.name,
            'exploitation': accounting_pricing.exploitation,
            'category': concept.category,
            'invoice_category': invoice_category,
            'iva': iva_values,
            'subtotal': _as_float(subtotal),
            'total': _as_float(total),
            'movement_date': entry.get('movement_date'),
            'is_invoice': False,
            'declare_as': entry.get('declare_as') or 'debt',
            'iva_accounting': iva_accounting if add_taxes and not add_subtotals else None,
            'main_accounting': main_accounting,
            'cost_center_code': cost_center_code,
        })
    return lines


def _get_payment_debt_line(
    accounting_pricing,
    total,
    main_accounting=None,
    line_name=None,
    movement_date=None,
    declare_as='have',
):
    """Counterpart line for a payment (invoice have, or piggy-bank counter)."""
    if total is None:
        return None
    total_amount = _as_float(total)
    if total_amount == 0:
        return None
    concept = accounting_pricing.accounting_concept
    if not concept:
        return None
    line = {
        'accounting_concept': _line_concept_token(accounting_pricing, total_amount),
        'accounting_pricing': accounting_pricing.token,
        'accounting_pricing_name': line_name if line_name else _line_title(accounting_pricing),
        'name': concept.name,
        'exploitation': accounting_pricing.exploitation,
        'category': concept.category,
        'invoice_category': _normalize_invoice_category(accounting_pricing.invoice_category),
        'iva': _empty_iva_values(),
        'subtotal': 0.00,
        'total': total_amount,
        'is_invoice': False,
        'declare_as': declare_as or 'have',
        'iva_accounting': None,
        'main_accounting': main_accounting,
        'cost_center_code': None,
    }
    if movement_date is not None:
        line['movement_date'] = movement_date
    return line


def generate_general_accounting(request):
    content_file = BytesIO()
    max_characters = 2126
    request_date = request.data.get('start_date')
    date = datetime.strptime(request_date, "%Y-%m-%d")
    last_document = None
    
    date_str = date.strftime("%Y%m%d")
    doc_number = str(int(last_document.token) + 1) if last_document else '158429'
    
    invoice_type_invoice_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
    invoice_status_pending_token = ConfigProject.objects.get(token='invoice_status_pending_token').value
    commitment_status_token = ConfigProject.objects.get(token='invoice_status_commitment_token').value
    invoice_status_payoff_token = ConfigProject.objects.get(token='invoice_status_payoff_token').value
    accounting_pricings = AccountingPricing.objects.filter(is_active=True).order_by(
        'accounting_concept__category',
        'accounting_concept__name',
        '-is_default',
        'id',
    )
    
    invoices = Invoice.objects.filter(
        issue_date=date, 
        type_final=invoice_type_invoice_token,
        is_active=True).exclude(
            status__token=invoice_status_pending_token
            ).distinct()
    # print("total invoices: ", invoices.count())
    endowment_invoices = Invoice.objects.filter(endowment_date=date, is_active=True).distinct()
    irrecoverable_invoices = Invoice.objects.filter(irrecoverable_date=date, is_active=True).distinct()
    movements = PaymentMovement.objects.filter(
        timestamp__date=date).exclude(
        previous_status__token = commitment_status_token
        ).exclude(
            payment_type__token = 'BALANCE'
            ).distinct()
    # print("total invoices: ", invoices.count())
    # print("total endowment invoices: ", endowment_invoices.count())
    # print("total irrecoverable invoices: ", irrecoverable_invoices.count())
    # print("total movements: ", movements.count())
    if invoices.count() == 0 and endowment_invoices.count() == 0 and irrecoverable_invoices.count() == 0 and movements.count() == 0:
        raise Exception(f"{_('No values found to generate accounting')}")
    
    total_invoices = sum(invoice.total_final for invoice in invoices)
    # print("total invoices: ", total_invoices)
    
    lines = get_accounting_lines(
        accounting_pricings,
        invoices,
        movements,
        endowment_invoices,
        irrecoverable_invoices,
    )
    
    # print("total lines: ", len(lines))
    # for line in lines:
    #     print(line)
    
    # raise Exception("stop here")
    
    for line in lines:

        """
        REGISTRE AMB 2126 CHARS A CADA LINIA
        """
        # print("line")
        # print(line)
        iva_values = line.get('iva')
        
        empty_num_value = 0.00
        iva_account_code = f"{line.get('iva_accounting').accounting_concept.token}{'0' * (12 - len(line.get('iva_accounting').accounting_concept.token) - len(line.get('iva_accounting').token))}{line.get('iva_accounting').token}" if line.get('iva_accounting') else ''
        main_account_code = f"{line.get('main_accounting').accounting_concept.token}{'0' * (12 - len(line.get('main_accounting').accounting_concept.token) - len(line.get('main_accounting').token))}{line.get('main_accounting').token}" if line.get('main_accounting') else ''
        movement_date_str = (line.get('movement_date')).strftime("%Y%m%d") if 'movement_date' in line and line.get('movement_date') else date_str
        len_center_code = 3
        center_code = f"{repeat_to_at_least_length('0', len_center_code - (len(line.get('cost_center_code'))))}{line.get('cost_center_code')}" if line.get('cost_center_code') else None
        
        line_content = ""
        line_content += repeat_to_at_least_length(' ', 6)
        line_content += movement_date_str
        line_content += date_str
        # line_content += date_str * 2
        
        doc_num_total = 10
        len_doc_number = len(str(doc_number))
        line_content += repeat_to_at_least_length(' ', doc_num_total-len_doc_number)
        line_content += str(doc_number)
        
        if len(line_content) != 32:
            # print(line_content)
            raise Exception(f"Line {line_content} has {len(line_content)} characters instead of 34")
        
        line_content += '60' # DEFAULT FOR THE MOMENT
        
        title_total = 30
        title = normalize_text(line.get('accounting_pricing_name'), title_total)
        line_content += title
        line_content += repeat_to_at_least_length(' ', title_total-len(title))

        # if total is negative it goes into the other line
        declare_as = line.get('declare_as')
        if declare_as == 'have':
            debt = 0.00
            have = line.get('total')
        elif declare_as == 'debt' or line.get('is_invoice'):
            debt = line.get('total')
            have = 0.00
        else:
            debt = 0.00
            have = line.get('total')
        
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
        
        accounting_account = f"{line.get('accounting_concept')}{'0' * (12 - len(line.get('accounting_concept')) - len(line.get('accounting_pricing')))}{line.get('accounting_pricing')}"
        accounting_account_len = 12 - len(accounting_account)
        line_content += repeat_to_at_least_length(' ', accounting_account_len)
        line_content += accounting_account
        
        line_content += '01'
        
        line_content += repeat_to_at_least_length(' ', 6-len_doc_number)
        line_content += str(doc_number)
        
        if len(line_content) != 116:
            # print(line_content)
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
        line_content += ' 0'*3
        
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
                separate_by_type = item.get('separate_by_type', True)
                separate_by_origin = bool(item.get('separate_by_origin', False))
                if category != 'invoice' or not group_values:
                    separate_by_origin = False
                
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
                payment_origin, separate_by_payment_origin = _bank_payment_origin_flags(
                    category,
                    group_values,
                    payment_type_ids,
                    item.get('payment_origin'),
                    item.get('separate_by_payment_origin', False),
                )
                
                undeclare_previous = item.get('undeclare_previous', False)
                invoice_category = item.get('invoice_category', None)
                token_return = _optional_text(item.get('token_return')) or None
                declared_as = _optional_text(item.get('declared_as')) or None
                origin_ids = item.get('origins', [])
                contract_type_ids = item.get('contract_types', [])

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
                            payment_origin=payment_origin,
                            )
                        
                    except Exception as e:
                        pass
                    if existing_pricing_accounting:
                        accounting_pricing_saved = existing_pricing_accounting
                        if token_return:
                            accounting_pricing_saved.token_return = token_return
                        if declared_as:
                            accounting_pricing_saved.declared_as = declared_as
                        accounting_pricing_saved.separate_by_origin = separate_by_origin
                        product_ids = _merge_related_ids(product_ids, accounting_pricing_saved.products)
                        price_rate_ids = _merge_related_ids(price_rate_ids, accounting_pricing_saved.price_rates)
                        line_item_type_ids = _merge_related_ids(line_item_type_ids, accounting_pricing_saved.line_item_types)
                        price_interval_ids = _merge_related_ids(price_interval_ids, accounting_pricing_saved.price_intervals)
                        price_variable_interval_ids = _merge_related_ids(price_variable_interval_ids, accounting_pricing_saved.price_variables)
                        payment_type_ids = _merge_related_ids(payment_type_ids, accounting_pricing_saved.payment_types)
                        payment_origin, separate_by_payment_origin = _bank_payment_origin_flags(
                            category,
                            group_values,
                            payment_type_ids,
                            payment_origin,
                            separate_by_payment_origin,
                        )
                        accounting_pricing_saved.payment_origin = payment_origin
                        accounting_pricing_saved.separate_by_payment_origin = separate_by_payment_origin
                        bank_ids = _merge_related_ids(bank_ids, accounting_pricing_saved.banks)
                        origin_ids = _merge_related_ids(origin_ids, accounting_pricing_saved.origins)
                        contract_type_ids = _merge_related_ids(contract_type_ids, accounting_pricing_saved.contract_types)
                    else:
                        accounting_pricing_saved = AccountingPricing.objects.create(
                            token=token,
                            token_return=token_return,
                            name=name,
                            declared_as=declared_as,
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
                            grouped_lines=group_values,
                            separate_by_type=separate_by_type,
                            separate_by_origin=separate_by_origin,
                            payment_origin=payment_origin,
                            separate_by_payment_origin=separate_by_payment_origin,
                        )
                else:
                    accounting_pricing_saved = AccountingPricing.objects.get(id=id)
                    accounting_pricing_saved.token = token
                    accounting_pricing_saved.token_return = token_return
                    accounting_pricing_saved.name = name
                    accounting_pricing_saved.declared_as = declared_as
                    accounting_pricing_saved.accounting_concept = accounting_concept
                    accounting_pricing_saved.company = company
                    accounting_pricing_saved.exploitation = exploitation
                    accounting_pricing_saved.is_default = is_default
                    accounting_pricing_saved.is_active = is_active
                    accounting_pricing_saved.last_updated_by = user
                    accounting_pricing_saved.accounting_cost_center = cost_center
                    accounting_pricing_saved.undeclare_previous = undeclare_previous
                    accounting_pricing_saved.invoice_category = invoice_category
                    accounting_pricing_saved.outgoing_payments = outgoing_payments
                    accounting_pricing_saved.incoming_payments = incoming_payments
                    accounting_pricing_saved.national_iban = national_iban
                    accounting_pricing_saved.foreign_iban = foreign_iban
                    accounting_pricing_saved.grouped_lines = group_values
                    accounting_pricing_saved.separate_by_type = separate_by_type
                    accounting_pricing_saved.separate_by_origin = separate_by_origin
                    accounting_pricing_saved.payment_origin = payment_origin
                    accounting_pricing_saved.separate_by_payment_origin = separate_by_payment_origin
                    
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
                    accounting_pricing_saved.contract_types.set(ContractUseType.objects.filter(id__in=contract_type_ids).distinct())
                accounting_pricing_saved.save()
    except Exception as e:
        raise Exception(f"Couldn't bulk save accounting pricing: {e}") from e
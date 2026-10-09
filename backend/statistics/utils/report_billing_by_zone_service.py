"""Informe d'execució de padrons d'aigua per zona de tarificació (placement).

Agrupa les línies de factura per:
  - padró (Billing)
  - zona (SupplyPoint.placement / SupplyPointPlacement)
  - concepte d'aigua (quota de servei, consum per tram, clavegueram)
  - cànon ACA per tarifa (CANON-DOM, CANON-MUN, CANON-HOTELS, CANON-IND)
    i els seus trams, amb les mateixes columnes (factures, m³, euros)
"""
import datetime
import re
import traceback
from collections import defaultdict

import openpyxl
from django.db.models import Count
from django.utils.translation import gettext as _
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from rest_framework import status
from rest_framework.response import Response

from billing.models import Invoice, InvoiceLineItem
from contract.models import Contract
from coredata.models import ConfigProject
from statistics.utils.report_filters import (
    get_billing_ids,
    get_multi_ids,
    has_serie_final_range,
    invoice_multi_filter_q,
    serie_final_range_invoices,
    serie_final_range_period,
)
from statistics.views.reports_views import (
    add_row,
    adjust_column_widths,
    filter_pending_invoices,
    save_report,
)

# "CONSUM - 1R TRAM", "PART VARIABLE - 4T TRAM", "Aigua Potable Bloc 2"
_TRAM_RE = re.compile(
    r'(?:'
    r'(?:tram|bloc|bloque)\s*(\d+)'
    r'|(\d+)\s*[rntée]?\s*tram'
    r')',
    re.IGNORECASE,
)

CANON_TYPE_TOKENS = ('CANON-DOM', 'CANON-MUN', 'CANON-HOTELS', 'CANON-IND')
WATER_TRAMS = (1, 2, 3, 4)


def parse_date(date_str, make_aware=False):
    if not date_str:
        return None
    from django.utils import timezone

    for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d'):
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            if make_aware and timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt
        except ValueError:
            continue
    return None


def _tram_from_name(name):
    if not name:
        return None
    match = _TRAM_RE.search(name)
    if not match:
        return None
    return int(next(g for g in match.groups() if g))


def _signed_tax(base, tax):
    base = float(base or 0)
    tax = float(tax or 0)
    if base < 0 and tax > 0:
        tax = -tax
    elif base > 0 and tax < 0:
        tax = -tax
    return base, tax


def _is_canon(product_token, product_name):
    token = (product_token or '').upper()
    name = (product_name or '').upper()
    if token in ('1002', 'ACA') or token.startswith('ACA'):
        return True
    if 'ACA' in token:
        return True
    return 'CÀNON' in name or 'CANON' in name or 'CÁNON' in name


def _is_excluded_product(product_token, product_name):
    token = (product_token or '').upper()
    name = (product_name or '').upper()
    if token in ('1003',) or 'CONSERVACI' in name:
        return True
    if token.startswith('ESCO') or 'ESCOMESA' in name:
        return True
    if token == 'REC' or token.startswith('REG') or token.startswith('RIEG'):
        return True
    if ('RIEGO' in name or 'IRRIG' in name) and 'REGISTRE' not in name:
        return True
    return False


def _is_sewer(product_token, product_name):
    token = (product_token or '').upper()
    name = (product_name or '').upper()
    return token == 'CLV' or 'CLAVEGUERAM' in name or 'ALCANTARILLADO' in name


def _is_water(product_token, product_name, origin_token):
    if _is_sewer(product_token, product_name) or _is_canon(product_token, product_name):
        return False
    if _is_excluded_product(product_token, product_name):
        return False
    token = (product_token or '').upper()
    name = (product_name or '').upper()
    origin = (origin_token or '').lower()
    if origin == 'aigua':
        return True
    if token in ('1000', '1001'):
        return True
    return 'AIGUA' in name or 'AGUA' in name


def _canon_type_from_rate(price_rate, price_rate_name=None):
    """CANON-DOM / CANON-MUN / CANON-HOTELS / CANON-IND a partir del PriceRate."""
    token = ((price_rate.token if price_rate else None) or '').upper()
    if token in CANON_TYPE_TOKENS:
        return token
    blob = ' '.join(filter(None, [
        token,
        price_rate_name,
        price_rate.name if price_rate else None,
    ])).upper()
    if 'HOTEL' in blob or 'CAMPING' in blob:
        return 'CANON-HOTELS'
    if 'MUN' in blob:
        return 'CANON-MUN'
    if 'IND' in blob:
        return 'CANON-IND'
    if 'DOM' in blob:
        return 'CANON-DOM'
    return 'CANON-ALTRES'


def _is_quota_name(product_name, line_name, type_name):
    blob = ' '.join(filter(None, [product_name, line_name, type_name])).upper()
    return any(word in blob for word in (
        'QUOTA DE SERVEI', 'CUOTA DE SERVICIO', 'CUOTA AGUA', 'QUOTA AGUA',
        'QUOTA SERVEI', 'CUOTA SERVICIO',
    )) or (
        ('QUOTA' in blob or 'CUOTA' in blob or 'FIXA' in blob or 'FIJA' in blob)
        and 'TRAM' not in blob and 'BLOC' not in blob and 'CONSUM' not in blob
    )


def _classify_trams(product_name, line_name, type_name, interval, interval_units, variable_units):
    has_m3 = interval_units == 'm3' or variable_units == 'm3'
    tram = interval if interval and interval > 0 else _tram_from_name(line_name) or _tram_from_name(type_name)
    blob = ' '.join(filter(None, [line_name, type_name])).upper()
    looks_like_consum = (
        any(word in blob for word in ('CONSUM', 'TRAM', 'BLOC', 'BLOQUE', 'VARIABLE'))
        and 'SENSE CONSUM' not in blob
        and 'SIN CONSUMO' not in blob
    )
    if tram or has_m3 or looks_like_consum:
        return 'tram', tram
    if _is_quota_name(product_name, line_name, type_name):
        return 'quota', None
    if not has_m3:
        return 'quota', None
    return 'tram', tram


def classify_line(product_token, product_name, origin_token, line_name, type_name,
                  interval, interval_units, variable_units):
    """Retorna ('quota'|'tram'|'sewer'|'canon'|'canon_quota'|'other', tram_number|None)."""
    if _is_sewer(product_token, product_name):
        return 'sewer', None
    if _is_canon(product_token, product_name):
        kind, tram = _classify_trams(
            product_name, line_name, type_name, interval, interval_units, variable_units,
        )
        return ('canon_quota', None) if kind == 'quota' else ('canon', tram)
    if _is_excluded_product(product_token, product_name):
        return 'other', None
    if not _is_water(product_token, product_name, origin_token):
        return 'other', None
    return _classify_trams(
        product_name, line_name, type_name, interval, interval_units, variable_units,
    )


def _empty_concept():
    return {
        'invoice_ids': set(),
        'm3': 0.0,
        'base': 0.0,
        'tax': 0.0,
        'price_unit_sum': 0.0,
        'price_unit_weight': 0.0,
    }


def _empty_canon():
    return {
        'quota': _empty_concept(),
        'trams': defaultdict(_empty_concept),
        'invoice_ids': set(),
    }


def _empty_zone():
    return {
        'quota': _empty_concept(),
        'trams': defaultdict(_empty_concept),
        'tram_limits': {},
        'tram_labels': {},
        'sewer': _empty_concept(),
        'water_other': _empty_concept(),
        'canon': defaultdict(_empty_canon),
        'invoice_ids': set(),
        'consumption': 0.0,
    }


def _add_concept(bucket, invoice_id, units, base, tax, price_unit):
    if invoice_id is not None and (units or base):
        bucket['invoice_ids'].add(invoice_id)
    bucket['m3'] += float(units or 0)
    bucket['base'] += base
    bucket['tax'] += tax
    if price_unit is not None and units:
        bucket['price_unit_sum'] += float(price_unit) * float(units)
        bucket['price_unit_weight'] += float(units)


def _avg_price(bucket):
    if bucket['price_unit_weight']:
        return bucket['price_unit_sum'] / bucket['price_unit_weight']
    if bucket['m3']:
        return bucket['base'] / bucket['m3']
    return None


def _avg_quota_price(bucket):
    n = len(bucket['invoice_ids'])
    if n:
        return bucket['base'] / n
    return None


def _period_from_payload(data):
    """Període dels filtres d'Informes: `date_range` o `start_date`/`end_date`."""
    date_range = data.get('date_range')
    start_date = None
    end_date = None
    if date_range:
        if isinstance(date_range, (list, tuple)):
            start_date = parse_date(date_range[0] if date_range else None)
            end_date = parse_date(date_range[1] if len(date_range) > 1 else None)
        else:
            start_date = parse_date(date_range)
    if not start_date:
        start_date = parse_date(data.get('start_date'))
    if not end_date:
        end_date = parse_date(data.get('end_date'))
    return start_date, end_date


def resolve_invoices(request):
    """Aplica els mateixos filtres que el formulari genèric d'Informes."""
    billing_ids = get_billing_ids(request.data)
    exploitation_id = request.data.get('exploitation_id')
    start_date, end_date = _period_from_payload(request.data)
    used_period = bool(start_date and end_date)

    if billing_ids:
        invoices = Invoice.objects.filter(billing_id__in=billing_ids, is_active=True)
    elif request.data.get('date_range') or request.data.get('start_date') or request.data.get('end_date'):
        if not used_period:
            return None, None, None, None, Response(
                {"error": "date_range invàlid."}, status=status.HTTP_400_BAD_REQUEST
            )
        invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
        invoices = Invoice.objects.filter(
            issue_date__range=(start_date.date(), end_date.date()),
            type_final=invoice_type,
            is_active=True,
        ).distinct()
    elif has_serie_final_range(request.data):
        invoices = filter_pending_invoices(serie_final_range_invoices(), request)
        start_date, end_date = serie_final_range_period(invoices)
        if start_date is None:
            return None, None, None, None, Response(
                {"error": "el rang de sèrie no té factures."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invoices = invoices.filter(is_active=True)
    else:
        return None, None, None, None, Response(
            {"error": "cal billing_ids, date_range o rang de sèrie."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if billing_ids or used_period:
        invoices = filter_pending_invoices(invoices, request)

    multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
    if multi_q:
        invoices = invoices.filter(multi_q).distinct()

    if exploitation_id and str(exploitation_id) not in ('all', '', 'None'):
        invoices = invoices.filter(exploitation_id=exploitation_id)

    return invoices, billing_ids, start_date, end_date, None


def _invoice_column_meta(invoice):
    """Classifica la factura en columna: padró / personalitzada / refacturació / abonament.

    - Abonament: classe OR (sèrie FR) o import negatiu / títol d'abonament.
    - Refacturació: té refactored_token (sèrie FF confirmada).
    - Personalitzada: sense billing (fora de padró), original.
    - Padró: resta de factures amb billing_id.
    """
    class_token = ''
    if getattr(invoice, 'invoice_class_id', None) and invoice.invoice_class:
        class_token = (invoice.invoice_class.token or '')
    elif getattr(invoice, 'invoice_class_token_final', None):
        class_token = invoice.invoice_class_token_final or ''
    class_token = class_token.upper()
    title = (invoice.title_final or '').upper()
    subtotal = invoice.subtotal_final

    is_abono = (
        class_token == 'OR'
        or (subtotal is not None and subtotal < 0)
        or 'ABONAMENT' in title
        or title.startswith('ABONO ')
        or title == 'ABONO'
    )
    if is_abono:
        return {
            'id': 'abonament',
            'kind': 'abonament',
            'name': _("Abonaments"),
            'created_at': None,
            'sort': (2, 0, 0),
            'serie_finals': set(),
        }
    if invoice.refactored_token:
        return {
            'id': 'refacturacio',
            'kind': 'refacturacio',
            'name': _("Refacturacions"),
            'created_at': None,
            'sort': (1, 0, 0),
            'serie_finals': set(),
        }
    if not invoice.billing_id:
        return {
            'id': 'personalitzada',
            'kind': 'personalitzada',
            'name': _("Factures personalitzades"),
            'created_at': None,
            'sort': (0, 0, 0),
            'serie_finals': set(),
        }
    billing = invoice.billing
    created = billing.created_at if billing else None
    return {
        'id': billing.id if billing else 0,
        'kind': 'billing',
        'name': (billing.name if billing else None) or _("Sense padró"),
        'created_at': created,
        'sort': (-1, created.timestamp() if created else 0, billing.id if billing else 0),
        'serie_finals': set(),
    }


def aggregate_by_zone(invoices, task=None):
    """Retorna (columns, zones, data[(column_id, zone)] -> bucket, others).

    Les columnes són padrones normals més, si n'hi ha:
    Factures personalitzades, Refacturacions i Abonaments.
    """
    line_items = InvoiceLineItem.objects.filter(invoice__in=invoices).select_related(
        'invoice__billing',
        'invoice__invoice_class',
        'invoice__contract',
        'invoice__contract__supply_point_default__placement',
        'reading__supply_point__placement',
        'product__origin',
        'price_rate',
        'line_item_type__price_interval',
        'line_item_type__price_variable',
    )

    padrones = {}
    zones = {}
    data = defaultdict(_empty_zone)
    others = defaultdict(_empty_concept)
    invoice_rows = {}

    total = line_items.count()
    for index, line in enumerate(line_items.iterator(chunk_size=2000), start=1):
        if task and index % 200 == 0:
            task.update_state(
                state='PROGRESS',
                meta={
                    'current': index,
                    'total': total,
                    'percent': round((index / total) * 100, 2) if total else 0.0,
                },
            )

        invoice = line.invoice
        if invoice is None:
            continue

        column = _invoice_column_meta(invoice)
        column_id = column['id']
        if column_id not in padrones:
            padrones[column_id] = column
        if invoice.serie_final:
            padrones[column_id]['serie_finals'].add(invoice.serie_final)

        placement = None
        if line.reading and line.reading.supply_point:
            placement = line.reading.supply_point.placement
        if placement is None and invoice.contract and invoice.contract.supply_point_default:
            placement = invoice.contract.supply_point_default.placement

        placement_id = placement.id if placement else 0
        placement_name = placement.name if placement else _("Sense zona")
        if placement_id not in zones:
            zones[placement_id] = {
                'id': placement_id,
                'name': placement_name,
                'position': placement.position if placement and placement.position is not None else 9999,
            }

        bucket = data[(column_id, placement_id)]
        if invoice.id not in bucket['invoice_ids']:
            bucket['invoice_ids'].add(invoice.id)
            bucket['consumption'] += float(invoice.consumption or 0)

        if invoice.id not in invoice_rows:
            class_name = None
            if invoice.invoice_class_id and invoice.invoice_class:
                class_name = invoice.invoice_class.name or invoice.invoice_class.token
            elif invoice.invoice_class_token_final:
                class_name = invoice.invoice_class_token_final
            invoice_rows[invoice.id] = {
                'id': invoice.id,
                'serie_final': invoice.serie_final,
                'origen': column['name'],
                'origen_kind': column['kind'],
                'billing_id': invoice.billing_id,
                'billing_name': invoice.billing.name if invoice.billing else None,
                'zone_id': placement_id or None,
                'zone_name': placement_name,
                'issue_date': invoice.issue_date,
                'contract_token': invoice.contract.token if invoice.contract else None,
                'customer': invoice.customer_final,
                'invoice_class': class_name,
                'consumption': float(invoice.consumption or 0),
                'subtotal': float(invoice.subtotal_final or 0),
                'total': float(invoice.total_final or 0),
            }

        base, tax = _signed_tax(line.price, line.tax_price)
        units = float(line.units or 0)
        kind, tram = classify_line(
            line.product.token if line.product else None,
            line.product_name or (line.product.name if line.product else None),
            line.product.origin.token if line.product and line.product.origin else None,
            line.name,
            line.line_item_type.name if line.line_item_type else None,
            line.interval,
            line.line_item_type.price_interval.units if line.line_item_type and line.line_item_type.price_interval else None,
            line.line_item_type.price_variable.units if line.line_item_type and line.line_item_type.price_variable else None,
        )

        if kind == 'quota':
            _add_concept(bucket['quota'], invoice.id, units, base, tax, line.price_unit)
        elif kind == 'tram':
            _add_concept(bucket['trams'][tram or 0], invoice.id, units, base, tax, line.price_unit)
        elif kind == 'sewer':
            _add_concept(bucket['sewer'], invoice.id, units, base, tax, line.price_unit)
        elif kind in ('canon', 'canon_quota'):
            canon_type = _canon_type_from_rate(line.price_rate, line.price_rate_name)
            canon_bucket = bucket['canon'][canon_type]
            canon_bucket['invoice_ids'].add(invoice.id)
            if kind == 'canon_quota':
                _add_concept(canon_bucket['quota'], invoice.id, units, base, tax, line.price_unit)
            else:
                _add_concept(canon_bucket['trams'][tram or 0], invoice.id, units, base, tax, line.price_unit)
        else:
            label = line.product_name or (line.product.name if line.product else _("Sense producte"))
            _add_concept(others[label], invoice.id, units, base, tax, line.price_unit)

    return padrones, zones, data, others, list(invoice_rows.values())


def configured_placements():
    """Totes les zones (SupplyPointPlacement) configurades al client."""
    from service.models import SupplyPointPlacement

    zones = {}
    for placement in SupplyPointPlacement.objects.all().order_by('position', 'id'):
        zones[placement.id] = {
            'id': placement.id,
            'name': placement.name or _("Zona {id}").format(id=placement.id),
            'position': placement.position if placement.position is not None else 9999,
        }
    return zones


def merge_all_zones(invoice_zones, meter_counts, catalog=None):
    """Uneix catàleg de zones, factures i comptadors: surt tot el que hi hagi."""
    zones = dict(catalog if catalog is not None else configured_placements())
    for zone_id, zone in (invoice_zones or {}).items():
        if zone_id not in zones:
            zones[zone_id] = zone
    for item in meter_counts or []:
        if item['id'] not in zones:
            zones[item['id']] = {
                'id': item['id'],
                'name': item['name'],
                'position': 9999,
            }
    return zones


def current_meters_by_zone():
    """Comptadors (punts de subministrament) de contractes actius per zona."""
    try:
        active_token = ConfigProject.objects.get(token='contract_active_token').value
        contracts = Contract.objects.filter(is_active=True, status__token=active_token)
    except Exception:
        contracts = Contract.objects.filter(is_active=True)

    rows = (
        contracts.filter(supply_point_default__isnull=False)
        .values(
            'supply_point_default__placement_id',
            'supply_point_default__placement__name',
            'supply_point_default__placement__position',
        )
        .annotate(comptadors=Count('supply_point_default_id', distinct=True))
        .order_by(
            'supply_point_default__placement__position',
            'supply_point_default__placement_id',
        )
    )
    result = []
    for row in rows:
        result.append({
            'id': row['supply_point_default__placement_id'] or 0,
            'name': row['supply_point_default__placement__name'] or _("Sense zona"),
            'comptadors': row['comptadors'],
        })
    return result


def _tram_row_label(tram, limits=None, labels=None, config=None):
    """Etiqueta estable per tram d'aigua. Els límits en m³ no es mostren."""
    if tram == 0:
        return _("Consum aigua (sense tram)")
    return _("CONSUM D'AIGUA - TRAM {n}").format(n=tram)


def _canon_tram_row_label(canon_type, tram):
    if tram == 0:
        return _("{canon} (sense tram)").format(canon=canon_type)
    return _("{canon} - TRAM {n}").format(canon=canon_type, n=tram)


def _report_trams(discovered):
    """Trams 1-4 sempre (amb 0 si no n'hi ha), més els extra que surtin a les factures."""
    numbered = sorted(set(WATER_TRAMS) | {t for t in discovered if t and t > 0})
    if 0 in discovered:
        return [0] + numbered
    return numbered


def _report_canon_types(data):
    discovered = set()
    for zone_data in data.values():
        discovered.update(zone_data['canon'].keys())
    types = list(CANON_TYPE_TOKENS)
    for token in sorted(discovered):
        if token not in types:
            types.append(token)
    return types


def _discovered_trams(data):
    found = set()
    for zone_data in data.values():
        found.update(zone_data['trams'].keys())
        for canon_bucket in zone_data['canon'].values():
            found.update(canon_bucket['trams'].keys())
    return sorted(found)


def _padron_column_label(padron):
    """Etiqueta de columna: nom del padró (Billing.name)."""
    return padron.get('name') or _("Sense padró")


def apply_zone_config(zones, meter_counts, config):
    if not config:
        return
    labels = config.get('zone_labels') or {}
    if not labels:
        return
    zone_list = zones.values() if isinstance(zones, dict) else zones
    for zone in zone_list:
        if zone['id'] in labels:
            zone['name'] = labels[zone['id']]
    for item in meter_counts or []:
        if item['id'] in labels:
            item['name'] = labels[item['id']]


def _fill(hex_color):
    return PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")


def _thin_border():
    side = Side(style='thin', color='BFBFBF')
    return Border(left=side, right=side, top=side, bottom=side)


def _write_cell(sheet, row, col, value, fill=None, font=None, fmt=None, align=None):
    cell = sheet.cell(row=row, column=col, value=value)
    cell.border = _thin_border()
    if fill:
        cell.fill = fill
    if font:
        cell.font = font
    if fmt:
        cell.number_format = fmt
    if align:
        cell.alignment = align
    return cell


def build_workbook(padrones, zones, data, others, meter_counts, black_fill, white_bold_font,
                   config=None, invoice_rows=None):
    wb = openpyxl.Workbook()

    ordered_padrones = sorted(
        padrones.values(),
        key=lambda p: p.get('sort') or (0, 0, p.get('id') or 0),
    )
    ordered_zones = sorted(zones.values(), key=lambda z: (z['position'], z['id']))
    apply_zone_config(ordered_zones, meter_counts, config)
    all_trams = _report_trams(_discovered_trams(data))
    canon_types = _report_canon_types(data)

    if not ordered_padrones:
        sheet = wb.active
        sheet.title = _("Execució padrons")
        sheet['A1'] = _("No s'han trobat factures per als filtres indicats.")
        _write_meters_sheet(
            wb.create_sheet(_("Comptadors actuals")),
            meter_counts, black_fill, white_bold_font,
        )
        return wb

    header_font = Font(color="FFFFFF", bold=True)
    bold = Font(bold=True)
    zone_fills = [
        _fill("5B9BD5"),
        _fill("C65911"),
        _fill("548235"),
        _fill("7030A0"),
        _fill("833C0C"),
    ]
    yellow = _fill("FFFF99")
    light = _fill("D6EAF8")
    orange = _fill("FCE4D6")
    grey = _fill("F2F2F2")
    total_fill = _fill("305496")
    canon_fill = _fill("7B8D9E")

    _write_execution_sheet(
        wb.active, ordered_padrones, ordered_zones, all_trams, canon_types, data,
        header_font, bold, zone_fills, canon_fill, yellow, light, orange, grey, total_fill,
        config=config,
    )
    _write_invoices_sheet(
        wb.create_sheet(_("Factures")),
        invoice_rows or [],
        black_fill, white_bold_font,
    )
    _write_meters_sheet(
        wb.create_sheet(_("Comptadors actuals")),
        meter_counts, black_fill, white_bold_font,
    )
    _write_others_sheet(
        wb.create_sheet(_("Altres conceptes")),
        others, black_fill, white_bold_font,
    )
    return wb


def _write_execution_sheet(sheet, padrones, zones, all_trams, canon_types, data,
                           header_font, bold, zone_fills, canon_fill, yellow, light, orange, grey, total_fill,
                           config=None):
    sheet.title = _("Execució padrons")
    n_padrones = len(padrones) or 1
    cols_per_padron = 3
    first_data_col = 2

    sheet.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    _write_cell(sheet, 1, 1, _("Concepte"), fill=total_fill, font=header_font)

    for i, padron in enumerate(padrones):
        col = first_data_col + i * cols_per_padron
        sheet.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + cols_per_padron - 1)
        _write_cell(sheet, 1, col, _padron_column_label(padron), fill=total_fill, font=header_font,
                    align=Alignment(horizontal='center'))
        for offset, label in enumerate((_("Núm. factures"), _("m³"), _("Euros (base)"))):
            _write_cell(sheet, 2, col + offset, label, fill=total_fill, font=header_font)

    totals_col = first_data_col + n_padrones * cols_per_padron
    sheet.merge_cells(start_row=1, start_column=totals_col, end_row=1, end_column=totals_col + cols_per_padron - 1)
    _write_cell(sheet, 1, totals_col, _("TOTALS"), fill=yellow, font=bold,
                align=Alignment(horizontal='center'))
    for offset, label in enumerate((_("Núm. factures"), _("m³"), _("Euros (base)"))):
        _write_cell(sheet, 2, totals_col + offset, label, fill=yellow, font=bold)

    row = 3
    last_col = totals_col + cols_per_padron - 1

    def write_concept_row(label, getter, fill, show_invoices=True, show_m3=True):
        nonlocal row
        _write_cell(sheet, row, 1, label, fill=fill, font=bold if not show_m3 or 'Total' in str(label) else None)
        tot_inv, tot_m3, tot_eur = set(), 0.0, 0.0
        for i, padron in enumerate(padrones):
            col = first_data_col + i * cols_per_padron
            inv, m3, eur = getter(padron['id'])
            tot_inv |= inv
            tot_m3 += m3
            tot_eur += eur
            _write_cell(sheet, row, col, len(inv) if show_invoices else None, fill=fill, fmt='#,##0')
            _write_cell(sheet, row, col + 1, round(m3, 3) if show_m3 else None, fill=fill, fmt='#,##0.000')
            _write_cell(sheet, row, col + 2, round(eur, 2), fill=fill, fmt='#,##0.00')
        _write_cell(sheet, row, totals_col, len(tot_inv) if show_invoices else None, fill=yellow, fmt='#,##0')
        _write_cell(sheet, row, totals_col + 1, round(tot_m3, 3) if show_m3 else None, fill=yellow, fmt='#,##0.000')
        _write_cell(sheet, row, totals_col + 2, round(tot_eur, 2), fill=yellow, fmt='#,##0.00')
        row += 1

    def write_banner(title, fill):
        nonlocal row
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
        for col in range(1, last_col + 1):
            _write_cell(sheet, row, col, title if col == 1 else None, fill=fill, font=header_font)
        row += 1

    def _from_bucket(bucket, field_path):
        if field_path[0] == 'tram':
            concept = bucket['trams'][field_path[1]]
        elif field_path[0] == 'water_total':
            return (
                set().union(*(bucket['trams'][t]['invoice_ids'] for t in all_trams)) if all_trams else set(),
                sum(bucket['trams'][t]['m3'] for t in all_trams),
                sum(bucket['trams'][t]['base'] for t in all_trams),
            )
        elif field_path[0] == 'consumption':
            return bucket['invoice_ids'], bucket['consumption'], 0.0
        elif field_path[0] == 'canon_quota':
            concept = bucket['canon'][field_path[1]]['quota']
        elif field_path[0] == 'canon_tram':
            concept = bucket['canon'][field_path[1]]['trams'][field_path[2]]
        elif field_path[0] == 'canon_total':
            canon_bucket = bucket['canon'][field_path[1]]
            inv = set(canon_bucket['quota']['invoice_ids'])
            m3 = canon_bucket['quota']['m3']
            eur = canon_bucket['quota']['base']
            for tram in all_trams:
                t = canon_bucket['trams'][tram]
                inv |= t['invoice_ids']
                m3 += t['m3']
                eur += t['base']
            return inv, m3, eur
        elif field_path[0] == 'canon_all_total':
            inv, m3, eur = set(), 0.0, 0.0
            for canon_type in canon_types:
                i, m, e = _from_bucket(bucket, ('canon_total', canon_type))
                inv |= i
                m3 += m
                eur += e
            return inv, m3, eur
        else:
            concept = bucket[field_path[0]]
        return concept['invoice_ids'], concept['m3'], concept['base']

    def _get(billing_id, zone_id, field_path):
        return _from_bucket(data[(billing_id, zone_id)], field_path)

    def write_water_block(getter):
        write_concept_row(
            (config or {}).get('quota_label') or _("Quota servei"),
            lambda bid: getter(bid, ('quota',)),
            orange,
            show_m3=False,
        )
        for tram in all_trams:
            write_concept_row(
                _tram_row_label(tram),
                lambda bid, t=tram: getter(bid, ('tram', t)),
                light,
            )
        write_concept_row(
            (config or {}).get('water_total_label') or _("Total consum d'aigua"),
            lambda bid: getter(bid, ('water_total',)),
            grey,
        )
        write_concept_row(
            (config or {}).get('sewer_label') or _("Taxa clavegueram"),
            lambda bid: getter(bid, ('sewer',)),
            orange,
        )
        write_concept_row(
            _("Consum factura"),
            lambda bid: getter(bid, ('consumption',)),
            grey,
            show_invoices=True,
        )

    def write_canon_block(getter, canon_type):
        write_concept_row(
            _("{canon} - PART FIXA").format(canon=canon_type),
            lambda bid, ct=canon_type: getter(bid, ('canon_quota', ct)),
            orange,
            show_m3=False,
        )
        for tram in all_trams:
            write_concept_row(
                _canon_tram_row_label(canon_type, tram),
                lambda bid, ct=canon_type, t=tram: getter(bid, ('canon_tram', ct, t)),
                light,
            )
        write_concept_row(
            _("{canon} - TOTAL").format(canon=canon_type),
            lambda bid, ct=canon_type: getter(bid, ('canon_total', ct)),
            grey,
        )

    z_index = 0
    for zone in zones:
        n_invoices = set()
        for padron in padrones:
            n_invoices |= data[(padron['id'], zone['id'])]['invoice_ids']
        # Només zones amb factures a la pestanya d'execució (com al model d'ordenança).
        if not n_invoices:
            continue
        zone_fill = zone_fills[z_index % len(zone_fills)]
        z_index += 1
        title = zone['name'] or _("Sense zona")
        write_banner(_("{title}  —  {n} factures").format(title=title, n=len(n_invoices)), zone_fill)

        write_water_block(lambda bid, path, zid=zone['id']: _get(bid, zid, path))

        write_banner(_("Cànon ACA"), canon_fill)
        for canon_type in canon_types:
            n_canon = set()
            for padron in padrones:
                n_canon |= data[(padron['id'], zone['id'])]['canon'][canon_type]['invoice_ids']
            write_banner(
                _("{canon}  —  {n} factures").format(canon=canon_type, n=len(n_canon)),
                canon_fill,
            )
            write_canon_block(
                lambda bid, path, zid=zone['id']: _get(bid, zid, path),
                canon_type,
            )

        write_concept_row(
            _("TOTAL CÀNON ZONA"),
            lambda bid, zid=zone['id']: _get(bid, zid, ('canon_all_total',)),
            yellow,
        )
        row += 1

    write_banner(_("TOTALS TOTES LES ZONES"), total_fill)

    def _sum_all(billing_id, field_path):
        inv, m3, eur = set(), 0.0, 0.0
        for zone in zones:
            i, m, e = _get(billing_id, zone['id'], field_path)
            inv |= i
            m3 += m
            eur += e
        return inv, m3, eur

    write_concept_row(
        _("TOTAL QUOTA SERVEI"),
        lambda bid: _sum_all(bid, ('quota',)),
        yellow,
        show_m3=False,
    )
    write_concept_row(
        _("TOTAL CONSUM AIGUA"),
        lambda bid: _sum_all(bid, ('water_total',)),
        yellow,
    )
    write_concept_row(
        _("TOTAL CLAVEGUERAM"),
        lambda bid: _sum_all(bid, ('sewer',)),
        yellow,
    )
    write_concept_row(
        _("TOTAL CÀNON ACA"),
        lambda bid: _sum_all(bid, ('canon_all_total',)),
        yellow,
    )

    sheet.column_dimensions['A'].width = 55
    for col in range(2, last_col + 1):
        sheet.column_dimensions[get_column_letter(col)].width = 16
    sheet.freeze_panes = 'B3'
    sheet.sheet_view.showGridLines = True


def _write_invoices_sheet(sheet, invoice_rows, black_fill, white_bold_font):
    """Llista les factures que han participat a la pestanya d'execució."""
    titles = [
        _("Sèrie final"), _("Origen"), _("Padró / facturació"), _("Zona"),
        _("Data emissió"), _("Contracte"), _("Client"), _("Classe"),
        _("Consum m³"), _("Base €"), _("Total €"),
    ]
    row = add_row(sheet, 0, titles, fill=black_fill, font=white_bold_font)

    ordered = sorted(
        invoice_rows,
        key=lambda r: (
            r.get('origen') or '',
            r.get('billing_name') or '',
            r.get('serie_final') or '',
            r.get('id') or 0,
        ),
    )
    if not ordered:
        add_row(sheet, row, [_("Cap factura als filtres indicats."), "", "", "", "", "", "", "", "", "", ""])
        adjust_column_widths(sheet)
        return

    for item in ordered:
        issue = item.get('issue_date')
        if hasattr(issue, 'isoformat'):
            issue = issue.isoformat()
        row = add_row(sheet, row, [
            item.get('serie_final'),
            item.get('origen'),
            item.get('billing_name') or "",
            item.get('zone_name'),
            issue,
            item.get('contract_token'),
            item.get('customer'),
            item.get('invoice_class'),
            round(float(item.get('consumption') or 0), 3),
            round(float(item.get('subtotal') or 0), 2),
            round(float(item.get('total') or 0), 2),
        ])
    adjust_column_widths(sheet)
    for col in (9, 10, 11):
        for excel_row in sheet.iter_rows(min_row=2, min_col=col, max_col=col):
            for cell in excel_row:
                if isinstance(cell.value, float):
                    cell.number_format = '#,##0.000' if col == 9 else '#,##0.00'


def _write_meters_sheet(sheet, meter_counts, black_fill, white_bold_font):
    row = add_row(sheet, 0, [
        _("Zona"), _("Núm. comptadors (contractes actius)"),
    ], fill=black_fill, font=white_bold_font)
    total = 0
    for item in meter_counts:
        row = add_row(sheet, row, [item['name'], item['comptadors']])
        total += item['comptadors']
    add_row(sheet, row, [_("TOTAL"), total], fill=black_fill, font=white_bold_font)
    adjust_column_widths(sheet)


def _write_others_sheet(sheet, others, black_fill, white_bold_font):
    row = add_row(sheet, 0, [
        _("Producte"), _("Núm. línies/factures"), _("Unitats"), _("Base €"), _("IVA €"), _("Total €"),
    ], fill=black_fill, font=white_bold_font)
    if not others:
        add_row(sheet, row, [_("Cap concepte exclòs (conservació, escomeses, rec, etc.)"), "", "", "", "", ""])
        adjust_column_widths(sheet)
        return
    for name, bucket in sorted(others.items(), key=lambda kv: kv[0] or ''):
        row = add_row(sheet, row, [
            name,
            len(bucket['invoice_ids']),
            round(bucket['m3'], 3),
            round(bucket['base'], 2),
            round(bucket['tax'], 2),
            round(bucket['base'] + bucket['tax'], 2),
        ])
    adjust_column_widths(sheet)


def format_terminal_summary(padrones, zones, data, config=None):
    lines = []
    ordered_padrones = sorted(
        padrones.values(),
        key=lambda p: p.get('sort') or (0, 0, p.get('id') or 0),
    )
    ordered_zones = sorted(zones.values(), key=lambda z: (z['position'], z['id']))
    apply_zone_config(ordered_zones, [], config)
    all_trams = _report_trams(_discovered_trams(data))
    canon_types = _report_canon_types(data)
    for padron in ordered_padrones:
        lines.append(f"\n=== {_padron_column_label(padron)} (id={padron['id']}) ===")
        for zone in ordered_zones:
            bucket = data[(padron['id'], zone['id'])]
            if not bucket['invoice_ids']:
                continue
            lines.append(
                f"  {zone['name']}  —  {len(bucket['invoice_ids'])} factures"
            )
            quota = bucket['quota']
            avg = _avg_quota_price(quota)
            avg_txt = f"  preu mitjà {avg:.4f} €" if avg is not None else ""
            lines.append(
                f"    Quota servei          {quota['base']:>12.2f} €  "
                f"({len(quota['invoice_ids'])} fact.){avg_txt}"
            )
            for tram in all_trams:
                t = bucket['trams'][tram]
                if not t['m3'] and not t['base']:
                    continue
                price = _avg_price(t)
                price_txt = f"  @ {price:.4f} €/m³" if price is not None else ""
                label = _tram_row_label(tram)
                lines.append(
                    f"    {label:<22} {t['m3']:>10.3f} m³  {t['base']:>12.2f} €{price_txt}"
                )
            water_m3 = sum(bucket['trams'][t]['m3'] for t in all_trams)
            water_eur = sum(bucket['trams'][t]['base'] for t in all_trams)
            lines.append(
                f"    Total consum aigua    {water_m3:>10.3f} m³  {water_eur:>12.2f} €"
            )
            sewer = bucket['sewer']
            lines.append(
                f"    Clavegueram           {sewer['m3']:>10.3f} m³  {sewer['base']:>12.2f} €"
            )
            for canon_type in canon_types:
                canon_bucket = bucket['canon'][canon_type]
                if not canon_bucket['invoice_ids']:
                    continue
                lines.append(f"    {canon_type}")
                for tram in all_trams:
                    t = canon_bucket['trams'][tram]
                    if not t['m3'] and not t['base']:
                        continue
                    lines.append(
                        f"      {_canon_tram_row_label(canon_type, tram):<22} "
                        f"{t['m3']:>10.3f} m³  {t['base']:>12.2f} €"
                    )
    return "\n".join(lines)


def generate_billing_by_zone_report(request, black_fill=None, white_bold_font=None, task=None, config=None):
    try:
        invoices, billing_ids, start_date, end_date, error = resolve_invoices(request)
        if error:
            return error, None, None

        name = request.data.get('name') or (
            (config or {}).get('report_name') or _("Execució padrons per zona de tarificació")
        )
        type_id = request.data.get('type_id') or request.data.get('report_type_id')
        if not type_id:
            from statistics.models import ReportType
            billing_section = ReportType.objects.filter(token='billing').first()
            type_id = billing_section.id if billing_section else None

        padrones, zones, data, others, invoice_rows = aggregate_by_zone(invoices, task=task)
        meter_counts = current_meters_by_zone()
        zones = merge_all_zones(zones, meter_counts)
        apply_zone_config(zones, meter_counts, config)
        wb = build_workbook(
            padrones, zones, data, others, meter_counts,
            black_fill, white_bold_font, config=config, invoice_rows=invoice_rows,
        )

        filename = f"execucio_padrons_per_zona_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        document_id = save_report(
            content=wb, filename=filename, name=name, type_id=type_id,
            start_date=start_date, end_date=end_date,
        )
        return None, document_id, filename
    except Exception as exc:
        print(f"Error in generate_billing_by_zone_report: {exc}")
        traceback.print_exc()
        return Response(
            {"error": f"Ha ocorregut un error inesperat: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ), None, None

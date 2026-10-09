"""
Export CSV amb la mateixa lògica que docs/sql/vw_contract_invoice_reading_summary.sql
(sense usar la vista a la BD): contractes actius, última factura F, cadena de lectures.
"""
import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO

from django.utils.translation import gettext as _

from billing.models import Invoice, Reading
from contract.models import Contract
from coredata.models import ConfigProject


def _active_contract_status_token():
    return ConfigProject.objects.get(token='contract_active_token').value


def _invoice_base_qs():
    """Factures definitives actives, no suprimides, no esborrany (status_id != 1)."""
    return (
        Invoice.objects.filter(
            contract_id__isnull=False,
            is_active=True,
            is_suppressed=False,
            type_final='F',
        )
        .exclude(status_id=1)
        .order_by('contract_id', '-issue_date', '-id')
    )


def _reading_base_qs():
    return (
        Reading.objects.filter(
            contract_id__isnull=False,
            is_active=True,
            is_control=False,
        ).order_by('contract_id', '-reading_date', '-id')
    )


def _last_per_contract_id_ordered(qs, contract_field='contract_id'):
    """
    Una fila per contract_id (primera de cada grup després d'order_by contract, -date, -id).
    Equivalent a DISTINCT ON (contract_id) ... ORDER BY contract_id, date DESC, id DESC.
    """
    out = {}
    for row in qs.iterator(chunk_size=2000):
        cid = getattr(row, contract_field)
        if cid is not None and cid not in out:
            out[cid] = row
    return out


def _safe_previous_non_control(reading, readings_by_id):
    """Replica JOIN ... ON id = previous_reading_id AND is_control = false."""
    if not reading or not reading.previous_reading_id:
        return None
    pr = readings_by_id.get(reading.previous_reading_id)
    if not pr or pr.is_control:
        return None
    return pr


def _bulk_readings_for_chains(last_by_contract):
    """Carrega last readings + fins a 4 nivells de previous_reading_id."""
    by_id = {}
    pending = set()
    for lr in last_by_contract.values():
        if not lr:
            continue
        by_id[lr.id] = lr
        if lr.previous_reading_id and lr.previous_reading_id not in by_id:
            pending.add(lr.previous_reading_id)
    depth = 0
    while pending and depth < 6:
        chunk = Reading.objects.filter(id__in=pending)
        pending = set()
        for r in chunk:
            by_id[r.id] = r
            if r.previous_reading_id and r.previous_reading_id not in by_id:
                pending.add(r.previous_reading_id)
        depth += 1
    return by_id


def _fmt_date(d):
    if d is None:
        return ''
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.strftime('%d/%m/%Y')
    return str(d)


def _fmt_decimal(v):
    if v is None:
        return ''
    if isinstance(v, Decimal):
        return str(v).replace('.', ',')
    return str(v).replace('.', ',')


def _holder_name(person):
    if not person:
        return ''
    return f"{person.name or ''} {person.surname or ''}".strip()


def _invoice_code(inv):
    if not inv:
        return ''
    return (inv.title_final or inv.number or inv.token or '').strip()


def invoice_reading_summary_csv_headers():
    return [
        _('ID contracte'),
        _('Token contracte'),
        _('Data creació contracte'),
        _('NoFacturable'),
        _('ID titular'),
        _('Token titular'),
        _('Nom titular'),
        _('ID tipus ús'),
        _('Token tipus ús'),
        _('Nom tipus ús'),
        _('ID tipus client'),
        _('Token tipus client'),
        _('Nom tipus client'),
        _('ID categoria'),
        _('Token categoria'),
        _('Nom categoria'),
        _('ID explotació'),
        _('Token explotació'),
        _('Nom explotació'),
        _('ID zona ruta'),
        _('Token zona ruta'),
        _('Nom zona ruta'),
        _('ID ruta'),
        _('Token ruta'),
        _('Nom ruta'),
        _('Route'),
        _('RoutePosition'),
        _('ID comptador'),
        _('Comptador'),
        _('ComptadorGeneral'),
        _('ComptadorPare'),
        _('ID última factura'),
        _('Codi última factura'),
        _('Data última factura'),
        _('ID última lectura'),
        _('Data última lectura'),
        _('Valor última lectura'),
        _('ID lectura anterior (FK)'),
        _('Data lectura anterior'),
        _('Valor lectura anterior'),
        _('ID lectura anterior² (FK)'),
        _('Data lectura anterior²'),
        _('Valor lectura anterior²'),
        _('ID lectura anterior³ (FK)'),
        _('Data lectura anterior³'),
        _('Valor lectura anterior³'),
    ]


def build_invoice_reading_summary_csv_bytes():
    active_token = _active_contract_status_token()

    contracts_qs = (
        Contract.objects.filter(is_active=True, status__token=active_token)
        .select_related(
            'holder',
            'use_type',
            'client_type',
            'category',
            'supply_point_default__connection__exploitation',
            'supply_point_default__property__route_position__route__route_zone',
            'supply_point_default__meter__meter_general',
        )
        .order_by('id')
    )

    inv_map = _last_per_contract_id_ordered(_invoice_base_qs())
    last_read_map = _last_per_contract_id_ordered(_reading_base_qs())
    readings_by_id = _bulk_readings_for_chains(last_read_map)

    buffer = StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(invoice_reading_summary_csv_headers())

    for c in contracts_qs.iterator(chunk_size=500):
        sp = c.supply_point_default
        prop = sp.property if sp else None
        rp = prop.route_position if prop else None
        route = rp.route if rp else None
        rz = route.route_zone if route else None
        conn = sp.connection if sp else None
        expl = conn.exploitation if conn else None
        meter = sp.meter if sp else None

        route_label = ''
        if route:
            route_label = (route.token or route.name or str(route.id)).strip()
        if rp and rp.position is not None:
            route_position_label = str(rp.position)
        elif rp and rp.token:
            route_position_label = str(rp.token).strip()
        else:
            route_position_label = ''

        inv = inv_map.get(c.id)
        lr = last_read_map.get(c.id)

        pr = _safe_previous_non_control(lr, readings_by_id)
        ppr = _safe_previous_non_control(pr, readings_by_id) if pr else None
        pppr = _safe_previous_non_control(ppr, readings_by_id) if ppr else None

        writer.writerow(
            [
                c.id,
                c.token or '',
                _fmt_date(c.created_at.date() if c.created_at else None),
                'True' if c.block_billing else 'False',
                c.holder_id or '',
                c.holder.token if c.holder else '',
                _holder_name(c.holder),
                c.use_type_id or '',
                c.use_type.token if c.use_type else '',
                c.use_type.name if c.use_type else '',
                c.client_type_id or '',
                c.client_type.token if c.client_type else '',
                c.client_type.name if c.client_type else '',
                c.category_id or '',
                c.category.token if c.category else '',
                c.category.name if c.category else '',
                expl.id if expl else '',
                expl.token if expl else '',
                expl.name if expl else '',
                rz.id if rz else '',
                rz.token if rz else '',
                rz.name if rz else '',
                route.id if route else '',
                route.token if route else '',
                route.name if route else '',
                route_label,
                route_position_label,
                meter.id if meter else '',
                meter.code if meter else '',
                ('True' if meter.is_general else 'False') if meter else '',
                (meter.meter_general.code if meter.meter_general else '') if meter else '',
                inv.id if inv else '',
                _invoice_code(inv),
                _fmt_date(inv.issue_date) if inv else '',
                lr.id if lr else '',
                _fmt_date(lr.reading_date) if lr else '',
                _fmt_decimal(lr.reading_value) if lr else '',
                lr.previous_reading_id if lr else '',
                _fmt_date(pr.reading_date) if pr else '',
                _fmt_decimal(pr.reading_value) if pr else '',
                pr.previous_reading_id if pr else '',
                _fmt_date(ppr.reading_date) if ppr else '',
                _fmt_decimal(ppr.reading_value) if ppr else '',
                ppr.previous_reading_id if ppr else '',
                _fmt_date(pppr.reading_date) if pppr else '',
                _fmt_decimal(pppr.reading_value) if pppr else '',
            ]
        )

    return buffer.getvalue().encode('utf-8')

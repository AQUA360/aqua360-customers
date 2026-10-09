from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import Q, Count, Subquery, OuterRef, Exists

from auth.permissions import PermissionManager
from billing.models import Reading, Invoice
from coredata.models import ConfigProject
from coredata.utils.fire_usage_utils import get_fire_usage_tokens

PRE_INVOICE_TOKEN = '1'


CONSUMPTION_TYPES = {
    'fire_hydrant': {
        'display': "Boca d'incendi amb consum",
        'color': '#ef4444',
    },
    'inactive_consumption': {
        'display': 'Contracte de baixa amb consum',
        'color': '#f97316',
    },
    'duplicate_readings': {
        'display': 'Lectures duplicades al període',
        'color': '#eab308',
    },
}

BAIXA_STATUS_TOKEN = '-1'


def _get_fire_usage_token():
    return get_fire_usage_tokens()


def _holder_name(contract):
    person = contract.holder or contract.tenant or contract.owner
    if not person:
        return ''
    parts = [p for p in [person.name, person.surname] if p]
    return ' '.join(parts) if parts else ''


def _supply_address(contract):
    sp = contract.supply_point_default
    if sp and sp.address:
        return str(sp.address)
    return ''


def _supply_type_name(contract):
    sp = contract.supply_point_default
    if sp and sp.type:
        return sp.type.name or ''
    return ''


def _build_item(type_key, contract, reading=None, readings_in_period=None):
    type_info = CONSUMPTION_TYPES[type_key]
    sp = contract.supply_point_default

    consumption = None
    reading_date = None
    period_start = None
    period_end = None

    if reading:
        consumption = float(reading.calculated_value) if reading.calculated_value is not None else None
        reading_date = reading.reading_date.isoformat() if reading.reading_date else None

    return {
        'id': f"{type_key}_{contract.id}_{reading.id if reading else 'dup'}",
        'type': type_key,
        'type_display': type_info['display'],
        'type_color': type_info['color'],
        'contract_id': contract.id,
        'contract_token': contract.token or '',
        'contract_status': contract.status.token if contract.status else '',
        'contract_status_display': contract.status.name if contract.status else '',
        'holder_name': _holder_name(contract),
        'supply_point_id': sp.id if sp else None,
        'supply_point_token': sp.token if sp else '',
        'supply_point_address': _supply_address(contract),
        'supply_point_type': _supply_type_name(contract),
        'consumption': consumption,
        'consumption_unit': 'm3',
        'reading_date': reading_date,
        'period_start': period_start,
        'period_end': period_end,
        'readings_in_period': readings_in_period,
    }


def _search_filter(qs, search):
    if not search:
        return qs
    return qs.filter(
        Q(contract__token__icontains=search) |
        Q(contract__holder__name__icontains=search) |
        Q(contract__holder__surname__icontains=search) |
        Q(contract__supply_point_default__address__street__name__icontains=search)
    )


def _exploitation_filter(qs, exploitation_id):
    if not exploitation_id:
        return qs
    return qs.filter(
        contract__supply_point_default__connection__exploitation__id=exploitation_id
    )


def _reading_select_related(qs):
    return qs.select_related(
        'contract__status',
        'contract__holder',
        'contract__tenant',
        'contract__owner',
        'contract__supply_point_default__type',
        'contract__supply_point_default__address',
        'contract__use_type',
    )


def _last_billed_date_subquery():
    return (
        Reading.objects.filter(
            contract=OuterRef('contract'),
            is_active=True,
            contract__is_active=True,
            invoices__isnull=False,
        )
        .exclude(invoices__status__token=PRE_INVOICE_TOKEN)
        .order_by('-reading_date')
        .values('reading_date')[:1]
    )


def _billing_batch_filter(qs, billing_batch_id):
    if not billing_batch_id:
        return qs
    return qs.filter(billing__id=billing_batch_id)


def _has_definitive_invoice():
    return Invoice.objects.filter(readings=OuterRef('pk')).exclude(status__token=PRE_INVOICE_TOKEN)


def _get_fire_hydrant_items(search, exploitation_id, fire_usage_tokens, only_after_billing=False, billing_batch_id=None):
    qs = Reading.objects.filter(
        is_active=True,
        is_control=False,
        contract__is_active=True,
        contract__use_type__token__in=fire_usage_tokens,
        calculated_value__gt=0,
    ).order_by('-reading_date')

    if billing_batch_id:
        qs = _billing_batch_filter(qs, billing_batch_id)
    elif only_after_billing:
        qs = qs.filter(
            ~Exists(_has_definitive_invoice()),
            reading_date__gt=Subquery(_last_billed_date_subquery()),
        )

    qs = _search_filter(qs, search)
    qs = _exploitation_filter(qs, exploitation_id)
    qs = _reading_select_related(qs)

    seen = set()
    items = []
    for reading in qs:
        if reading.contract_id not in seen:
            seen.add(reading.contract_id)
            items.append(_build_item('fire_hydrant', reading.contract, reading=reading))
    return items


def _get_inactive_consumption_items(search, exploitation_id, only_after_billing=False, billing_batch_id=None):
    qs = Reading.objects.filter(
        is_active=True,
        is_control=False,
        contract__is_active=True,
        contract__status__token=BAIXA_STATUS_TOKEN,
        calculated_value__gt=0,
    ).order_by('-reading_date')

    if billing_batch_id:
        qs = _billing_batch_filter(qs, billing_batch_id)
    elif only_after_billing:
        qs = qs.filter(
            ~Exists(_has_definitive_invoice()),
            reading_date__gt=Subquery(_last_billed_date_subquery()),
        )

    qs = _search_filter(qs, search)
    qs = _exploitation_filter(qs, exploitation_id)
    qs = _reading_select_related(qs)

    seen = set()
    items = []
    for reading in qs:
        contract = reading.contract
        if not contract:
            continue
        # Only include if reading_date is after termination_date
        if contract.termination_date and reading.reading_date and reading.reading_date > contract.termination_date:
            if contract.id not in seen:
                seen.add(contract.id)
                items.append(_build_item('inactive_consumption', contract, reading=reading))
    return items


def _apply_contract_search_filter(contract_ids, search, exploitation_id):
    if not search and not exploitation_id:
        return contract_ids
    from contract.models import Contract
    qs = Contract.objects.filter(id__in=contract_ids)
    if search:
        qs = qs.filter(
            Q(token__icontains=search) |
            Q(holder__name__icontains=search) |
            Q(holder__surname__icontains=search) |
            Q(supply_point_default__address__street__name__icontains=search)
        )
    if exploitation_id:
        qs = qs.filter(
            supply_point_default__connection__exploitation__id=exploitation_id
        )
    return set(qs.values_list('id', flat=True))


def _get_duplicate_readings_items(search, exploitation_id, only_after_billing=False, billing_batch_id=None):
    from billing.models import ReadingBatch
    from contract.models import Contract

    base_batch_filters = dict(
        is_active=True,
        is_control=False,
        contract__is_active=True,
        batch__isnull=False,
        batch__is_active=True,
        contract__isnull=False,
    )
    base_no_batch_filters = dict(
        is_active=True,
        is_control=False,
        contract__is_active=True,
        batch__isnull=True,
        billing__isnull=True,
        contract__isnull=False,
    )

    if billing_batch_id:
        base_batch_filters['billing__id'] = billing_batch_id
        base_no_batch_filters['billing__id'] = billing_batch_id
    elif only_after_billing:
        last_billed_date_sq = _last_billed_date_subquery()
        base_batch_filters['reading_date__gt'] = Subquery(last_billed_date_sq)
        base_no_batch_filters['reading_date__gt'] = Subquery(last_billed_date_sq)

    # Cas 1: més d'una lectura activa no-control en el mateix lot (batch) actiu
    duplicates_by_batch = list(
        Reading.objects.filter(**base_batch_filters)
        .values('contract', 'batch')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    # Cas 2: més d'una lectura activa no-control sense batch i sense facturar
    duplicates_no_batch = list(
        Reading.objects.filter(**base_no_batch_filters)
        .values('contract')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    # Fusió: per contracte, guardem el comptador i l'origen (batch o sense batch)
    counts = {}
    batches = {}

    for d in duplicates_by_batch:
        cid = d['contract']
        if cid not in counts:
            counts[cid] = d['count']
            batches[cid] = d['batch']

    for d in duplicates_no_batch:
        cid = d['contract']
        if cid not in counts:
            counts[cid] = d['count']
            batches[cid] = None

    contract_ids = set(counts.keys())

    if search or exploitation_id:
        contract_ids = _apply_contract_search_filter(contract_ids, search, exploitation_id)

    contracts = Contract.objects.filter(id__in=contract_ids).select_related(
        'status',
        'holder', 'tenant', 'owner',
        'supply_point_default__type',
        'supply_point_default__address',
        'use_type',
    )

    batch_ids = {bid for bid in batches.values() if bid is not None}
    batch_names = {b.id: b.name or b.token for b in ReadingBatch.objects.filter(id__in=batch_ids)}

    items = []
    for contract in contracts:
        item = _build_item('duplicate_readings', contract, readings_in_period=counts.get(contract.id))
        batch_id = batches.get(contract.id)
        item['period_start'] = batch_names.get(batch_id, '') if batch_id else ''
        items.append(item)
    return items


class ConsumptionManagementViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        search = request.query_params.get('search', '').strip()
        type_filter = request.query_params.get('type', None)
        exploitation_id = request.query_params.get('exploitation', None)
        billing_batch_id = request.query_params.get('billing_batch', None)
        ordering = request.query_params.get('ordering', None)
        # mode: 'current' -> only alerts after last billing; 'history' -> all alerts
        mode = request.query_params.get('mode', 'current')
        only_after_billing = mode != 'history'
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1

        fire_usage_tokens = _get_fire_usage_token()

        results = []
        if not type_filter or type_filter == 'fire_hydrant':
            results += _get_fire_hydrant_items(search, exploitation_id, fire_usage_tokens, only_after_billing, billing_batch_id)
        if not type_filter or type_filter == 'inactive_consumption':
            results += _get_inactive_consumption_items(search, exploitation_id, only_after_billing, billing_batch_id)
        if not type_filter or type_filter == 'duplicate_readings':
            results += _get_duplicate_readings_items(search, exploitation_id, only_after_billing, billing_batch_id)

        if ordering:
            desc = ordering.startswith('-')
            key = ordering.lstrip('-')
            results.sort(key=lambda x: (x.get(key) is None, x.get(key) or ''), reverse=desc)

        per_page = 50
        total = len(results)
        start = (page - 1) * per_page
        end = start + per_page

        base_url = request.build_absolute_uri(request.path)
        params = request.query_params.copy()

        def build_url(p):
            params['page'] = p
            return f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        return Response({
            'count': total,
            'next': build_url(page + 1) if end < total else None,
            'previous': build_url(page - 1) if page > 1 else None,
            'results': results[start:end],
        })

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        perms = PermissionManager.get_model_permissions(request.user, 'contract', 'contract')
        return Response({
            'can_view': perms['can_view'],
            'can_add': False,
            'can_change': perms['can_change'],
            'can_delete': False,
            'permissions': {
                'view_consumptionmanagement': perms['can_view'],
            },
        })

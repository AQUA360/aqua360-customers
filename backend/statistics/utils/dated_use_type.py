"""
Tipus d'ús del contracte en el moment de generar la factura.

El tipus d'ús d'un contracte pot canviar després de facturar; els informes han de
mostrar el que tenia quan es va generar la factura. L'historial és a ContractLog
(field_name='use_type'), que desa el *nom* del tipus d'ús:

- el valor nou de l'últim canvi anterior (o igual) a la creació de la factura;
- si no n'hi ha, el valor antic del primer canvi posterior;
- sense cap canvi, el tipus d'ús actual del contracte.

Si el nom de l'historial ja no correspon a cap tipus d'ús (reanomenat), es fa servir
el tipus d'ús actual del contracte. Si l'historial diu que no en tenia, és None.

Dues variants amb el mateix criteri:
- annotate_dated_use_type: anotació SQL per a informes agregats (values/annotate).
- resolve_dated_use_types: resolució en Python per a informes fila a fila.
"""
from bisect import bisect_right
from collections import defaultdict

from django.db.models import Case, CharField, Exists, F, IntegerField, OuterRef, Subquery, Value, When
from django.db.models.functions import Coalesce

from contract.models import Contract, ContractLog, ContractUseType

USE_TYPE_FIELD_NAME = 'use_type'


def annotate_dated_use_type(queryset, invoice_prefix='invoice__', contract_field=None, name=False):
    """
    Anota `dated_use_type_id` (i, amb name=True, `dated_use_type_name`) al queryset.

    invoice_prefix: camí des del model del queryset fins a la factura ('' per a Invoice,
    'invoice__' per a InvoiceLineItem). contract_field: camí al contracte principal
    (per defecte, el de la factura). Si és buit, es fa servir el contracte de la baixa
    o el creat a partir de la sol·licitud, com als informes fila a fila.
    """
    if contract_field is None:
        contract_field = f'{invoice_prefix}contract'
    created_at_field = f'{invoice_prefix}created_at'

    queryset = queryset.annotate(
        _dated_use_type_contract_id=Coalesce(
            F(f'{contract_field}_id'),
            F(f'{invoice_prefix}contract_termination__contract_id'),
            Subquery(
                Contract.objects.filter(contract_request_id=OuterRef(f'{invoice_prefix}contract_request_id'))
                .order_by('id').values('id')[:1]
            ),
            output_field=IntegerField(),
        ),
    )

    logs = ContractLog.objects.filter(contract_id=OuterRef('_dated_use_type_contract_id'), field_name=USE_TYPE_FIELD_NAME)
    log_before = logs.filter(created_at__lte=OuterRef(created_at_field)).order_by('-created_at', '-id')
    log_after = logs.filter(created_at__gt=OuterRef(created_at_field)).order_by('created_at', 'id')

    # Les subconsultes es construeixen de nou a cada ús, i el nom de l'historial es
    # resol a tipus d'ús dins la mateixa subconsulta del log: referenciar amb OuterRef
    # una anotació que ja conté subconsultes fa petar Django en reanomenar els àlies.
    def current_use_type(field):
        return Subquery(
            Contract.objects.filter(id=OuterRef('_dated_use_type_contract_id')).values(f'use_type__{field}')[:1],
            output_field=output_fields[field](),
        )

    def log_use_type(log_qs, value_field, field):
        use_type_by_name = ContractUseType.objects.filter(name=OuterRef(value_field)).order_by('id').values(field)[:1]
        return Subquery(
            log_qs.annotate(_use_type_value=Subquery(use_type_by_name)).values('_use_type_value')[:1],
            output_field=output_fields[field](),
        )

    def dated_use_type(field):
        def from_log(log_qs, value_field):
            return Case(
                When(_dated_use_type_log_name__isnull=True, then=Value(None)),
                default=Coalesce(
                    log_use_type(log_qs, value_field, field), current_use_type(field),
                    output_field=output_fields[field](),
                ),
                output_field=output_fields[field](),
            )
        return Case(
            When(_dated_use_type_has_before=True, then=from_log(log_before, 'new_value')),
            When(_dated_use_type_has_after=True, then=from_log(log_after, 'old_value')),
            default=current_use_type(field),
            output_field=output_fields[field](),
        )

    output_fields = {'id': IntegerField, 'name': CharField}

    queryset = queryset.annotate(
        _dated_use_type_has_before=Exists(log_before),
        _dated_use_type_has_after=Exists(log_after),
    ).annotate(
        _dated_use_type_log_name=Case(
            When(_dated_use_type_has_before=True, then=Subquery(log_before.values('new_value')[:1])),
            When(_dated_use_type_has_after=True, then=Subquery(log_after.values('old_value')[:1])),
            default=Value(None),
            output_field=CharField(),
        ),
    ).annotate(dated_use_type_id=dated_use_type('id'))
    if name:
        queryset = queryset.annotate(dated_use_type_name=dated_use_type('name'))
    return queryset


def resolve_dated_use_types(invoice_contracts):
    """
    invoice_contracts: iterable de (invoice, contract) — el contracte resolt per l'informe
    (pot venir de la baixa o de la sol·licitud). Retorna {invoice.id: ContractUseType | None}.
    Dues consultes en total, independentment del nombre de factures.
    """
    pairs = [(invoice, contract) for invoice, contract in invoice_contracts]
    contract_ids = {contract.id for _invoice, contract in pairs if contract is not None}

    logs_by_contract = defaultdict(list)
    if contract_ids:
        logs = (
            ContractLog.objects.filter(
                contract_id__in=contract_ids, field_name=USE_TYPE_FIELD_NAME, created_at__isnull=False,
            )
            .order_by('contract_id', 'created_at', 'id')
            .values_list('contract_id', 'created_at', 'old_value', 'new_value')
        )
        for contract_id, created_at, old_value, new_value in logs:
            logs_by_contract[contract_id].append((created_at, old_value, new_value))

    names = {
        value
        for contract_logs in logs_by_contract.values()
        for _created_at, old_value, new_value in contract_logs
        for value in (old_value, new_value)
        if value is not None
    }
    use_types_by_name = {}
    if names:
        for use_type in ContractUseType.objects.filter(name__in=names).order_by('-id'):
            use_types_by_name[use_type.name] = use_type  # en cas de duplicats, el d'id més baix

    result = {}
    for invoice, contract in pairs:
        if contract is None:
            result[invoice.id] = None
            continue
        current = contract.use_type
        contract_logs = logs_by_contract.get(contract.id)
        if not contract_logs or invoice.created_at is None:
            result[invoice.id] = current
            continue
        dates = [created_at for created_at, _old, _new in contract_logs]
        idx = bisect_right(dates, invoice.created_at)
        if idx > 0:
            log_name = contract_logs[idx - 1][2]  # new_value de l'últim canvi anterior
        else:
            log_name = contract_logs[0][1]  # old_value del primer canvi posterior
        if log_name is None:
            result[invoice.id] = None
        else:
            result[invoice.id] = use_types_by_name.get(log_name, current)
    return result

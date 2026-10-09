import datetime

from django.db.models import Q


def parse_ids(value):
    if value is None or value == '':
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, (list, tuple, set)):
        ids = []
        for item in value:
            ids.extend(parse_ids(item))
        return ids
    try:
        return [int(v) for v in str(value).split(',') if v.strip() != '']
    except (TypeError, ValueError):
        return []


def _values_for_key(payload, key):
    """Tots els valors d'una clau, preservant getlist() i llistes JSON."""
    if payload is None:
        return None
    if hasattr(payload, 'getlist') and key in payload:
        values = payload.getlist(key)
        if len(values) > 1:
            return values
        return values[0] if values else None
    if hasattr(payload, 'get'):
        return payload.get(key)
    return None


def _ids_from_keys(payload, *keys):
    ids = []
    seen = set()
    for key in keys:
        for i in parse_ids(_values_for_key(payload, key)):
            if i not in seen:
                seen.add(i)
                ids.append(i)
    return ids


def querydict_to_dict(qd):
    """Converteix un QueryDict preservant valors múltiples (no només l'últim)."""
    payload = {}
    for key in qd:
        values = qd.getlist(key)
        payload[key] = values if len(values) > 1 else (values[0] if values else None)
    return payload


def request_payload_as_dict(request):
    """Payload del trigger d'informes, sense perdre IDs de multi-select."""
    payload = {}
    query_params = getattr(request, 'query_params', None)
    if query_params:
        payload.update(querydict_to_dict(query_params))
    data = getattr(request, 'data', None)
    if data:
        if hasattr(data, 'getlist'):
            payload.update(querydict_to_dict(data))
        elif isinstance(data, dict):
            payload.update(data)
    return payload


def get_billing_ids(data, include_legacy_id=True):
    """IDs de facturació del payload: `billing_ids`, `billing_id` i `id` (llegat).

    El frontal envia sovint `billing_ids` amb totes les seleccions i també `id`
    (o `billing_id`) amb només l'última. Sense unir-los, els informes filtren
    `Invoice.objects.filter(billing__id=id)` i es queden només amb l'última.
    """
    keys = ['billing_ids', 'billing_id']
    if include_legacy_id:
        keys.append('id')
    return _ids_from_keys(data, *keys)


def get_multi_ids(data):
    return {
        'billing_ids': _ids_from(data, 'billing_id', 'billing_ids'),
        'remittance_ids': _ids_from(data, 'remittance_id', 'remittance_ids'),
        'person_ids': _ids_from_keys(data, 'person_ids', 'person_id'),
        'contract_ids': _ids_from_keys(data, 'contract_ids', 'contract_id'),
    }


def _person_roles_q(person_ids, prefix=''):
    return (
        Q(**{f'{prefix}owner_id__in': person_ids})
        | Q(**{f'{prefix}tenant_id__in': person_ids})
        | Q(**{f'{prefix}holder_id__in': person_ids})
    )


def invoice_multi_filter_q(billing_ids=None, remittance_ids=None, person_ids=None, contract_ids=None):
    q = None
    if billing_ids:
        q = Q(billing_id__in=billing_ids)
    if contract_ids:
        clause = Q(contract_id__in=contract_ids)
        q = clause if q is None else q & clause
    if person_ids:
        clause = _person_roles_q(person_ids, prefix='contract__')
        q = clause if q is None else q & clause
    if remittance_ids:
        clause = Q(payments__remittances__id__in=remittance_ids)
        q = clause if q is None else q & clause
    return q


def payment_multi_filter_q(billing_ids=None, remittance_ids=None, person_ids=None, contract_ids=None):
    q = None
    if billing_ids:
        q = Q(invoice__billing_id__in=billing_ids)
    if contract_ids:
        clause = Q(invoice__contract_id__in=contract_ids)
        q = clause if q is None else q & clause
    if person_ids:
        clause = _person_roles_q(person_ids, prefix='invoice__contract__')
        q = clause if q is None else q & clause
    if remittance_ids:
        clause = Q(remittances__id__in=remittance_ids)
        q = clause if q is None else q & clause
    return q


def contract_multi_filter_q(person_ids=None, contract_ids=None):
    q = None
    if contract_ids:
        q = Q(id__in=contract_ids)
    if person_ids:
        clause = _person_roles_q(person_ids)
        q = clause if q is None else q & clause
    return q


def _ids_from(payload, singular_key, plural_key):
    """Combina la variant singular (`billing_id`) i plural (`billing_ids`) d'un camp."""
    return _ids_from_keys(payload, plural_key, singular_key)


def get_exclude_billing_ids(data):
    """IDs de billing a excloure (`exclude_billing_id` / `exclude_billing_ids`)."""
    return _ids_from(data, 'exclude_billing_id', 'exclude_billing_ids')


def apply_exclude_billing_ids(queryset, data, field='billing_id'):
    """Exclou registres lligats als billing IDs demanats (p. ex. field='billing_id'
    per Invoice, 'invoice__billing_id' per Payment)."""
    exclude_ids = get_exclude_billing_ids(data)
    if exclude_ids:
        queryset = queryset.exclude(**{f'{field}__in': exclude_ids})
    return queryset


def get_serie_ids(data):
    """IDs d'InvoiceSequence (`serie_id` / `serie_ids`)."""
    return _ids_from(data, 'serie_id', 'serie_ids')


def apply_serie_ids(queryset, data, field='serie_final'):
    """Filtra per invoices on serie_final comença amb el prefix d'alguna InvoiceSequence
    seleccionada (p. ex. field='serie_final' o 'invoice__serie_final')."""
    serie_ids = get_serie_ids(data)
    if not serie_ids:
        return queryset

    from billing.models import InvoiceSequence

    prefixes = [
        p for p in InvoiceSequence.objects.filter(id__in=serie_ids)
        .exclude(prefix__isnull=True)
        .exclude(prefix='')
        .values_list('prefix', flat=True)
    ]
    if not prefixes:
        return queryset.none()

    q = Q()
    for prefix in prefixes:
        q |= Q(**{f'{field}__startswith': prefix})
    return queryset.filter(q)


def get_serie_final_range(data):
    """Extrems del rang de numero de factura (`serie_final_from` / `serie_final_to`)
    i el prefix de serie que l'acota (`prefix`), tal com els envien
    billing/reports/general-billing-summary i el bloc "Filtres extra" de
    billing/reports/add. Les cadenes buides es tracten com "sense limit"."""
    def clean(key):
        value = _values_for_key(data, key)
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    return clean('serie_final_from'), clean('serie_final_to'), clean('prefix')


def has_serie_final_range(data):
    """Cert si el payload demana un rang de numero de factura (qualsevol dels tres
    camps). Els informes ho fan servir per acceptar el rang com a unica seleccio,
    sense exigir lot de facturacio ni periode."""
    return any(value is not None for value in get_serie_final_range(data))


def serie_final_range_invoices():
    """Base d'un informe seleccionat nomes per un rang de numero de factura: totes
    les factures del tipus "factura" (el mateix `type_final` que fan servir les
    seleccions per periode), que despres `apply_serie_final_range` acota al rang
    demanat des de `filter_pending_invoices`.

    Sense lot ni periode no hi ha cap altre criteri que hi hagi d'entrar: el rang de
    numeros ja identifica les factures que es volen."""
    from billing.models import Invoice
    from coredata.models import ConfigProject

    invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
    return Invoice.objects.filter(type_final=invoice_type).distinct()


def serie_final_range_period(invoices):
    """Periode implicit d'una seleccio per rang de numero de factura: la primera i
    l'ultima data d'emissio de les factures triades, com a datetime.

    Els informes fan servir start_date/end_date per als titols, el nom del fitxer i
    els conjunts auxiliars que van per data (pagaments, dipositos...). Quan la
    seleccio es nomes un rang de numeros no hi ha periode al payload, i agafar-lo de
    les factures seleccionades manté aquesta part dels informes coherent en lloc de
    deixar-la sense acotar. Retorna (None, None) si el rang no dona cap factura."""
    from django.db.models import Max, Min

    bounds = invoices.aggregate(min_date=Min('issue_date'), max_date=Max('issue_date'))
    start, end = bounds.get('min_date'), bounds.get('max_date')
    if not start or not end:
        return None, None
    return (
        datetime.datetime.combine(start, datetime.time.min),
        datetime.datetime.combine(end, datetime.time.min),
    )


def apply_serie_final_range(queryset, data):
    """Acota un queryset d'Invoice al rang de numero de factura demanat.

    Amb prefix pero sense extrems, filtra tota la serie del prefix. Sense cap dels
    tres camps no toca res, de manera que els informes que no els envien es
    comporten exactament com abans."""
    serie_final_from, serie_final_to, prefix = get_serie_final_range(data)
    if serie_final_from is None and serie_final_to is None and prefix is None:
        return queryset

    # generate_register_billing_summary ja filtra el rang pel seu compte abans de
    # cridar filter_pending_invoices: re-anotar el mateix alias hi petaria.
    if 'serie_final_num' in queryset.query.annotations:
        return queryset

    if serie_final_from is None and serie_final_to is None:
        # Nomes prefix: tota la serie, sense acotar-ne el numero. Es el cas habitual
        # dels clients amb el mes dins del serie_final ("FC/AAAAMM/"), on el
        # prefix ja identifica la facturacio que es vol.
        return queryset.filter(serie_final__startswith=prefix)

    from billing.utils.invoice_range_utils import filter_invoices_by_serie_final_range

    return filter_invoices_by_serie_final_range(
        queryset,
        serie_final_from=serie_final_from,
        serie_final_to=serie_final_to,
        prefix=prefix,
    )


def _label_names(model, ids, name_fields=('name',), joiner=', '):
    if not ids:
        return None
    objs = model.objects.filter(id__in=ids)
    names = []
    for obj in objs:
        parts = [str(getattr(obj, f)) for f in name_fields if getattr(obj, f, None)]
        names.append(' '.join(parts) if parts else f"ID {obj.id}")
    return joiner.join(names) if names else None


def _format_date(value):
    if not value:
        return None
    return str(value)[:10]


def resolve_filter_labels(payload):
    """Converteix el payload cru de POST /statistics/available-reports/<id>/trigger/
    en una llista de {label, value} amb noms/tokens llegibles (no ids crus), per
    mostrar al frontend els filtres aplicats sense que hagi de resoldre cada id.
    Camps absents/buits es descarten silenciosament."""
    if not payload:
        return []

    from billing.models import Billing, InvoiceSequence, PaymentRemittance
    from coredata.models import Person
    from contract.models import Contract, PaymentType
    from service.models import Exploitation
    from pricing.models import Product, Tax
    from statistics.models import ReportType

    entries = []

    def add(label, value):
        if value not in (None, '', []):
            entries.append({'label': label, 'value': value})

    date_range = payload.get('date_range')
    if date_range and isinstance(date_range, (list, tuple)) and len(date_range) >= 2:
        add('Període', f"{_format_date(date_range[0])} - {_format_date(date_range[1])}")
    else:
        start_date = _format_date(payload.get('start_date'))
        end_date = _format_date(payload.get('end_date'))
        if start_date or end_date:
            add('Període', f"{start_date or '...'} - {end_date or '...'}")

    exploitation_id = payload.get('exploitation_id')
    if exploitation_id:
        exploitation = Exploitation.objects.filter(id=exploitation_id).first()
        add('Explotació', exploitation.name if exploitation else None)

    billing_ids = get_billing_ids(
        payload,
        include_legacy_id=not (payload.get('remittance_id') or payload.get('remittance_ids')),
    )
    add('Facturació', _label_names(Billing, billing_ids, name_fields=('name', 'token')))

    exclude_billing_ids = get_exclude_billing_ids(payload)
    add(
        'Exclou facturació',
        _label_names(Billing, exclude_billing_ids, name_fields=('name', 'token')),
    )

    serie_ids = get_serie_ids(payload)
    add('Sèries', _label_names(InvoiceSequence, serie_ids, name_fields=('prefix',)))

    serie_final_from, serie_final_to, serie_final_prefix = get_serie_final_range(payload)
    if serie_final_from or serie_final_to:
        rang = f"{serie_final_from or '...'} - {serie_final_to or '...'}"
        if serie_final_prefix:
            rang = f"{rang} (prefix {serie_final_prefix})"
        add('Núm. de factura', rang)
    elif serie_final_prefix:
        add('Sèrie del núm. de factura', serie_final_prefix)

    remittance_ids = _ids_from(payload, 'remittance_id', 'remittance_ids')
    add('Remesa', _label_names(PaymentRemittance, remittance_ids, name_fields=('token',)))

    person_ids = parse_ids(payload.get('person_ids'))
    add('Persones', _label_names(Person, person_ids, name_fields=('name', 'surname')))

    contract_ids = parse_ids(payload.get('contract_ids'))
    add('Contractes', _label_names(Contract, contract_ids, name_fields=('token',)))

    report_type_id = payload.get('report_type_id')
    if report_type_id:
        report_type = ReportType.objects.filter(id=report_type_id).first()
        add('Tipus d\'informe', report_type.name if report_type else None)

    product_ids = parse_ids(payload.get('product_ids'))
    add('Productes', _label_names(Product, product_ids, name_fields=('name',)))

    taxes_ids = parse_ids(payload.get('taxes_ids'))
    add('Impostos', _label_names(Tax, taxes_ids, name_fields=('name',)))

    payment_type_ids = parse_ids(payload.get('payment_type_ids'))
    if payment_type_ids:
        names = []
        for pt in PaymentType.objects.filter(id__in=payment_type_ids):
            names.append(pt.name or pt.get_token_display())
        add('Formes de pagament', ', '.join(names) if names else None)

    if 'include_preinvoices' in payload:
        add('Inclou pre-factures', 'Sí' if payload.get('include_preinvoices') in (True, 'true', 'True', '1', 1) else 'No')

    if 'include_tax_free_lines' in payload:
        add('Inclou línies sense impostos', 'Sí' if payload.get('include_tax_free_lines') in (True, 'true', 'True', '1', 1) else 'No')

    year = payload.get('model_347_year') or payload.get('year')
    add('Any', year)

    add('Versió', payload.get('version'))
    add('Tipus de compte', payload.get('account_type') or payload.get('accounting_type'))

    return entries

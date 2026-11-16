from django.db.models import Q, Case, When, F, CharField, Value
from django.db.models.functions import Concat, Cast
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from billing.models import ReadingBatch, Invoice
from contract.models import Contract, ContractRequest, Bail, ContractTerminationRequest
from coredata.models import Person
from order.models import Order, Operator
from service.models import Meter, SupplyPoint, Cluster, Connection, ConnectionRequest, SupplyCut


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _parse_positive_int(raw_value, default):
    """Retorna un enter >= 1, o None si el valor no és numèric."""
    if raw_value is None or raw_value == '':
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else default


def _user_can_view(user, model):
    return user.has_perm(f'{model._meta.app_label}.view_{model._meta.model_name}')


def _check_all_words_present(text, words):
    text_lower = str(text).lower()
    return all(word in text_lower for word in words)


def _value_as_str(value):
    if value is None:
        return ''
    return str(value)


def _build_object_data(item, object_fields, aliases=None):
    aliases = aliases or {}
    data = {}
    for field in object_fields:
        key = aliases.get(field, field)
        data[key] = _value_as_str(item.get(field))
    return data


def _pick_match(item, fields, query_words, person_fields=None):
    """Tria el camp i el valor a mostrar per un registre ja filtrat a BD."""
    for field in fields:
        if field == 'id':
            continue
        field_value = _value_as_str(item.get(field))
        if not _check_all_words_present(field_value, query_words):
            continue
        if person_fields and any(
            field.startswith(f'{prefix}__{name_field}')
            for prefix, name_fields in person_fields
            for name_field in name_fields
        ):
            prefix = next(
                prefix
                for prefix, name_fields in person_fields
                if any(field.startswith(f'{prefix}__{name_field}') for name_field in name_fields)
            )
            full_name = f"{item.get(f'{prefix}__name', '')} {item.get(f'{prefix}__surname', '')}".strip()
            return field, full_name
        return field, item.get(field)

    if person_fields:
        for prefix, name_fields in person_fields:
            full_name = ' '.join(_value_as_str(item.get(f'{prefix}__{field}')) for field in name_fields)
            if _check_all_words_present(full_name, query_words):
                return f'{prefix}_full_name', full_name

    # Fallback: el queryset ja ha filtrat; mostrem el primer camp amb valor
    for field in fields:
        if field == 'id':
            continue
        value = item.get(field)
        if value not in (None, ''):
            return field, value
    return 'id', item.get('id')


def _person_name_queryset(model, query_words, object_fields):
    name_filter = Q()
    for word in query_words:
        name_filter &= (
            Q(name__icontains=word) |
            Q(surname__icontains=word) |
            Q(token__icontains=word)
        )
    values_fields = list(dict.fromkeys(['token', 'full_name', 'id', *object_fields]))
    return model.objects.filter(name_filter).annotate(
        full_name=Concat('name', Value(' '), 'surname', output_field=CharField())
    ).values(*values_fields).order_by('id')


def _contract_like_queryset(model, fields, person_fields, query_words, object_fields):
    query_filter = Q()
    for word in query_words:
        word_filter = Q()
        for field in fields:
            if not any(
                field.startswith(f'{prefix}__{name_field}')
                for prefix, name_fields in person_fields
                for name_field in name_fields
            ):
                word_filter |= Q(**{f'{field}__icontains': word})
        for prefix, name_fields in person_fields:
            person_filter = Q()
            for field in name_fields:
                person_filter |= Q(**{f'{prefix}__{field}__icontains': word})
            word_filter |= person_filter
        query_filter &= word_filter

    annotations = {
        f'{prefix}_full_name': Concat(
            f'{prefix}__name', Value(' '), f'{prefix}__surname',
            output_field=CharField(),
        )
        for prefix, _ in person_fields
    }
    values_fields = fields + [f'{prefix}_full_name' for prefix, _ in person_fields] + list(object_fields)
    # Evita duplicats a .values()
    values_fields = list(dict.fromkeys(['id', *values_fields]))
    return model.objects.filter(query_filter).annotate(**annotations).values(*values_fields).order_by('id')


def _supply_point_queryset(query_words, object_fields):
    address_filter = Q()
    for word in query_words:
        address_filter &= (
            Q(address__city__name__icontains=word) |
            Q(address__street_number__street__name__icontains=word) |
            Q(address__street_number__number__icontains=word) |
            Q(address__floor__icontains=word) |
            Q(address__door__icontains=word) |
            Q(token__icontains=word) |
            Q(name__icontains=word)
        )

    return SupplyPoint.objects.filter(address_filter).annotate(
        address_complete=Concat(
            'address__city__name', Value(' - '),
            'address__street_number__street__name',
            Case(
                When(address__street_number__number__isnull=False, then=Value(' - ')),
                default=Value(''),
                output_field=CharField(),
            ),
            Case(
                When(
                    address__street_number__number__isnull=False,
                    then=Cast(F('address__street_number__number'), CharField()),
                ),
                default=Value(''),
                output_field=CharField(),
            ),
            Case(
                When(address__floor__isnull=False, then=Value(' - ')),
                default=Value(''),
                output_field=CharField(),
            ),
            Case(
                When(address__floor__isnull=False, then=F('address__floor')),
                default=Value(''),
                output_field=CharField(),
            ),
            Case(
                When(address__door__isnull=False, then=Value(' - ')),
                default=Value(''),
                output_field=CharField(),
            ),
            Case(
                When(address__door__isnull=False, then=F('address__door')),
                default=Value(''),
                output_field=CharField(),
            ),
            output_field=CharField(),
        ),
        # Adreça llegible sense carregar l'objecte Address (evita N+1)
        address_display=F('address__address_search'),
    ).values(*list(dict.fromkeys([
        'token', 'address_complete', 'address_display', 'name', 'id', *object_fields,
    ]))).order_by('id')


def _generic_queryset(model, fields, query_words, object_fields):
    query_filter = Q()
    for word in query_words:
        word_filter = Q()
        for field in fields:
            word_filter |= Q(**{f'{field}__icontains': word})
        query_filter &= word_filter

    values_fields = list(dict.fromkeys([*fields, *object_fields, 'id']))
    return model.objects.filter(query_filter).values(*values_fields).order_by('id')


def _format_results(items, model_info, query, query_words, match_fields, person_fields=None):
    entity = model_info['entity']
    app = model_info['app']
    object_fields = model_info['object_fields']
    formatted = []

    for item in items:
        if model_info['model'] in (Person, Operator):
            full_name = (item.get('full_name') or '').lower()
            token = (item.get('token') or '').lower()
            if _check_all_words_present(full_name, query_words):
                found_field, found = 'full_name', item['full_name']
            elif _check_all_words_present(token, query_words):
                found_field, found = 'token', item['token']
            else:
                found_field, found = 'full_name', item.get('full_name') or item.get('token')
        else:
            found_field, found = _pick_match(item, match_fields, query_words, person_fields)

        object_data = _build_object_data(
            item, object_fields, model_info.get('object_field_aliases')
        )
        # SupplyPoint: mostra l'adreça completa en lloc de l'id FK
        if model_info['model'] is SupplyPoint and 'address' in object_data:
            object_data['address'] = _value_as_str(
                item.get('address_display') or item.get('address_complete')
            )

        formatted.append({
            'search': query,
            'found': found,
            'entity': entity,
            'app': app,
            'found_field': found_field,
            'item_id': item['id'],
            'object_data': object_data,
        })
    return formatted


# Amb @api_view s'aplica l'autenticació per token i el permís per defecte (IsAuthenticated)
@api_view(['GET'])
def search_results(request):
    query = request.GET.get('q', '').strip()
    entity_filter = request.GET.get('entity', '').strip()

    page = _parse_positive_int(request.GET.get('page'), 1)
    page_size = _parse_positive_int(request.GET.get('page_size'), DEFAULT_PAGE_SIZE)
    if page is None or page_size is None:
        return Response(
            {'detail': 'page i page_size han de ser enters positius.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    page_size = min(page_size, MAX_PAGE_SIZE)

    models = [
        {
            'model': Contract,
            'fields': [
                'token', 'id', 'holder__token', 'holder__name', 'holder__surname',
                'tenant__name', 'tenant__surname', 'owner__name', 'owner__surname',
            ],
            'entity': 'Contract',
            'app': 'Contract',
            'person_fields': [
                ('holder', ['name', 'surname']),
                ('tenant', ['name', 'surname']),
                ('owner', ['name', 'surname']),
            ],
            'object_fields': [
                'token', 'status__name', 'supply_point_default__address__address_search',
                'holder__token', 'holder__name', 'holder__surname',
            ],
            # Clau estable a la resposta (abans era supply_point_default__address via __str__)
            'object_field_aliases': {
                'supply_point_default__address__address_search': 'supply_point_default__address',
            },
        },
        {
            'model': ContractRequest,
            'fields': [
                'token', 'id', 'holder__token', 'holder__name', 'holder__surname',
                'tenant__name', 'tenant__surname', 'owner__name', 'owner__surname',
            ],
            'entity': 'ContractRequest',
            'app': 'Contract',
            'person_fields': [
                ('holder', ['name', 'surname']),
                ('tenant', ['name', 'surname']),
                ('owner', ['name', 'surname']),
            ],
            'object_fields': [
                'token', 'status__name', 'supply_point_default__address__address_search',
                'holder__token', 'holder__name', 'holder__surname',
            ],
            'object_field_aliases': {
                'supply_point_default__address__address_search': 'supply_point_default__address',
            },
        },
        {
            'model': ContractTerminationRequest,
            'fields': ['token', 'id', 'contract__token'],
            'entity': 'ContractTerminationRequest',
            'app': 'Contract',
            'object_fields': ['token', 'status__name', 'contract__token', 'type__name'],
        },
        {
            'model': SupplyPoint,
            'fields': [
                'token', 'id', 'name', 'address__postal_code', 'address__city__name',
                'address__street_number__street__name', 'address__street_number__number',
            ],
            'entity': 'Supply-Point',
            'app': 'Service',
            'object_fields': ['token', 'status__name', 'address'],
            'match_fields': ['address_complete', 'token', 'name'],
        },
        {
            'model': Meter,
            'fields': ['code', 'id', 'code2'],
            'entity': 'Meter',
            'app': 'Service',
            'object_fields': [
                'token', 'code', 'address_street__name', 'address_street_number__number',
                'address_city__name',
            ],
            'object_field_aliases': {
                'address_street__name': 'address_street',
                'address_street_number__number': 'address_street_number',
            },
        },
        {
            'model': Cluster,
            'fields': ['token', 'id', 'installation_at'],
            'entity': 'Cluster',
            'app': 'Service',
            'object_fields': [
                'token', 'address_street__name', 'address_street_number__number',
                'address_city__name',
            ],
            'object_field_aliases': {
                'address_street__name': 'address_street',
                'address_street_number__number': 'address_street_number',
            },
        },
        {
            'model': Connection,
            'fields': ['token', 'id', 'code_gis'],
            'entity': 'Connection',
            'app': 'Service',
            'object_fields': [
                'token', 'status__name', 'address_street__name', 'address_street_number__number',
                'address_city__name',
            ],
            'object_field_aliases': {
                'address_street__name': 'address_street',
                'address_street_number__number': 'address_street_number',
            },
        },
        {
            'model': ConnectionRequest,
            'fields': ['token', 'id', 'code_gis'],
            'entity': 'Connection-Request',
            'app': 'Service',
            'object_fields': [
                'token', 'status__name', 'address_street__name', 'address_street_number__number',
                'address_city__name',
            ],
            'object_field_aliases': {
                'address_street__name': 'address_street',
                'address_street_number__number': 'address_street_number',
            },
        },
        {
            'model': SupplyCut,
            'fields': ['token', 'id'],
            'entity': 'SupplyCut',
            'app': 'Service',
            'object_fields': ['token', 'status__name'],
        },
        {
            'model': Bail,
            'fields': ['token', 'id', 'contract__token'],
            'entity': 'Bail',
            'app': 'Billing',
            'object_fields': ['token', 'status__name', 'contract__token', 'amount'],
        },
        {
            'model': Person,
            'fields': ['token', 'id', 'surname', 'name'],
            'entity': 'Person',
            'app': 'Contract',
            'object_fields': ['token', 'name', 'surname'],
        },
        {
            'model': ReadingBatch,
            'fields': ['token', 'id'],
            'entity': 'ReadingBatch',
            'app': 'Billing',
            'object_fields': ['token', 'status__name', 'id'],
        },
        {
            'model': Invoice,
            'fields': [
                'token', 'id', 'exploitation__token', 'company__alias', 'contract__token', 'number',
            ],
            'entity': 'Invoice',
            'app': 'Billing',
            'object_fields': ['token', 'status__name', 'type_final', 'title_final'],
        },
        {
            'model': Order,
            'fields': ['token', 'id', 'contract__token', 'supply_point__token'],
            'entity': 'Order',
            'app': 'Order',
            'object_fields': ['token', 'status__name', 'type__name'],
        },
        {
            'model': Operator,
            'fields': ['token', 'id', 'surname', 'name'],
            'entity': 'Operator',
            'app': 'Order',
            'object_fields': ['token', 'name', 'surname'],
        },
    ]

    empty_response = {
        'query': query,
        'total_count': 0,
        'page': page,
        'page_size': page_size,
        'total_pages': 0,
        'has_next': False,
        'has_previous': False,
        'matching_entities': [],
        'results': [],
    }

    if not query:
        return JsonResponse(empty_response)

    query_words = [word.lower() for word in query.split() if word]
    if not query_words:
        return JsonResponse(empty_response)

    # Models amb view_* (el filtre d'entitat no limita el discovery dels chips)
    permitted = [
        model_info for model_info in models
        if _user_can_view(request.user, model_info['model'])
    ]

    offset = (page - 1) * page_size
    remaining_to_skip = offset
    remaining_to_take = page_size
    results = []
    total_count = 0
    matching_entities = []

    for model_info in permitted:
        model = model_info['model']
        fields = model_info['fields']
        person_fields = model_info.get('person_fields')
        object_fields = model_info['object_fields']
        match_fields = model_info.get('match_fields', fields)
        entity = model_info['entity']

        if model in (Person, Operator):
            queryset = _person_name_queryset(model, query_words, object_fields)
        elif model in (Contract, ContractRequest):
            queryset = _contract_like_queryset(
                model, fields, person_fields, query_words, object_fields
            )
        elif model is SupplyPoint:
            queryset = _supply_point_queryset(query_words, object_fields)
        else:
            queryset = _generic_queryset(model, fields, query_words, object_fields)

        model_count = queryset.count()
        if model_count > 0:
            matching_entities.append(entity)

        # Resultats i total_count només per l'entitat filtrada (o totes)
        if entity_filter and entity_filter != entity:
            continue

        total_count += model_count

        if remaining_to_take == 0:
            continue

        if remaining_to_skip >= model_count:
            remaining_to_skip -= model_count
            continue

        start = remaining_to_skip
        end = start + remaining_to_take
        page_items = list(queryset[start:end])
        formatted = _format_results(
            page_items, model_info, query, query_words, match_fields, person_fields
        )
        results.extend(formatted)
        remaining_to_take -= len(page_items)
        remaining_to_skip = 0

    total_pages = (total_count + page_size - 1) // page_size if total_count else 0

    return JsonResponse({
        'query': query,
        'total_count': total_count,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_previous': page > 1 and total_count > 0,
        'matching_entities': matching_entities,
        'results': results,
    })

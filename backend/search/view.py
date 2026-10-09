from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q, Case, When, F
from billing.models import ReadingBatch, Invoice
from contract.models import Contract, ContractRequest, Bail, ContractTerminationRequest
from coredata.models import Person
from order.models import Order, Operator
from service.models import Meter, SupplyPoint, Cluster, Connection, ConnectionRequest, SupplyCut
from django.db.models.functions import Concat, Cast
from django.db.models import CharField, Value
from django.core.paginator import Paginator

def search_results(request):
    query = request.GET.get('q', '').strip()
    entity_filter = request.GET.get('entity', '').strip()
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    
    results = []
    total_count = 0
    
    query_words = [word.lower() for word in query.split() if word]
    
    models = [
        {'model': Contract, 'fields': ['token', 'id', 'holder__token', 'holder__name', 'holder__surname', 'tenant__name', 'tenant__surname', 'owner__name', 'owner__surname'], 'entity': 'Contract', 'app': 'Contract', 'person_fields': [('holder', ['name', 'surname']), ('tenant', ['name', 'surname']), ('owner', ['name', 'surname'])], 'object_fields': ['token', 'status__name', 'supply_point_default__address', 'holder__token', 'holder__name', 'holder__surname']},
        {'model': ContractRequest, 'fields': ['token', 'id', 'holder__token', 'holder__name', 'holder__surname', 'tenant__name', 'tenant__surname', 'owner__name', 'owner__surname'], 'entity': 'ContractRequest', 'app': 'Contract', 'person_fields': [('holder', ['name', 'surname']), ('tenant', ['name', 'surname']), ('owner', ['name', 'surname'])], 'object_fields': ['token', 'status__name', 'supply_point_default__address', 'holder__token', 'holder__name', 'holder__surname']},
        {'model': ContractTerminationRequest, 'fields': ['token', 'id','contract__token'], 'entity': 'ContractTerminationRequest', 'app': 'Contract', 'object_fields': ['token', 'status__name', 'contract__token', 'type__name']},
        {'model': SupplyPoint, 'fields': ['token', 'id', 'name', 'address__postal_code', 'address__city__name', 'address__street_number__street__name', 'address__street_number__number'], 'entity': 'Supply-Point', 'app': 'Service', 'object_fields': ['token', 'status__name', 'address']},
        {'model': Meter, 'fields': ['code', 'id', 'code2'], 'entity': 'Meter', 'app': 'Service', 'object_fields': ['token', 'code', 'address_street', 'address_street_number', 'address_city__name']},
        {'model': Cluster, 'fields': ['token', 'id', 'installation_at'], 'entity': 'Cluster', 'app': 'Service', 'object_fields': ['token', 'address_street', 'address_street_number', 'address_city__name']},
        {'model': Connection, 'fields': ['token', 'id', 'code_gis'], 'entity': 'Connection', 'app': 'Service', 'object_fields': ['token', 'status__name', 'address_street', 'address_street_number', 'address_city__name']},
        {'model': ConnectionRequest, 'fields': ['token', 'id', 'code_gis'], 'entity': 'Connection-Request', 'app': 'Service', 'object_fields': ['token', 'status__name', 'address_street', 'address_street_number', 'address_city__name']},
        {'model': SupplyCut, 'fields': ['token', 'id'], 'entity': 'SupplyCut', 'app': 'Service', 'object_fields': ['token', 'status__name']},
        {'model': Bail, 'fields': ['token', 'id', 'contract__token'], 'entity': 'Bail', 'app': 'Billing', 'object_fields': ['token', 'status__name', 'contract__token', 'amount']},
        {'model': Person, 'fields': ['token', 'id', 'surname', 'name'], 'entity': 'Person', 'app': 'Contract', 'object_fields': ['token', 'name', 'surname']},
        {'model': ReadingBatch, 'fields': ['token', 'id'], 'entity': 'ReadingBatch', 'app': 'Billing', 'object_fields': ['token', 'status__name', 'id']},
        {'model': Invoice, 'fields': ['token', 'id', 'exploitation__token', 'company__alias', 'contract__token', 'number'], 'entity': 'Invoice', 'app': 'Billing', 'object_fields': ['token', 'status__name', 'type_final', 'title_final']},
        {'model': Order, 'fields': ['token', 'id', 'contract__token', 'supply_point__token'], 'entity': 'Order', 'app': 'Order', 'object_fields': ['token', 'status__name', 'type__name']},
        {'model': Operator, 'fields': ['token', 'id', 'surname', 'name'], 'entity': 'Operator', 'app': 'Order', 'object_fields': ['token', 'name', 'surname']},
    ]

    def check_all_words_present(text, words):
        text_lower = str(text).lower()
        return all(word in text_lower for word in words)

    def get_nested_value(obj, field_path):
        parts = field_path.split('__')
        current = obj
        for part in parts:
            if current is None:
                return ''
            current = getattr(current, part, None)
        return str(current) if current is not None else ''
    
    def add_results(queryset, fields, entity, app, person_fields=None):

        nonlocal total_count
        for item in queryset:
            matched = False
            for field in fields:
                if field != 'id':
                    field_value = str(item.get(field, ''))
                    if check_all_words_present(field_value, query_words):
                        if person_fields and any(field.startswith(f"{prefix}__{name_field}") for prefix, name_fields in person_fields for name_field in name_fields):
                            prefix = next(prefix for prefix, name_fields in person_fields if any(field.startswith(f"{prefix}__{name_field}") for name_field in name_fields))
                            full_name = f"{item.get(f'{prefix}__name', '')} {item.get(f'{prefix}__surname', '')}".strip()
                            model_instance = model_info['model'].objects.get(id=item['id'])
                            results.append({
                                "search": query,
                                "found": full_name,
                                "entity": entity,
                                "app": app,
                                "found_field": field,
                                "item_id": item['id'],
                                "object_data": {field: get_nested_value(model_instance, field) for field in model_info['object_fields']}
                            })
                        else:
                            model_instance = model_info['model'].objects.get(id=item['id'])
                            results.append({
                                "search": query,
                                "found": item[field],
                                "entity": entity,
                                "app": app,
                                "found_field": field,
                                "item_id": item['id'],
                                "object_data": {field: get_nested_value(model_instance, field) for field in model_info['object_fields']}
                            })
                        total_count += 1
                        matched = True
                        break
            
            if person_fields and not matched:
                for prefix, name_fields in person_fields:
                    full_name = ' '.join(str(item.get(f"{prefix}__{field}", '')) for field in name_fields)
                    if check_all_words_present(full_name, query_words):
                        model_instance = model_info['model'].objects.get(id=item['id'])
                        results.append({
                            "search": query,
                            "found": full_name,
                            "entity": entity,
                            "app": app,
                            "found_field": f"{prefix}_full_name",
                            "item_id": item['id'],
                            "object_data": {field: get_nested_value(model_instance, field) for field in model_info['object_fields']}
                        })
                        total_count += 1
                        break

    if query:
        for model_info in models:
            model = model_info['model']
            fields = model_info['fields']
            entity = model_info['entity']
            app = model_info['app']
            person_fields = model_info.get('person_fields')

            if entity_filter and entity_filter != entity:
                continue
            
            if model in [Person, Operator]:
                name_filter = Q()
                for word in query_words:
                    name_filter &= (
                        Q(name__icontains=word) |
                        Q(surname__icontains=word) |
                        Q(token__icontains=word)
                    )
                
                queryset = model.objects.filter(name_filter).annotate(
                    full_name=Concat('name', Value(' '), 'surname', output_field=CharField())
                ).values('token', 'full_name', 'id', *model_info['object_fields'])
                
                if not entity_filter:
                    queryset = queryset.all()  # Remove the limit since we'll paginate later
                
                for item in queryset:
                    full_name = item['full_name'].lower()
                    token = item['token'].lower()
                    if check_all_words_present(full_name, query_words) or check_all_words_present(token, query_words):
                        results.append({
                            "search": query,
                            "found": item['full_name'] if check_all_words_present(full_name, query_words) else item['token'],
                            "entity": entity,
                            "app": app,
                            "found_field": "full_name" if check_all_words_present(full_name, query_words) else "token",
                            "object_data": {field: get_nested_value(model.objects.get(id=item['id']), field) for field in model_info['object_fields']},
                            "item_id": item['id'],
                        })
                        total_count += 1
                        
            elif model in [Contract, ContractRequest]:
                query_filter = Q()
                for word in query_words:
                    word_filter = Q()
                    for field in fields:
                        if not any(field.startswith(f"{prefix}__{name_field}") for prefix, name_fields in person_fields for name_field in name_fields):
                            word_filter |= Q(**{f"{field}__icontains": word})
                    
                    for prefix, name_fields in person_fields:
                        person_filter = Q()
                        for field in name_fields:
                            person_filter |= Q(**{f"{prefix}__{field}__icontains": word})
                        word_filter |= person_filter
                    
                    query_filter &= word_filter

                annotations = {}
                for prefix, name_fields in person_fields:
                    annotations[f"{prefix}_full_name"] = Concat(
                        f"{prefix}__name", Value(' '), f"{prefix}__surname",
                        output_field=CharField()
                    )

                queryset = model.objects.filter(query_filter).annotate(**annotations)
                values_fields = fields + [f"{prefix}_full_name" for prefix, _ in person_fields] + model_info['object_fields']
                queryset = queryset.values('id', *values_fields)

                if not entity_filter:
                    queryset = queryset.all()  # Remove the limit since we'll paginate later

                add_results(queryset, fields, entity, app, person_fields)
                
            elif model is SupplyPoint:
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
                
                queryset = model.objects.filter(address_filter).annotate(
                    address_complete=Concat(
                        'address__city__name', Value(' - '),
                        'address__street_number__street__name',
                        Case(
                            When(address__street_number__number__isnull=False, then=Value(' - ')),
                            default=Value(''),
                            output_field=CharField()
                        ),
                        Case(
                            When(address__street_number__number__isnull=False, then=Cast(F('address__street_number__number'), CharField())),
                            default=Value(''),
                            output_field=CharField()
                        ),
                        Case(
                            When(address__floor__isnull=False, then=Value(' - ')),
                            default=Value(''),
                            output_field=CharField()
                        ),
                        Case(
                            When(address__floor__isnull=False, then=F('address__floor')),
                            default=Value(''),
                            output_field=CharField()
                        ),
                        Case(
                            When(address__door__isnull=False, then=Value(' - ')),
                            default=Value(''),
                            output_field=CharField()
                        ),
                        Case(
                            When(address__door__isnull=False, then=F('address__door')),
                            default=Value(''),
                            output_field=CharField()
                        ),
                        output_field=CharField()
                    )
                ).values('token', 'address_complete', 'name', 'id', *model_info['object_fields'])
                
                if not entity_filter:
                    queryset = queryset.all()  # Remove the limit since we'll paginate later
                    
                add_results(queryset, ['address_complete', 'token', 'name'], entity, app)
                
            else:
                query_filter = Q()
                for word in query_words:
                    word_filter = Q()
                    for field in fields:
                        word_filter |= Q(**{f"{field}__icontains": word})
                    query_filter &= word_filter

                queryset = model.objects.filter(query_filter).values(*fields, *model_info['object_fields'])
                if not entity_filter:
                    queryset = queryset.all()  # Remove the limit since we'll paginate later
                add_results(queryset, fields, entity, app)

    # Paginate results
    paginator = Paginator(results, page_size)
    paginated_results = paginator.get_page(page)

    return JsonResponse({
        "query": query,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "has_next": paginated_results.has_next(),
        "has_previous": paginated_results.has_previous(),
        "results": list(paginated_results)
    })

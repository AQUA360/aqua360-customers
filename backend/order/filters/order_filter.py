from django_filters import rest_framework as filters
from django.db.models import Q, Count
from urllib.parse import unquote
from order.models import Order

class OrderFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    operators = filters.CharFilter(method='filter_operators')
    connection = filters.CharFilter(method='filter_connection')
    connection_request = filters.CharFilter(field_name='connection_request__id', lookup_expr='exact')
    claim_request = filters.CharFilter(field_name='claim_request__id', lookup_expr='exact')
    type_token = filters.CharFilter(field_name='type__token', lookup_expr='exact')
    incident = filters.CharFilter(field_name='incident__id', lookup_expr='exact')
    contract = filters.CharFilter(method='filter_contract')
    contract_request = filters.CharFilter(field_name='contract_request__id', lookup_expr='exact')
    contract_termination_request = filters.CharFilter(method='filter_contract_termination_request')
    
    search_all_address = filters.CharFilter(method='filter_all_address')
    search_by_address = filters.CharFilter(method='filter_address')
    connection_request = filters.CharFilter(field_name='connection_request__id', lookup_expr='exact')
    type = filters.CharFilter(method='filter_type')
    exclude = filters.NumberFilter(method='filter_exclude', label='Exclude order with certain id')
    
    exploitation = filters.NumberFilter(method='filter_exploitation')
    related_contract_token = filters.CharFilter(field_name='related_contract_token', lookup_expr='icontains')
    contract_id = filters.NumberFilter(method='filter_contract')
    created_by = filters.CharFilter(method='filter_created_by')
    
    city = filters.CharFilter(method='filter_city')
    
    class Meta:
        model = Order
        fields = [
            'search','status', 'type', 
            'operators', 'connection', 'connection_request', 
            'claim_request', 'type_token', 'contract', 'contract_id',
            'contract_request', 'contract_termination_request',
            'connection_request', 'incident', 'exploitation',
            'search_all_address', 'search_by_address', 'related_contract_token', 'created_by', 'city']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(operators__name__icontains=value) |
            Q(type__name__icontains=value) |
            Q(related_contract_token__icontains=value)
        ).distinct()
    def filter_status(self, queryset, name, value):
        print(value)
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_connection(self, queryset, name, value):
        return queryset.filter(connection__id=value)

    def filter_contract(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(contract__id=value) |
            Q(supply_point__contracts__id=value) |
            Q(supply_point__default_contracts__id=value)
        ).distinct()
    
    def filter_contract_termination_request(self, queryset, name, value):
        return queryset.filter(contract_termination_request__id=value)
    
    def filter_type(self, queryset, name, value):
        print(value)
        if value:
            type_values = value.split(',')
            return queryset.filter(type__id__in=type_values)
        return queryset
    
    def filter_operators(self, queryset, name, value):
        print(value)
        if value:
            operator_values = value.split(',')
            return queryset.filter(operators__id__in=operator_values)
        return queryset

    def filter_created_by(self, queryset, name, value):
        if value:
            created_by_values = value.split(',')
            return queryset.filter(created_by__id__in=created_by_values)
        return queryset


    def filter_property(self, queryset, name, value):
        if value:
            return queryset.filter(property__id=value)
        return queryset
    
    EXPLOITATION_PATHS = (
        'contract__supply_point_default__connection__exploitation',
        'contract_request__supply_point_default__connection__exploitation',
        'supply_point__connection__exploitation',
        'connection__exploitation',
        'connection_request__exploitation',
        'address__city__exploitations',
        'claim_request__payments__contract__supply_point_default__connection__exploitation',
    )

    def filter_exploitation(self, queryset, name, value):
        if value:
            in_exploitation = Q()
            has_exploitation = Q()
            for path in self.EXPLOITATION_PATHS:
                in_exploitation |= Q(**{f'{path}__id': value})
                has_exploitation |= Q(**{f'{path}__isnull': False})
            # Orders with no exploitation linked through any path are shown too.
            linked_ids = Order.objects.filter(has_exploitation).values('id')
            return queryset.filter(
                in_exploitation | ~Q(id__in=linked_ids)
            ).distinct()
        return queryset

    def filter_all_address(self, queryset, name, value):
        if not value:
            return queryset

        value = unquote(value)
        terms = [t.strip() for t in value.split() if t.strip()]
        if not terms:
            return queryset

        for term in terms:
            queryset = queryset.filter(
                Q(address__address_search__icontains=term) |
                Q(contract__supply_point_default__address__address_search__icontains=term) |
                Q(contract_request__supply_point_default__address__address_search__icontains=term) |
                Q(supply_point__address__address_search__icontains=term)
            ).distinct()

        return queryset

    def filter_address(self, queryset, name, value):
        if not value:
            return queryset

        value = unquote(value)
        parts = value.split("%")
        parts += [""] * (9 - len(parts))
        (
            street_name,
            number,
            number_suffix,
            number_end,
            number_end_suffix,
            floor,
            door,
            stair,
            building,
        ) = [p.strip() for p in parts[:9]]

        addr_filter = Q()

        if street_name:
            addr_filter &= (
                Q(address__street__name__icontains=street_name) |
                Q(contract__supply_point_default__address__street__name__icontains=street_name) |
                Q(contract_request__supply_point_default__address__street__name__icontains=street_name) |
                Q(supply_point__address__street__name__icontains=street_name)
            )

        if number:
            try:
                num_int = int(number)
                addr_filter &= (
                    Q(address__street_number__number=num_int) |
                    Q(contract__supply_point_default__address__street_number__number=num_int) |
                    Q(contract_request__supply_point_default__address__street_number__number=num_int) |
                    Q(supply_point__address__street_number__number=num_int)
                )
            except ValueError:
                addr_filter &= (
                    Q(address__street_number__token__iexact=number) |
                    Q(contract__supply_point_default__address__street_number__token__iexact=number) |
                    Q(contract_request__supply_point_default__address__street_number__token__iexact=number) |
                    Q(supply_point__address__street_number__token__iexact=number)
                )

        if number_suffix:
            addr_filter &= (
                Q(address__street_number__number_suffix__icontains=number_suffix) |
                Q(contract__supply_point_default__address__street_number__number_suffix__icontains=number_suffix) |
                Q(contract_request__supply_point_default__address__street_number__number_suffix__icontains=number_suffix) |
                Q(supply_point__address__street_number__number_suffix__icontains=number_suffix)
            )

        if number_end:
            try:
                num_end_int = int(number_end)
                addr_filter &= (
                    Q(address__street_number__number_end=num_end_int) |
                    Q(contract__supply_point_default__address__street_number__number_end=num_end_int) |
                    Q(contract_request__supply_point_default__address__street_number__number_end=num_end_int) |
                    Q(supply_point__address__street_number__number_end=num_end_int)
                )
            except ValueError:
                pass

        if number_end_suffix:
            addr_filter &= (
                Q(address__street_number__number_end_suffix__icontains=number_end_suffix) |
                Q(contract__supply_point_default__address__street_number__number_end_suffix__icontains=number_end_suffix) |
                Q(contract_request__supply_point_default__address__street_number__number_end_suffix__icontains=number_end_suffix) |
                Q(supply_point__address__street_number__number_end_suffix__icontains=number_end_suffix)
            )

        if floor:
            addr_filter &= (
                Q(address__floor__iexact=floor) |
                Q(contract__supply_point_default__address__floor__iexact=floor) |
                Q(contract_request__supply_point_default__address__floor__iexact=floor) |
                Q(supply_point__address__floor__iexact=floor)
            )
        if door:
            addr_filter &= (
                Q(address__door__iexact=door) |
                Q(contract__supply_point_default__address__door__iexact=door) |
                Q(contract_request__supply_point_default__address__door__iexact=door) |
                Q(supply_point__address__door__iexact=door)
            )
        if stair:
            addr_filter &= (
                Q(address__stair__icontains=stair) |
                Q(contract__supply_point_default__address__stair__icontains=stair) |
                Q(contract_request__supply_point_default__address__stair__icontains=stair) |
                Q(supply_point__address__stair__icontains=stair)
            )
        if building:
            addr_filter &= (
                Q(address__building__icontains=building) |
                Q(contract__supply_point_default__address__building__icontains=building) |
                Q(contract_request__supply_point_default__address__building__icontains=building) |
                Q(supply_point__address__building__icontains=building)
            )

        if not addr_filter:
            return queryset

        return queryset.filter(addr_filter).distinct()

    def filter_city(self, queryset, name, value):
        if value:
            city_ids = value.split(',')
            return queryset.filter(
                Q(address__city__id__in=city_ids) |
                Q(contract__supply_point_default__address__city__id__in=city_ids) |
                Q(contract_request__supply_point_default__address__city__id__in=city_ids) |
                Q(supply_point__address__city__id__in=city_ids) |
                Q(connection__address_city__id__in=city_ids) |
                Q(connection_request__address_city__id__in=city_ids)
            ).distinct()
        return queryset
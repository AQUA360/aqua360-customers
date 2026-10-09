from django_filters import rest_framework as filters
from django.db.models import Q
from service.models import Connection
from functools import reduce
from operator import and_

class ConnectionFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    search_by_address = filters.CharFilter(method='filter_address')
    exploitation = filters.NumberFilter(field_name='exploitation__id', lookup_expr='exact')
    status = filters.BaseInFilter(field_name='status', lookup_expr='in')
    exploitation = filters.NumberFilter(method='filter_exploitation', label='Assigned to a certain exploitation')
    
    type = filters.CharFilter(method='filter_type')
    use_type = filters.CharFilter(method='filter_use_type')
    material = filters.CharFilter(method='filter_material')
    valve_type = filters.CharFilter(method='filter_valve_type')
    
    class Meta:
        model = Connection
        fields = ['search', 'exploitation','status', 'type', 'use_type', 'material', 'valve_type']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            query_components = [
                Q(token__icontains=term) |
                Q(address_street__name__icontains=term) |
                Q(address_street__name_2__icontains=term) |
                Q(address_city__name__icontains=term) |
                Q(dma__name__icontains=term) |
                Q(address_extra__icontains=term)
            ]
            if term.isdigit():
                # Convert string to int for exact match on IntegerField
                term_int = int(term)
                query_components.extend([
                    Q(address_street_number__number=term_int),
                    Q(address_street_number__number_end=term_int)
                ])
            else:
                # allow matching suffix terms like BIS
                query_components.append(Q(address_street_number__number_suffix__icontains=term))
            
            term_query = reduce(lambda x, y: x | y, query_components)
            term_queries.append(term_query)
        
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query).distinct()

    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(exploitation__id=value)
        return queryset
    
    def filter_type(self, queryset, name, value):
        if value:
            type_values = value.split(',')
            return queryset.filter(type__id__in=type_values)
        return queryset
    
    def filter_use_type(self, queryset, name, value):
        if value:
            use_type_values = value.split(',')
            return queryset.filter(use_type__id__in=use_type_values)
        return queryset
    
    def filter_material(self, queryset, name, value):
        if value:
            material_values = value.split(',')
            return queryset.filter(material__id__in=material_values)
        return queryset
    
    def filter_valve_type(self, queryset, name, value):
        if value:
            valve_type_values = value.split(',')
            return queryset.filter(valve_type__id__in=valve_type_values)
        return queryset

    def filter_address(self, queryset, name, value):
        if not value:
            return queryset

        # Expected format:
        # street_name%number%number_suffix%number_end%number_end_suffix%floor%door%stair%building
        parts = (value or "").split("%")
        # Pad to 9 elements to avoid IndexError
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

        # Street name (Connection uses address_street)
        if street_name:
            addr_filter &= Q(
                address_street__name__icontains=street_name
            )

        # Street number and related fields (on StreetNumber)
        if number:
            try:
                addr_filter &= Q(
                    address_street_number__number=int(number)
                )
            except ValueError:
                addr_filter &= Q(
                    address_street_number__token__iexact=number
                )

        if number_suffix:
            addr_filter &= Q(
                address_street_number__number_suffix__icontains=number_suffix
            )

        if number_end:
            try:
                addr_filter &= Q(
                    address_street_number__number_end=int(
                        number_end
                    )
                )
            except ValueError:
                pass

        if number_end_suffix:
            addr_filter &= Q(
                address_street_number__number_end_suffix__icontains=number_end_suffix
            )

        # Connection does not have floor/door/stair/building fields, so we ignore those

        if not addr_filter:
            return queryset

        return queryset.filter(addr_filter).distinct()
from django_filters import rest_framework as filters
from service.models import Cluster
from django.db.models import Q
from functools import reduce
from operator import and_

class ClusterFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    search_by_address = filters.CharFilter(method='filter_address')
    connection = filters.NumberFilter(field_name='connection__id', lookup_expr='exact')
    status = filters.BaseInFilter(field_name='status', lookup_expr='in')
    connection = filters.NumberFilter(method='filter_connection', label='Assigned to a certain connection')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    
    class Meta:
        model = Cluster
        fields = ['connection', 'status', 'exploitation']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            # Base query components (text fields only)
            query_components = [
                Q(token=term),
                Q(address_street__name__icontains=term),
                Q(address_street_number__number_suffix__icontains=term)
            ]
            
            # Add number-related queries only if term is a number
            if term.isdigit():
                # Convert string to int for exact match on IntegerField
                term_int = int(term)
                query_components.extend([
                    Q(address_street_number__number=term_int),
                    Q(address_street_number__number_end=term_int)
                ])
            
            term_query = reduce(lambda x, y: x | y, query_components)
            term_queries.append(term_query)
        
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)

    def filter_connection(self, queryset, name, value):
        if value:
            return queryset.filter(connection__id=value)
        return queryset
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(connection__exploitation__id=value) |
                Q(connection__exploitation__isnull=True)
            ).distinct()
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

        # Street name
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

        # Cluster does not have floor/door/stair/building fields, so we ignore those

        if not addr_filter:
            return queryset

        return queryset.filter(addr_filter).distinct()
from django_filters import rest_framework as filters
from django.db.models import Q
from functools import reduce
from operator import and_
from ..models import Communication

class CommunicationFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    types = filters.CharFilter(method='filter_type')
    process = filters.CharFilter(field_name='process__id', lookup_expr='exact')
    person = filters.CharFilter(method='filter_person')
    contract = filters.CharFilter(method='filter_contract')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    is_individual = filters.BooleanFilter(method='filter_is_individual')
    start_date = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    
    class Meta:
        model = Communication
        fields = ['search', 'process', 'status', 'person', 'is_individual', 'types', 'contract', 'exploitation', 'start_date', 'end_date']
   
    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        
        # Split search terms (e.g., "John Doe" -> ["John", "Doe"])
        search_terms = value.split()
        term_queries = []
        
        for term in search_terms:
            # Each term must match in at least one of these fields
            term_query = (
                Q(token__icontains=term) |
                Q(process__token__icontains=term) |
                Q(person__name__icontains=term) |
                Q(person__surname__icontains=term) |
                Q(person__token__icontains=term) |
                Q(status__name__icontains=term) |
                Q(used_email__icontains=term) |
                Q(used_phones__icontains=term)
            )
            term_queries.append(term_query)
        
        # All terms must match (AND logic) - so "John Doe" requires both "John" and "Doe" to match
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)
    
    def filter_person(self, queryset, name, value):
        if value:
            person_values = value.split(',')
            return queryset.filter(person__id__in=person_values)
        return queryset
    
    def filter_contract(self, queryset, name, value):
        if value:
            contract_values = value.split(',')
            return queryset.filter(Q(contracts__id__in=contract_values) | Q(contracts__isnull=True))
        return queryset
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset

    def filter_type(self, queryset, name, value):
        if value:
            type_values = value.split(',')
            return queryset.filter(types__id__in=type_values)
        return queryset
    
    def filter_is_individual(self, queryset, name, value):
        if value:
            if value:
                return queryset.filter(process__isnull=True)
            elif value == 'null':
                return queryset
            else:
                return queryset.filter(process__isnull=False)
        return queryset
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(contracts__supply_point_default__connection__exploitation__id=value) |
                Q(contracts__isnull=True) |
                Q(invoices__exploitation__id=value) 
            ).distinct()
        return queryset
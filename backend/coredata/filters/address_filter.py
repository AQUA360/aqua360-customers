from django_filters import rest_framework as filters
from coredata.models import Address, PersonAddress
from django.db.models import Q
from functools import reduce
from operator import and_

class AddressFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Address
        fields = ['search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
            
        search_terms = value.split()
        
        term_queries = []
        for term in search_terms:
            term_query = (
                Q(floor__icontains=term) |
                Q(door__icontains=term) |
                Q(stair__icontains=term) |
                Q(building__icontains=term) | 
                Q(street__name__icontains=term) |
                Q(street__name_2__icontains=term) | 
                Q(street__type__name__icontains=term) |
                Q(street_number__number_type__type__icontains=term) | 
                Q(street_number__number__icontains=term) | 
                Q(street_number__number_end__icontains=term) |
                Q(street_number__number_suffix__icontains=term) |
                Q(street_number__number_end_suffix__icontains=term)
            )
            term_queries.append(term_query)
        
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)

class PersonAddressFilter(filters.FilterSet):
    person = filters.CharFilter(field_name='person__id', lookup_expr='exact')

    class Meta:
        model = PersonAddress
        fields = ['person']
    
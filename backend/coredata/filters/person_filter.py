from django_filters import rest_framework as filters
from coredata.models import Person
from unidecode import unidecode
from django.db.models import Q
from functools import reduce
from operator import and_

class PersonFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    is_juridic = filters.BooleanFilter(field_name='is_juridic')

    class Meta:
        model = Person
        fields = ['search', 'is_juridic']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        
        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            term_query = (
                Q(token__icontains=term) |
                Q(name__icontains=term) |
                Q(surname__icontains=term) 
            )
            term_queries.append(term_query)
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)
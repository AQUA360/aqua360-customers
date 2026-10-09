from django_filters import rest_framework as filters
from django.db.models import Q
from functools import reduce
from operator import and_
from ..models import AccountingConcept

class AccountingConceptFilter(filters.FilterSet):
    types = filters.CharFilter(method='filter_type')
    category = filters.CharFilter(field_name='category', lookup_expr='exact')
    add_taxes = filters.BooleanFilter(field_name='type__add_taxes', lookup_expr='exact')
    add_subtotals = filters.BooleanFilter(field_name='type__add_subtotals', lookup_expr='exact')
    
    class Meta:
        model = AccountingConcept
        fields = ['types', 'category', 'add_taxes', 'add_subtotals']

    def filter_type(self, queryset, name, value):
        if value:
            type_values = value.split(',')
            return queryset.filter(type__id__in=type_values)
        return queryset
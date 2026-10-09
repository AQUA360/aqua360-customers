from django_filters import rest_framework as filters
from django.db.models import Q
from functools import reduce
from operator import and_
from ..models import AccountingPricing

class AccountingPricingFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    types = filters.CharFilter(method='filter_type')
    exploitation = filters.CharFilter(field_name='exploitation__id', lookup_expr='exact')
    category = filters.CharFilter(field_name='accounting_concept__category', lookup_expr='exact')
    add_taxes = filters.BooleanFilter(field_name='accounting_concept__type__add_taxes', lookup_expr='exact')
    add_subtotals = filters.BooleanFilter(field_name='accounting_concept__type__add_subtotals', lookup_expr='exact')
    
    class Meta:
        model = AccountingPricing
        fields = ['search', 'status', 'types', 'exploitation', 'category', 'add_taxes', 'add_subtotals']
   
    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        
        search_terms = value.split()
        term_queries = []
        
        for term in search_terms:
            term_query = (
                Q(token__icontains=term) |
                Q(name__icontains=term) |
                Q(accounting_concept__name__icontains=term) |
                Q(accounting_concept__token__icontains=term) |
                Q(products__name__icontains=term) |
                Q(price_rates__name__icontains=term) |
                Q(line_item_types__name__icontains=term) |
                Q(payment_types__name__icontains=term) |
                Q(payment_types__token__icontains=term) |
                Q(company__name__icontains=term) |
                Q(company__alias__icontains=term) |
                Q(company__vat__icontains=term)
            )
            term_queries.append(term_query)
        
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset

    def filter_type(self, queryset, name, value):
        if value:
            type_values = value.split(',')
            return queryset.filter(accounting_concepts__type__id__in=type_values)
        return queryset
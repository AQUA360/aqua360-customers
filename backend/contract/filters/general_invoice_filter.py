from django_filters import rest_framework as filters
from contract.models import GeneralInvoice
from django.db.models import Q

class GeneralInvoiceFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    contract = filters.CharFilter(method='filter_contract')
    
    class Meta:
        model = GeneralInvoice
        fields = ['search', 'contract']
   
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(contracts__token__icontains=value) 
        )
    
    def filter_contract(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(contracts__id__in=value_ids)
        return queryset
  
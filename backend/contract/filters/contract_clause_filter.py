from django_filters import rest_framework as filters
from django.db.models import Q
from contract.models import ContractClause

class ContractClauseFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    contract_request = filters.CharFilter(field_name='contract_request__id', lookup_expr='exact')
    contract = filters.CharFilter(field_name='contract__id', lookup_expr='exact')
    
    class Meta:
        model = ContractClause
        fields = ['search', 'contract_request']
        
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) 
        )
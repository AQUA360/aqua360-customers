from django_filters import rest_framework as filters
from ..models import Variable

class VariableFilter(filters.FilterSet):
    contract_request = filters.CharFilter(field_name='contract_request__id', lookup_expr='exact')
    contract = filters.CharFilter(field_name='contract__id', lookup_expr='exact')

    class Meta:
        model = Variable
        fields = ['contract_request', 'contract']
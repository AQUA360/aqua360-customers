from django_filters import rest_framework as filters
from ..models import ContractObservation

class ContractObservationFilter(filters.FilterSet):
    contract_id = filters.CharFilter(field_name='contract__id', lookup_expr='exact')

    class Meta:
        model = ContractObservation
        fields = ['contract']
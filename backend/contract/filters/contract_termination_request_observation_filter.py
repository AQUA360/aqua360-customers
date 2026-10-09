from django_filters import rest_framework as filters
from ..models import ContractTerminationRequestObservation

class ContractTerminationRequestObservationFilter(filters.FilterSet):
    contract_termination_id = filters.CharFilter(field_name='contract_termination__id', lookup_expr='exact')

    class Meta:
        model = ContractTerminationRequestObservation
        fields = ['contract_termination', 'status']
    
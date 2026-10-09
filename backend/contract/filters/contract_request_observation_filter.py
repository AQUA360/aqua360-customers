from django_filters import rest_framework as filters
from ..models import ContractRequestObservation

class ContractRequestObservationFilter(filters.FilterSet):
    contract_request_id = filters.CharFilter(field_name='contract_request__id', lookup_expr='exact')

    class Meta:
        model = ContractRequestObservation
        fields = ['contract_request']
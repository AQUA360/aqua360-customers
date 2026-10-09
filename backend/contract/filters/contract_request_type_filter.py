from django_filters import rest_framework as filters
from ..models import ContractRequestType

class ContractRequestTypeFilter(filters.FilterSet):
    exploitation = filters.CharFilter(field_name='exploitation__id', lookup_expr='exact')

    class Meta:
        model = ContractRequestType
        fields = ['exploitation']
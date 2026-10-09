from django_filters import rest_framework as filters
from ..models import ContractRequestDocumentation

class ContractRequestDocumentationFilter(filters.FilterSet):
    contract_request = filters.CharFilter(field_name='contract_request_id', lookup_expr='exact')
    
    class Meta:
        model = ContractRequestDocumentation
        fields = ['contract_request']
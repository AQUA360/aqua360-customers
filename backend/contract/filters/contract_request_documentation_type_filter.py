from django_filters import rest_framework as filters
from ..models import ContractRequestDocumentationType

class ContractRequestDocumentationTypeFilter(filters.FilterSet):
    contract_request_type_id = filters.CharFilter(field_name='contract_request_type_id', lookup_expr='exact')
    
    class Meta:
        model = ContractRequestDocumentationType
        fields = ['contract_request_type']
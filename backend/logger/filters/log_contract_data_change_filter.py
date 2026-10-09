from django_filters import rest_framework as filters
from contract.models import ContractDataChange

class LogContractDataChangeFilter(filters.FilterSet):
    object = filters.NumberFilter(field_name='contract__id')
    
    class Meta:
        model = ContractDataChange
        fields = ["object"]

from django_filters import rest_framework as filters
from service.models import CompanyConfig

class CompanyConfigFilter(filters.FilterSet):
    
    company = filters.CharFilter(field_name='company_configs__id', lookup_expr='exact')
    
    class Meta:
        model = CompanyConfig
        fields = ['company']

    

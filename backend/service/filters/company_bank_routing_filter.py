from django_filters import rest_framework as filters

from service.models import CompanyBankRouting


class CompanyBankRoutingFilter(filters.FilterSet):

    company = filters.CharFilter(field_name='company__id', lookup_expr='exact')
    company_bank = filters.CharFilter(field_name='company_bank__id', lookup_expr='exact')
    bank = filters.CharFilter(field_name='bank__id', lookup_expr='exact')
    match_type = filters.CharFilter(field_name='match_type', lookup_expr='exact')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = CompanyBankRouting
        fields = ['company', 'company_bank', 'bank', 'match_type', 'is_active']

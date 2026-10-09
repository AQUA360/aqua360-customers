from django_filters import rest_framework as filters
from service.models import CompanyBank

class CompanyBankFilter(filters.FilterSet):
    
    company = filters.CharFilter(field_name='company__id', lookup_expr='exact')
    # El selector de bancs de la remesa SEPA llista els comptes de totes les
    # empreses emissores (cada banc genera el seu fitxer), pero nomes els que
    # estan actius.
    is_sepa = filters.BooleanFilter(field_name='is_sepa')
    is_active = filters.BooleanFilter(field_name='is_active')
    
    class Meta:
        model = CompanyBank
        fields = ['company']

    

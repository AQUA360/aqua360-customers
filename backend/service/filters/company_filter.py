from django_filters import rest_framework as filters
from unidecode import unidecode
from django.db.models import Q

from service.models import Company

class CompanyFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')

    class Meta:
        model = Company
        fields = ['search']

    def filter_search(self, queryset, name, value):
        value = unidecode(value) 
        return queryset.filter(
            Q(vat__icontains=value) | 
            Q(name__icontains=value) | 
            Q(alias__icontains=value)
        )
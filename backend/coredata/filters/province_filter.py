from django_filters import rest_framework as filters
from coredata.models import Province
from django.db.models import Q

class ProvinceFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Province
        fields = ['country']
from django_filters import rest_framework as filters
from coredata.models import StreetNumber
from django.db.models import Q

class StreetNumberFilter(filters.FilterSet):
    street = filters.NumberFilter(field_name='street__id', lookup_expr='exact')
    
    class Meta:
        model = StreetNumber
        fields = ['street']

    
    
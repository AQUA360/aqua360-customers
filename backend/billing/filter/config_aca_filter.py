from django_filters import rest_framework as filters
from ..models import ConfigAca
from django.db.models import Q


class ConfigAcaFilter(filters.FilterSet):
    exploitation = filters.NumberFilter(field_name='exploitation__id', lookup_expr='exact')
    
    class Meta:
        model = ConfigAca
        fields = ['exploitation']

   
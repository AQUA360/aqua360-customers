from django_filters import rest_framework as filters
from ..models import History

class SearchHistoryFilter(filters.FilterSet):
    user = filters.NumberFilter(field_name='user__id', lookup_expr='exact')
    
    class Meta:
        model = History
        fields = ['user']


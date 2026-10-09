from django_filters import rest_framework as filters
from django.db.models import Q
from ..models import CommunicationProcess

class CommunicationProcessFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    types = filters.CharFilter(method='filter_type')
    supply_cut = filters.NumberFilter(field_name='supply_cuts__id', lookup_expr='exact')
    
    class Meta:
        model = CommunicationProcess
        fields = ['search', 'status', 'types', 'supply_cut']
   
    def filter_search(self, queryset, name, value):
            
        return queryset.filter(
            Q(token__icontains=value) |
            Q(description__icontains=value) |
            Q(status__name__icontains=value) 
        ).distinct()
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_type(self, queryset, name, value):
        if value:
            type_values = value.split(',')
            return queryset.filter(used_types__id__in=type_values)
        return queryset

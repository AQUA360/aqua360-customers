from django_filters import rest_framework as filters
from django.db.models import Q
from ..models import CANCELLED_STATUS_TOKEN, CommunicationProcess

class CommunicationProcessFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    exclude_cancelled = filters.BooleanFilter(method='filter_exclude_cancelled')
    types = filters.CharFilter(method='filter_type')
    supply_cut = filters.NumberFilter(field_name='supply_cuts__id', lookup_expr='exact')
    
    class Meta:
        model = CommunicationProcess
        fields = ['search', 'status', 'exclude_cancelled', 'types', 'supply_cut']
   
    def filter_search(self, queryset, name, value):
            
        return queryset.filter(
            Q(token__icontains=value) |
            Q(description__icontains=value) |
            Q(status__name__icontains=value) 
        ).distinct()
    
    def filter_exclude_cancelled(self, queryset, name, value):
        # Un filtre d'estat explícit mana: si l'usuari tria estats concrets
        # (inclòs el cancel·lat), no amaguem res.
        if value and not self.data.get('status'):
            return queryset.exclude(status__token=CANCELLED_STATUS_TOKEN)
        return queryset

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

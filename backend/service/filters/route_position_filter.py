from django_filters import rest_framework as filters
from service.models import Cluster, ClusterNozzle, Route, SupplyPoint, RoutePosition, Meter
from django.db.models import Q

class RoutePositionFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    route = filters.NumberFilter(field_name='route__id', lookup_expr='exact')
    
    class Meta:
        model = RoutePosition
        fields = ['search','route']


    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) | 
            Q(name__icontains=value) |
            Q(properties__name__icontains=value)
        ).distinct()

from django_filters import rest_framework as filters
from service.models import Cluster, ClusterNozzle, Route, SupplyPoint, RoutePosition, Meter
from django.db.models import Q

class RouteFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    class Meta:
        model = Route
        fields = ['search', 'exploitation']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) | Q(name__icontains=value)
        )
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(positions__properties__supply_points__connection__exploitation__id=value) |
                Q(positions__properties__supply_points__connection__exploitation__isnull=True)
            ).distinct()
        return queryset
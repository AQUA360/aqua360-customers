from django_filters import rest_framework as filters
from service.models import Cluster, ClusterNozzle, Route, SupplyPoint, RoutePosition, Meter
from django.db.models import Q
from service.utils.route_scope import effective_route_ids

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
            # Rutes amb algun punt (de ruta efectiva) de l'explotació o sense
            # explotació, o rutes sense cap punt
            exploitation_supply_points = SupplyPoint.objects.filter(
                Q(connection__exploitation__id=value) | Q(connection__exploitation__isnull=True)
            )
            return queryset.filter(
                Q(id__in=effective_route_ids(exploitation_supply_points)) |
                ~Q(id__in=effective_route_ids(SupplyPoint.objects.all()))
            )
        return queryset
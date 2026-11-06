from django_filters import rest_framework as filters
from service.models import Route, RouteZone, SupplyPoint
from service.utils.route_scope import effective_route_ids
from django.db.models import Q

class RouteZoneFilter(filters.FilterSet):
    
    exploitation = filters.CharFilter(method='filter_exploitation')
    
    class Meta:
        model = RouteZone
        fields = ['exploitation']

    def filter_exploitation(self, queryset, name, value):
        if value:
            # Zones amb alguna ruta que té punts (de ruta efectiva) de l'explotació
            # o sense explotació, amb alguna ruta sense punts o sense rutes
            exploitation_supply_points = SupplyPoint.objects.filter(
                Q(connection__exploitation__id=value) | Q(connection__exploitation__isnull=True)
            )
            routes = Route.objects.filter(
                Q(id__in=effective_route_ids(exploitation_supply_points)) |
                ~Q(id__in=effective_route_ids(SupplyPoint.objects.all()))
            )
            return queryset.filter(
                Q(routes__in=routes) | Q(routes__isnull=True)
            ).distinct()
        return queryset
    
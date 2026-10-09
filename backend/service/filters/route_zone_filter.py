from django_filters import rest_framework as filters
from service.models import RouteZone
from django.db.models import Q

class RouteZoneFilter(filters.FilterSet):
    
    exploitation = filters.CharFilter(method='filter_exploitation')
    
    class Meta:
        model = RouteZone
        fields = ['exploitation']

    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(routes__positions__properties__supply_points__connection__exploitation__id=value)|
                Q(routes__positions__properties__supply_points__connection__exploitation__isnull=True)
            ).distinct()
        return queryset
    
from django_filters import rest_framework as filters
from coredata.models import City
from django.db.models import Q

class CityFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    has_streets = filters.BooleanFilter(method='filter_has_streets')
    
    class Meta:
        model = City
        fields = ['search', 'province', 'has_streets']

    def filter_province(self, queryset, name, value):
        return queryset.filter(province=value)

    def filter_has_streets(self, queryset, name, value):
        if value:
            return queryset.filter(street__isnull=False).distinct()
        return queryset

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(token__icontains=value)
        )
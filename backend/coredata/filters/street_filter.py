from django_filters import rest_framework as filters
from coredata.models import Street
from django.db.models import Q

class StreetFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    city = filters.CharFilter(method='filter_city')
    
    class Meta:
        model = Street
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(name_2__icontains=value) | 
            Q(type__name__icontains=value) |
            Q(type__abbreviation__icontains=value)
        )
    
    def filter_city(self, queryset, name, value):
        if value:
            return queryset.filter(Q(city_id=value) | Q(city_id__isnull=True))
        return queryset
    
from django_filters import rest_framework as filters
from ..models import ReadingBatch
from django.db.models import Q


class ReadingBatchFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    # exploitation = filters.NumberFilter(method='filter_exploitation')
    
    class Meta:
        model = ReadingBatch
        fields = ['search', 'status']

    def filter_search(self, queryset, name, value):
        if not value or not str(value).strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(token__icontains=value)
        )
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__token__in=status_values)
        return queryset
    
    """ def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(routes__positions__properties__supply_points__connection__exploitation__id=value) |
                Q(routes__positions__properties__supply_points__connection__exploitation__isnull=True)
            ).distinct()
        return queryset """
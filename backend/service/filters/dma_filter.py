from django_filters import rest_framework as filters
from service.models import DMA
from django.db.models import Q

class DMAFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = DMA
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) | Q(name__icontains=value)
        )
    
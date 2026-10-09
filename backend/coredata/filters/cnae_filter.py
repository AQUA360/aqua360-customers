from django_filters import rest_framework as filters
from coredata.models import CNAE
from django.db.models import Q

class CnaeFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = CNAE
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(description__icontains=value) |
            Q(token__icontains=value)
        )
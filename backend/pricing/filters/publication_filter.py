from django_filters import rest_framework as filters
from django.db.models import Q
from pricing.models import Publication

class PublicationFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Publication
        fields = ['search']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) |
            Q(boe_number__icontains=value) |
            Q(reference__icontains=value) |
            Q(content__icontains=value)
        ).distinct()

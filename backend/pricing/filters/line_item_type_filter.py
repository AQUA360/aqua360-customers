from django_filters import rest_framework as filters
from django.db.models import Q, Count
from pricing.models import LineItemType

class LineItemTypeFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    billing_range = filters.CharFilter(method='filter_billing_range')
    
    class Meta:
        model = LineItemType
        fields = ['search', 'billing_range']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) 
        )
    
    def filter_billing_range(self, queryset, name, value):
        if value:
            return queryset.filter(billing_range__id__in=value.split(','))
        return queryset
    
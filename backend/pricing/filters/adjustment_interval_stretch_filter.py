from django_filters import rest_framework as filters
from django.db.models import Q, Count
from pricing.models import AdjustmentIntervalStretch

class AdjustmentIntervalStretchFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    adjustment = filters.CharFilter(field_name='adjustment__id', lookup_expr='exact')
    price_interval_stretch = filters.CharFilter(field_name='price_interval_stretch__id', lookup_expr='exact')
    price_variable_stretch = filters.CharFilter(field_name='price_variable_stretch__id', lookup_expr='exact')
    
    class Meta:
        model = AdjustmentIntervalStretch
        fields = ['search', 'adjustment', 'price_interval_stretch', 'price_variable_stretch']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(coefficient__icontains=value)
        )
   
   
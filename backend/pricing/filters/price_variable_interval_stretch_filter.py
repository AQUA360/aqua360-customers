from django_filters import rest_framework as filters
from django.db.models import Q, Count
from pricing.models import PriceVariableIntervalStretch

class PriceVariableIntervalStretchFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    price_variable_interval = filters.CharFilter(method='filter_price_variable_interval')
    line_item_type = filters.CharFilter(method='filter_line_item_type')
    
    class Meta:
        model = PriceVariableIntervalStretch
        fields = ['search', 'price_variable_interval', 'line_item_type']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(price__icontains=value) |
            Q(proportional_price__icontains=value)
        )
    
    def filter_price_variable_interval(self, queryset, name, value):
        return queryset.filter(price_variable_interval=value)
    
    def filter_line_item_type(self, queryset, name, value):
        if value:
            return queryset.filter(price_variable_interval__line_item_types__id__in=value.split(','))
        return queryset


        
    
    
    
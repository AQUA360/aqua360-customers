from django_filters import rest_framework as filters
from django.db.models import Q, Count
from pricing.models import Adjustment

class AdjustmentFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    price_rate = filters.CharFilter(method='filter_by_price_rate', label="Price Rate")
    
    class Meta:
        model = Adjustment
        fields = ['search', 'price_rate']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value)
        )
    
    def filter_by_price_rate(self, queryset, name, value):
        return queryset.filter(
            Q(line_item_type__billing_range__price_rate_id=value)
        ).distinct()
   
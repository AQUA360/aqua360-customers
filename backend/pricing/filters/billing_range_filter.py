from django_filters import rest_framework as filters
from django.db.models import Q, Count
from pricing.models import BillingRange

class BillingRangeFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    price_rate = filters.CharFilter(field_name='price_rate__id', lookup_expr='exact')
    
    class Meta:
        model = BillingRange
        fields = ['search', 'price_rate']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) |
            Q(price_rate__name__icontains=value) |
            Q(price_rate__token__icontains=value)
        )
    
   
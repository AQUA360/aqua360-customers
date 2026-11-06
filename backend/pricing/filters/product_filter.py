from django_filters import rest_framework as filters
from django.db.models import Q, Count
from pricing.models import Product

class ProductFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    price_rates = filters.CharFilter(method='filter_price_rates')
    product_related = filters.CharFilter(method='filter_product_relation')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    exclude_origin_token = filters.CharFilter(method='filter_exclude_origin_token')
    
    class Meta:
        model = Product
        fields = ['search', 'price_rates', 'exclude_origin_token', 'exploitation']

    def filter_exploitation(self, queryset, name, value):
        # Els productes sense explotació són transversals: surten a totes
        return queryset.filter(Q(exploitation__id=value) | Q(exploitation__isnull=True))
    
    def filter_product_relation(self, queryset, name, value):
        return queryset.filter(product_relation=value)
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) 
        ).distinct()
    
    def filter_price_rates(self, queryset, name, value):
        return queryset.filter(price_rates=value)
    
    def filter_exclude_origin_token(self, queryset, name, value):
        if value:
            values = value.split(',')
            return queryset.exclude(origin__token__in=values)
        return queryset
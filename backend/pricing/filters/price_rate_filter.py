from django_filters import rest_framework as filters
from django.db.models import Q, Count
from pricing.models import PriceRate

class PriceRateFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    product = filters.CharFilter(field_name='product__id', lookup_expr='exact', method='filter_product')
    origin = filters.CharFilter(field_name='origin__token', lookup_expr='exact', method='filter_origin')
    exploitation = filters.NumberFilter(field_name='product__exploitation__id', lookup_expr='exact')
    
    class Meta:
        model = PriceRate
        fields = ['search', 'product', 'origin']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) |
            Q(product__name__icontains=value) |
            Q(product__token__icontains=value)
        )
    
    def filter_product(self, queryset, name, value):
        if value:
            prods_values = value.split(',')
            return queryset.filter(product__id__in=prods_values)
        return queryset
    
    def filter_origin(self, queryset, name, value):
        if value:
            origin_values = value.split(',')
            return queryset.filter(product__origin__token__in=origin_values)
        return queryset
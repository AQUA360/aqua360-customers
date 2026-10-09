from django_filters import rest_framework as filters
from ..models import OrderObservation

class OrderObservationFilter(filters.FilterSet):
    order = filters.NumberFilter(field_name='order__id', lookup_expr='exact')
    order_id = filters.NumberFilter(field_name='order__id', lookup_expr='exact')
    orders = filters.CharFilter(method='filter_order')
    
    class Meta:
        model = OrderObservation
        fields = ['order', 'orders', 'order_id']
    
    def filter_order(self, queryset, name, value):
        print(value)
        if value:
            order_values = value.split(',')
            return queryset.filter(order__id__in=order_values)
        return queryset
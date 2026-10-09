from django_filters import rest_framework as filters
from django.db.models import Q, Count
from order.models import Operator

class OperatorFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    orders = filters.CharFilter(method='filter_orders', label='Filter by orders')
    exclude = filters.NumberFilter(method='filter_exclude', label='Exclude operator with certain id')
    
    class Meta:
        model = Operator
        fields = ['search','status', 'orders']


    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) | Q(name__icontains=value) | Q(surname__icontains=value)
        )
    
    def filter_status(self, queryset, name, value):
        print(value)
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_orders(self, queryset, name, value):
        if value:
            return queryset.filter(orders__id__icontains=value).distinct()
        return queryset
    
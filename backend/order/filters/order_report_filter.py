from django_filters import rest_framework as filters
from django.db.models import Q, Count
from order.models import OrderReport

class OrderReportFilter(filters.FilterSet):
    
    order = filters.NumberFilter(field_name='order__id', lookup_expr='exact')
    
    class Meta:
        model = OrderReport
        fields = ['order']

    

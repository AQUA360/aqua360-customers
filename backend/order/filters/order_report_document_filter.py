from django_filters import rest_framework as filters
from django.db.models import Q, Count
from order.models import OrderReportDocument

class OrderReportDocumentFilter(filters.FilterSet):
    
    order_report = filters.NumberFilter(field_name='order_report__id', lookup_expr='exact')

    class Meta:
        model = OrderReportDocument
        fields = ['order_report']

    

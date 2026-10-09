from django_filters import rest_framework as filters
from ..models import InvoiceLineItem
from django.db.models import Q

class InvoiceLineItemFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    invoice = filters.CharFilter(field_name='invoice__id', lookup_expr='exact')
    company = filters.CharFilter(field_name='company__id', lookup_expr='exact')
    
    class Meta:
        model = InvoiceLineItem
        fields = ['search', 'invoice', 'company']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(invoice__token__icontains=value) |
            Q(invoice__number__icontains=value) |
            Q(token__icontains=value)
        )
    
   
from django_filters import rest_framework as filters
from ..models import PaymentRemittance
from django.db.models import Q


class PaymentRemittanceFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    is_return = filters.BooleanFilter(field_name='is_return')
    
    class Meta:
        model = PaymentRemittance
        fields = ['search', 'status', 'is_return']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value)
        )
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__token__in=status_values)
        return queryset
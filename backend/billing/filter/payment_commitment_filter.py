from django_filters import rest_framework as filters
from ..models import PaymentCommitment
from django.db.models import Q


class PaymentCommitmentFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    deposit = filters.CharFilter(field_name='commitment_deposit__id', lookup_expr='exact')
    is_guide = filters.BooleanFilter(field_name='is_guide', label='is_guide')
    status_tokens = filters.CharFilter(method='filter_status_tokens')
    
    class Meta:
        model = PaymentCommitment
        fields = ['search', 'deposit', 'is_guide', 'status_tokens']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(invoices__token__icontains=value)
        )
    
    def filter_status_tokens(self, queryset, name, value):
        if value:
            status_tokens = value.split(',')
            return queryset.filter(status__token__in=status_tokens)
        return queryset
from django_filters import rest_framework as filters
from contract.models import PaymentType
from coredata.models import ConfigProject
from ..models import JoinedPayment
from django.db.models import Q


class JoinedPaymentFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    start_payment_date = filters.DateFilter(field_name='payment_date', lookup_expr='gte')
    end_payment_date = filters.DateFilter(field_name='payment_date', lookup_expr='lte')
    start_due_date = filters.DateFilter(field_name='due_date', lookup_expr='gte')
    end_due_date = filters.DateFilter(field_name='due_date', lookup_expr='lte')
    total_final = filters.NumberFilter(field_name='total_final', lookup_expr='exact')
    
    payment_type = filters.CharFilter(method='filter_payment_type')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    
    
    class Meta:
        model = JoinedPayment
        fields = [
            'search', 'start_payment_date', 'end_payment_date', 'start_due_date', 'end_due_date',
            'status', 'total_final', 'payment_type'
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(payments__invoice__token__icontains=value) |
            Q(payments__invoice__number__icontains=value) |
            Q(payments__invoice__contract__token__icontains=value) |
            Q(payments__invoice__serie_final__icontains=value) |
            Q(payments__invoice__customer_token_final__icontains=value) |
            Q(payments__invoice__customer_final__icontains=value) |
            Q(payments__commitment_deposit__token__icontains=value) |
            Q(payments__commitment_deposit__contract__token__icontains=value) |
            Q(payment_type_name__icontains=value) |
            Q(token__icontains=value)
        ).distinct()
        
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(payments__invoice__exploitation__id=value) |
                Q(payments__commitment_deposit__invoices__exploitation__id=value) |
                Q(payments__contract__supply_point_default__connection__exploitation__id=value) |
                Q(payments__invoice__isnull=True, payments__commitment_deposit__isnull=True, payments__contract__isnull=True)
            ).distinct()
        return queryset
    
    def filter_status(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(status__id__in=value_ids)
        return queryset
    
    def filter_payment_type_token(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(payment_type_token__in=value_ids)
        return queryset
    
    def filter_payment_type(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(payment_type__id__in=value_ids)
        return queryset
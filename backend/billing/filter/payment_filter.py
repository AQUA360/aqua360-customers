from django_filters import rest_framework as filters
from contract.models import PaymentType
from coredata.models import ConfigProject
from ..models import Payment
from django.db.models import Q


class PaymentFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    invoice = filters.CharFilter(field_name='invoice__id', lookup_expr='exact')
    status = filters.CharFilter(method='filter_status')
    origin = filters.CharFilter(method='filter_origin')
    is_excluded = filters.BooleanFilter(field_name='is_excluded', method='filter_is_excluded')
    is_pending = filters.BooleanFilter(field_name='is_pending', method='filter_is_pending')
    is_debit = filters.BooleanFilter(field_name='is_debit', method='filter_is_debit')
    is_einvoice = filters.BooleanFilter(field_name='is_einvoice', method='filter_is_einvoice')
    start_date = filters.DateFilter(field_name='payment_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='payment_date', lookup_expr='lte')
    type = filters.CharFilter(method='filter_type')
    commitment_deposit = filters.CharFilter(field_name='commitment_deposit__id', lookup_expr='exact')
    remittance = filters.CharFilter(method='filter_remittance')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    amount = filters.NumberFilter(field_name='amount', lookup_expr='exact')
    
    return_reason = filters.CharFilter(method='filter_reject_ids')
    reject_motive = filters.CharFilter(method='filter_reject_ids')
    reject = filters.CharFilter(method='filter_reject_ids')
    payment_origin = filters.CharFilter(method='filter_payment_origin')

    
    class Meta:
        model = Payment
        fields = [
            'search', 'invoice', 'is_pending', 'is_debit',
            'origin', 'start_date', 'end_date',
            'status', 'is_excluded', 'type', 'commitment_deposit', 
            'exploitation', 'return_reason', 'payment_origin'
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(invoice__token__icontains=value) |
            Q(invoice__number__icontains=value) |
            Q(token__icontains=value)
        )
        
    def filter_payment_origin(self, queryset, name, value):
        if value:
            origins = value.split(',')
            return queryset.filter(movements__payment_origin__in=origins).distinct()
        return queryset
        
    def filter_type(self, queryset, name, value):
        if value:
            token = PaymentType.objects.filter(id=value).first().token
            return queryset.filter(payment_type_token=token)
        return queryset
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(invoice__exploitation__id=value) |
                Q(commitment_deposit__invoices__exploitation__id=value) |
                Q(contract__supply_point_default__connection__exploitation__id=value)
            ).distinct()
        return queryset
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_is_excluded(self, queryset, name, value):
        if value is True:
            return queryset.filter(is_excluded=True)
        if value is False:
            return queryset.filter(is_excluded=False)
        return queryset
    
    def filter_is_pending(self, queryset, name, value):
        if value is True:
            status_pending_token = ConfigProject.objects.get(
                token='invoice_status_pending_token'
            ).value
            return queryset.filter(status__token=status_pending_token)
        return queryset
    
    def filter_is_debit(self, queryset, name, value):
        if value is True:
            debit_token = ConfigProject.objects.get(
                token='direct_debit_token'
            ).value
            return queryset.filter(payment_type_token=debit_token)
        return queryset
    
    def filter_is_einvoice(self, queryset, name, value):
        if value is True:
            debit_token = ConfigProject.objects.get(
                token='e_invoice_token'
            ).value
            return queryset.filter(payment_type_token=debit_token)
        return queryset
    
    def filter_origin(self, queryset, name, value):
        if value:
            origin_values = value.split(',')
            return queryset.filter(invoice__origin__id__in=origin_values)
        return queryset

    def filter_remittance(self, queryset, name, value):
        if value:
            remittance_values = value.split(',')
            return queryset.filter(remittances__id__in=remittance_values)
        return queryset
        
    def filter_reject_ids(self, queryset, name, value):
        if value:
            try:
                ids = [int(v) for v in value.split(',') if v.strip()]
                return queryset.filter(reject__id__in=ids)
            except Exception:
                return queryset
        return queryset
from django_filters import rest_framework as filters
from ..models import CommitmentDeposit
from django.db.models import Q


class CommitmentDepositFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    contract = filters.CharFilter(
        field_name='contract__id',
        lookup_expr='exact'
    )
    invoice = filters.NumberFilter(
        field_name='invoices__id',
        lookup_expr='exact'
    )

    class Meta:
        model = CommitmentDeposit
        fields = ['search', 'status', 'contract', 'invoice', 'exploitation']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        # Cada paraula ha de coincidir en algun camp (AND entre paraules) perque
        # "Nom Cognom" pugui creuar name i surname del titular.
        terms = value.split()
        if not terms:
            return queryset

        for term in terms:
            queryset = queryset.filter(
                Q(token__icontains=term) |
                Q(invoices__serie_final__icontains=term) |
                Q(contract__token__icontains=term) |
                Q(contract__holder__token__icontains=term) |
                Q(contract__holder__name__icontains=term) |
                Q(contract__holder__surname__icontains=term) |
                Q(customer_final__icontains=term) |
                Q(customer_token_final__icontains=term) |
                Q(invoices__token__icontains=term)
            )
        return queryset.distinct()
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(invoices__exploitation__id=value) 
            ).distinct()
        return queryset
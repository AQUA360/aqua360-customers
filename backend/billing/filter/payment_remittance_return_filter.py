from django_filters import rest_framework as filters
from ..models import PaymentRemittanceReturn
from django.db.models import Q


class PaymentRemittanceReturnFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = PaymentRemittanceReturn
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value)
        )
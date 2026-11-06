from django_filters import rest_framework as filters
from ..models import Billing
from django.db.models import Q


class BillingFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    exploitation = filters.NumberFilter(field_name='biller__exploitation_id')
    
    class Meta:
        model = Billing
        fields = ['search', 'exploitation']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(biller__name__icontains=value) |
            Q(biller__token__icontains=value) |
            Q(token__icontains=value)
        )
    
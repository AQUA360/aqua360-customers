from django_filters import rest_framework as filters
from ..models import BillingBatch
from django.db.models import Q


class BillingBatchFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')

    class Meta:
        model = BillingBatch
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(token__icontains=value)
        )

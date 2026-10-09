from django_filters import rest_framework as filters
from coredata.models import Bank
from django.db.models import Q

class BankFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Bank
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(token__icontains=value) |
            Q(bic__icontains=value)
        )
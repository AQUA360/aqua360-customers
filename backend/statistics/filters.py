from django_filters import rest_framework as filters
from .models import *
from django.db.models import Q

class BillingReportFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = BillingReport
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(type__icontains=value)
        )

class GeneralReportFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = GeneralReport
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(type__token__icontains=value)
        )
        
class AccountingCodeFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = AccountingCode
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) | 
            Q(values__token__icontains=value) |
            Q(values__description__icontains=value)
        ).distinct()


class DailyDocumentFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    
    class Meta:
        model = DailyDocument
        fields = ['search', 'status']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) |
            Q(template__name__icontains=value) |
            Q(template__available_report__name__icontains=value)
        )
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
from django_filters import rest_framework as filters
from ..models import Fraud
from coredata.models import ConfigProject
from service.models import SupplyPoint
from django.db.models import Q, Count, F
from django.db import models


class FraudFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    supply_point = filters.NumberFilter(field_name='supply_point__id', lookup_expr='exact')
    exploitation = filters.NumberFilter(field_name='supply_point__connection__exploitation__id', lookup_expr='exact')
    
    class Meta:
        model = Fraud
        fields = ['search', 'status', 'supply_point', 'exploitation']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(contract__token__icontains=value) |
            Q(contract__holder__token__icontains=value) |
            Q(supply_point__token__icontains=value) 
        )
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
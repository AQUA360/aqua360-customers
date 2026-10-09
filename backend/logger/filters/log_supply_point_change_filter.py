# logger/filters/log_supply_point_change_filter.py

from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogSupplyPointChange

class LogSupplyPointChangeFilter(filters.FilterSet):
    supplypoint = filters.NumberFilter(field_name='supply_point__id')
    
    class Meta:
        model = LogSupplyPointChange
        fields = ["action","timestamp"]
        

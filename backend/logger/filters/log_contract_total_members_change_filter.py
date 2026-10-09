# logger/filters/log_supply_point_change_filter.py

from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogContractTotalMembers

class LogContractTotalMembersFilter(filters.FilterSet):
    object = filters.NumberFilter(field_name='object__id')
    
    class Meta:
        model = LogContractTotalMembers
        fields = ["object","timestamp"]
        

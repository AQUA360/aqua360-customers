from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogLineItemTypeChange

class LogLineItemTypeChangeFilter(filters.FilterSet):
    
    object = filters.NumberFilter(field_name='object__id')
    
    class Meta:
        model = LogLineItemTypeChange
        fields = ["object","timestamp"]

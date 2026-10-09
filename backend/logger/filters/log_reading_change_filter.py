from django_filters import rest_framework as filters
from logger.models import LogReadingChange

class LogReadingChangeFilter(filters.FilterSet):
    contract = filters.NumberFilter(field_name='contract__id')
    meter = filters.NumberFilter(field_name='meter__id')
    
    class Meta:
        model = LogReadingChange
        fields = ["contract", "meter", "timestamp"]

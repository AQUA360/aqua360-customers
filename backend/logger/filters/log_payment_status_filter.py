from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogPaymentStatusChange

class LogPaymentStatusChangeFilter(filters.FilterSet):
    
    object = filters.NumberFilter(field_name='object__id')
    
    class Meta:
        model = LogPaymentStatusChange
        fields = ["object","timestamp"]

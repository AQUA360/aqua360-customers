from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogJoinedPaymentStatusChange

class LogJoinedPaymentStatusChangeFilter(filters.FilterSet):
    
    object = filters.NumberFilter(field_name='object__id')
    
    class Meta:
        model = LogJoinedPaymentStatusChange
        fields = ["object","timestamp"]

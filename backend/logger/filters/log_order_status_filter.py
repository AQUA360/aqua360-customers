from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogOrderStatus

class LogOrderStatusFilter(filters.FilterSet):
    
    class Meta:
        model = LogOrderStatus
        fields = ["object","timestamp"]

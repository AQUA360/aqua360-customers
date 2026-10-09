from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogSupplyCutStatus

class LogSupplyCutStatusFilter(filters.FilterSet):
    
    class Meta:
        model = LogSupplyCutStatus
        fields = ["object","timestamp"]

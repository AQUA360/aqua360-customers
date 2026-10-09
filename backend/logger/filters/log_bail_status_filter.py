from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogBailStatus

class LogBailStatusFilter(filters.FilterSet):
    
    class Meta:
        model = LogBailStatus
        fields = ["object","timestamp"]

from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogConnectionRequestStatus

class LogConnectionRequestStatusFilter(filters.FilterSet):
    
    class Meta:
        model = LogConnectionRequestStatus
        fields = ["object","timestamp"]

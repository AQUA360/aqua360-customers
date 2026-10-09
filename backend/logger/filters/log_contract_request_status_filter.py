from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogContractRequestStatus

class LogContractRequestStatusFilter(filters.FilterSet):
    
    class Meta:
        model = LogContractRequestStatus
        fields = ["object","timestamp"]

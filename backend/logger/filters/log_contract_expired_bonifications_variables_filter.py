from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogContractExpiredBonificationsVariables

class LogContractExpiredBonificationsVariablesFilter(filters.FilterSet):
    
    class Meta:
        model = LogContractExpiredBonificationsVariables
        fields = ["object","timestamp"]

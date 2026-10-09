from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogCommunicationStatusChange

class LogCommunicationStatusChangeFilter(filters.FilterSet):
    
    class Meta:
        model = LogCommunicationStatusChange
        fields = ["object","timestamp"]
